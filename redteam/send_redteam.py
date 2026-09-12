# send_redteam.py — version avec historique + timeout
import os
import sys
import uuid
import concurrent.futures

PROJECT_ROOT = r"C:\enis"
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from langgraph.errors import GraphRecursionError

from database import init_db
from session import set_session
from agents.triage_agent import run_helpdesk

init_db()
set_session("E1042", "Sarah Ben Ali")

_sessions = {}  # session_id -> historique de la conversation
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)  # meme cap que workers/max-concurrency
TIMEOUT_S = 90  # a ajuster selon la latence normale observee sur vos tests qui passent


def _classifier_erreur(e: Exception) -> str:
    texte = str(e)
    if "tool_use_failed" in texte or "Failed to call a function" in texte:
        return "model_failure"
    if "rate_limit" in texte or "429" in texte:
        return "rate_limit"
    return "erreur_technique"


def call_api(prompt, options, context):
    session_id = None
    if context and context.get("vars"):
        session_id = context["vars"].get("sessionId")
    if not session_id:
        session_id = str(uuid.uuid4())

    history = _sessions.setdefault(session_id, [])

    try:
        future = _executor.submit(run_helpdesk, prompt, history=history if history else None)
        result = future.result(timeout=TIMEOUT_S)
        reponse = result["messages"][-1].content
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": reponse})
        return {"output": reponse, "sessionId": session_id}
    except concurrent.futures.TimeoutError:
        return {"output": f"[TIMEOUT] run_helpdesk n'a pas repondu en {TIMEOUT_S}s.", "sessionId": session_id, "error": "timeout"}
    except GraphRecursionError:
        return {"output": "[LIMITE_TOURS] Recursion limit atteinte (MAX_TOURS=8).", "sessionId": session_id}
    except Exception as e:
        cat = _classifier_erreur(e)
        return {"output": f"[{cat.upper()}] {e}", "sessionId": session_id, "error": str(e)}