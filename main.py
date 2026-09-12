"""
NexaTech HelpDesk -- point d'entree.

Prerequis :
  pip install langgraph langchain-groq langchain-chroma chromadb langchain-ollama python-dotenv
  ollama pull nomic-embed-text        (embeddings locaux)
  .env contenant GROQ_API_KEY=...

Lancer :
  python main.py
"""

from langgraph.errors import GraphRecursionError

from database import init_db
from session import set_session, get_session
from agents.triage_agent import run_helpdesk

DEBUG = True


def afficher_trace(messages):
    print("  --- trace ---")
    for msg in messages:
        role = msg.__class__.__name__
        if role == "AIMessage" and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  [APPEL] {tc['name']}({tc['args']})")
        elif role == "ToolMessage":
            contenu = msg.content.replace("\n", " ")[:200]
            print(f"  [RESULTAT] {contenu}")
    print("  -------------")


def classifier_erreur(e: Exception) -> str:
    """Distingue model_failure d'un vrai blocage de securite.
    Indispensable pour ne pas fausser les taux mesures en Phase III."""
    texte = str(e)
    if "tool_use_failed" in texte or "Failed to call a function" in texte:
        return "model_failure"
    if "rate_limit" in texte or "429" in texte:
        return "rate_limit"
    return "erreur_technique"


if __name__ == "__main__":
    init_db()
    set_session("E1042", "Sarah Ben Ali")
    session = get_session()

    print("=" * 60)
    print("NexaTech HelpDesk IT")
    print(f"Session : {session.full_name} ({session.employee_id})")
    print("Tape 'quit' pour sortir.")
    print("=" * 60 + "\n")

    historique = []

    while True:
        question = input("Toi : ")

        if question.strip().lower() in ("quit", "exit", "q"):
            print("A bientot.")
            break

        try:
            result = run_helpdesk(question, historique)

            if DEBUG:
                afficher_trace(result["messages"])

            reponse = result["messages"][-1].content
            print(f"HelpDesk : {reponse}\n")

            # conserve le fil pour les conversations multi-tours
            historique.append({"role": "user", "content": question})
            historique.append({"role": "assistant", "content": reponse})

        except GraphRecursionError:
            print("HelpDesk : [ARRET] Limite de tours atteinte.\n")

        except Exception as e:
            cat = classifier_erreur(e)
            if cat == "model_failure":
                print("HelpDesk : [MODEL_FAILURE] Appel d'outil mal forme.")
                print("Ce n'est PAS un blocage de securite.\n")
            elif cat == "rate_limit":
                print("HelpDesk : [RATE_LIMIT] Quota atteint, attends une minute.\n")
            else:
                print(f"ERREUR technique : {e}\n")