"""
Collecteur de traces d'execution.

POURQUOI CE FICHIER EXISTE
--------------------------
Dans ton architecture, ask_ops_agent et ask_knowledge_agent sont des
outils LangChain qui invoquent un SOUS-GRAPHE puis ne retournent qu'une
chaine de caracteres :

    result = ops_agent_app.invoke(...)
    return result["messages"][-1].content    # <-- tout le reste est perdu

Consequence : les VRAIS appels d'outils (query_asset_db, reset_user_password,
search_procedures...) n'apparaissent jamais dans result["messages"] du
triage. Ragas ne peut donc pas les evaluer.

Ce module ouvre une "boite noire" partagee dans laquelle chaque sous-agent
depose ses messages internes avant de retourner sa reponse. On appelle ca
de l'INSTRUMENTATION : on ne change pas le comportement du systeme, on
l'observe.

ATTENTION - POURQUOI UNE VARIABLE GLOBALE ET PAS threading.local()
------------------------------------------------------------------
Premiere version de ce fichier : threading.local(). C'etait un bug.

LangGraph execute les outils synchrones dans un pool de threads
(get_executor_for_config -> ThreadPoolExecutor), meme pour un seul appel.
Resultat : start_trace() s'executait dans le thread principal, mais
record() dans un thread ouvrier, ou la variable locale valait None.
La trace ressortait donc systematiquement vide.

Une variable de module est partagee par tous les threads : c'est
exactement ce qu'il faut ici. Elle suffit car run_traces.py execute les
cas SEQUENTIELLEMENT. Si tu paralleles un jour tes executions, remplace
_EVENTS par un contextvars.ContextVar, qui se propage correctement a
travers les threads et les taches asyncio.
"""

_EVENTS = None


# ------------------------------------------------------------------
# API du collecteur
# ------------------------------------------------------------------

def start_trace():
    """Ouvre une nouvelle trace vide. A appeler AVANT chaque execution."""
    global _EVENTS
    _EVENTS = []


def record(agent_name: str, messages: list):
    """Depose les messages internes d'un sous-agent dans la trace courante.

    Appelee par ask_ops_agent et ask_knowledge_agent.
    Si aucune trace n'est ouverte (usage normal via main.py), ne fait rien :
    l'instrumentation est donc totalement transparente en production.
    """
    if _EVENTS is None:
        return
    _EVENTS.append({"agent": agent_name, "messages": messages})


def get_events() -> list:
    """Retourne les evenements captures pendant l'execution courante."""
    return _EVENTS or []


# ------------------------------------------------------------------
# Conversion vers le format attendu par Ragas
# ------------------------------------------------------------------

def to_ragas_messages(question: str, triage_messages: list, events: list,
                      level: str = "tools"):
    """Convertit une execution en liste de messages Ragas.

    Deux niveaux de lecture, volontairement separes :

    level="delegation"
        Ne garde que le niveau triage : ask_ops_agent / ask_knowledge_agent.
        Repond a la question "l'orchestrateur a-t-il bien route la demande ?"

    level="tools"
        Aplatit les appels d'outils REELS des sous-agents.
        Repond a la question "les bonnes actions ont-elles ete executees,
        avec les bons arguments ?"

    Mesurer les deux separement est ce qui te permettra de dire, quand un
    score chute : "le probleme vient du routage" ou "le probleme vient de
    l'agent Ops". Sans cette separation, tu as un chiffre mais pas de
    diagnostic.
    """
    from ragas.messages import HumanMessage, AIMessage, ToolMessage, ToolCall

    msgs = [HumanMessage(content=question)]

    if level == "delegation":
        source = [{"agent": "triage", "messages": triage_messages}]
    elif level == "tools":
        source = events
    else:
        raise ValueError("level doit valoir 'delegation' ou 'tools'")

    for event in source:
        for m in event["messages"]:
            kind = m.__class__.__name__

            if kind == "AIMessage" and getattr(m, "tool_calls", None):
                msgs.append(AIMessage(
                    content=m.content or "",
                    tool_calls=[
                        ToolCall(name=tc["name"], args=tc["args"])
                        for tc in m.tool_calls
                    ],
                ))

            elif kind == "ToolMessage":
                msgs.append(ToolMessage(content=str(m.content)))

    # la reponse finale vue par l'utilisateur vient toujours du triage
    final = triage_messages[-1].content if triage_messages else ""
    msgs.append(AIMessage(content=final))

    return msgs


def to_serializable(question: str, triage_messages: list, events: list) -> dict:
    """Version JSON-serialisable, pour sauvegarder les traces sur disque.

    Pourquoi sauvegarder ? Parce qu'executer ton agent coute du temps et
    des tokens Groq. Tu veux pouvoir relancer l'EVALUATION sans relancer
    l'AGENT. Separer "produire la trace" de "noter la trace" est un
    principe de base : sinon chaque essai de metrique recoute une
    execution complete.
    """
    def dump(messages):
        out = []
        for m in messages:
            kind = m.__class__.__name__
            entry = {"type": kind, "content": str(m.content or "")}
            if kind == "AIMessage" and getattr(m, "tool_calls", None):
                entry["tool_calls"] = [
                    {"name": tc["name"], "args": tc["args"]} for tc in m.tool_calls
                ]
            out.append(entry)
        return out

    return {
        "question": question,
        "triage_messages": dump(triage_messages),
        "sub_agent_events": [
            {"agent": e["agent"], "messages": dump(e["messages"])} for e in events
        ],
        "final_answer": triage_messages[-1].content if triage_messages else "",
    }


def from_serializable(data: dict, level: str = "tools"):
    """Recharge une trace JSON en messages Ragas (operation inverse)."""
    from ragas.messages import HumanMessage, AIMessage, ToolMessage, ToolCall

    msgs = [HumanMessage(content=data["question"])]

    if level == "delegation":
        source = [{"messages": data["triage_messages"]}]
    else:
        source = data["sub_agent_events"]

    for event in source:
        for m in event["messages"]:
            if m["type"] == "AIMessage" and m.get("tool_calls"):
                msgs.append(AIMessage(
                    content=m["content"],
                    tool_calls=[
                        ToolCall(name=tc["name"], args=tc["args"])
                        for tc in m["tool_calls"]
                    ],
                ))
            elif m["type"] == "ToolMessage":
                msgs.append(ToolMessage(content=m["content"]))

    msgs.append(AIMessage(content=data["final_answer"]))
    return msgs