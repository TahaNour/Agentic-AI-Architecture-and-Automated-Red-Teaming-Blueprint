# Modifications à apporter aux fichiers existants

Trois modifications, six lignes au total. Aucune ne change le comportement
du système : ce sont des points d'observation, pas des changements de logique.

---

## 1. `agents/ops_agent.py`

**En haut du fichier**, avec les autres imports :

```python
from eval import tracing
```

**Tout en bas**, dans `ask_ops_agent`, ajouter une seule ligne :

```python
@tool
def ask_ops_agent(request: str) -> str:
    """Delegue une action TECHNIQUE a l'Ops Agent : verifier un service,
    consulter du materiel, lire un ticket, reinitialiser un mot de passe,
    lancer un diagnostic, creer un ticket."""
    result = ops_agent_app.invoke(
        {"messages": [{"role": "user", "content": request}]},
        config={"recursion_limit": 8},
    )
    tracing.record("ops", result["messages"])      # <<< AJOUTER CETTE LIGNE
    return result["messages"][-1].content
```

---

## 2. `agents/knowledge_agent.py`

**En haut du fichier** :

```python
from eval import tracing
```

**Tout en bas**, dans `ask_knowledge_agent` :

```python
@tool
def ask_knowledge_agent(request: str) -> str:
    """Delegue une recherche documentaire au Knowledge Agent : procedures
    IT officielles, historique des tickets, profil et preferences de
    l'employe. N'effectue AUCUNE action technique."""
    result = knowledge_agent_app.invoke(
        {"messages": [{"role": "user", "content": request}]},
        config={"recursion_limit": 8},
    )
    tracing.record("knowledge", result["messages"])   # <<< AJOUTER CETTE LIGNE
    return result["messages"][-1].content
```

---

## 3. `agents/triage_agent.py`

Aucune modification obligatoire. Optionnelle, pour que `run_helpdesk`
reste utilisable directement depuis un notebook :

```python
def run_helpdesk(user_input: str, history=None):
    from eval import tracing
    tracing.start_trace()          # <<< OPTIONNEL
    messages = (history or []) + [{"role": "user", "content": user_input}]
    return triage_app.invoke(
        {"messages": messages},
        config={"recursion_limit": MAX_TOURS},
    )
```

`run_traces.py` appelle déjà `tracing.start_trace()` lui-même, donc cette
modification n'est utile que si tu veux tracer depuis ailleurs.

---

## Pourquoi `tracing.record()` ne casse rien en production

Regarde le code de `record()` :

```python
def record(agent_name, messages):
    events = getattr(_local, "events", None)
    if events is None:
        return          # <-- aucune trace ouverte : ne fait rien
    events.append(...)
```

Quand tu lances `python main.py` normalement, `start_trace()` n'est jamais
appelé, donc `_local.events` vaut `None`, donc `record()` retourne
immédiatement. Coût : une comparaison. Ton agent se comporte exactement
comme avant.

C'est un principe d'instrumentation important : **l'observateur ne doit pas
modifier l'observé**. Si ton code d'évaluation change le comportement de
l'agent, tu mesures ton instrumentation, pas ton agent.

---

## Installation

```bash
cd enis/
pip install ragas openai
```

`openai` est nécessaire uniquement pour le client HTTP du juge — on l'utilise
pour parler à l'endpoint compatible OpenAI de Groq, pas à OpenAI.

## Ordre d'exécution

```bash
cd enis/                    # IMPORTANT : toujours depuis la racine du projet
                            # (database.py utilise un chemin relatif "nexatech.db")

python -m eval.run_traces   # 1. exécute l'agent, écrit eval/traces/traces.json
python -m eval.evaluate     # 2. note les traces, écrit eval/traces/results.json
```
