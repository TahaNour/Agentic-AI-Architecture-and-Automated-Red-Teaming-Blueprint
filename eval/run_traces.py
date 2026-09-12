"""
Etape 1 du pipeline : PRODUIRE les traces.

Ce script execute ton agent sur chaque cas du jeu de test et sauvegarde
le resultat en JSON. Il ne calcule AUCUNE metrique.

Pourquoi separer ? Parce que produire une trace coute du temps et des
tokens Groq, alors que la noter est gratuit et instantane. Tu vas
retoucher tes metriques dix fois : tu ne veux pas relancer l'agent dix
fois. C'est le meme principe qu'en science : on collecte les donnees
une fois, on les analyse autant de fois qu'on veut.

Lancement (depuis le dossier enis/, pas depuis eval/) :
    python -m eval.run_traces
"""

import json
import time
from pathlib import Path

from database import init_db, get_connection
from session import set_session
from agents.triage_agent import run_helpdesk

from eval import tracing
from eval.dataset import TEST_CASES, SESSION_ID, SESSION_NAME


TRACES_DIR = Path("eval/traces")


# ------------------------------------------------------------------
# Lecture du journal d'audit
# ------------------------------------------------------------------

def audit_snapshot() -> int:
    """Retourne l'id du dernier evenement d'audit.

    On prend une photo AVANT chaque execution pour ne recuperer ensuite
    que les lignes ecrites par CETTE execution.
    """
    conn = get_connection()
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM audit_log").fetchone()
    conn.close()
    return row["m"]


def audit_since(last_id: int) -> list:
    """Retourne les evenements d'audit ecrits depuis le snapshot.

    C'est la VERITE TERRAIN de ton systeme : ces lignes sont ecrites par
    du code Python deterministe (log_action dans database.py), jamais
    par le LLM. Un LLM peut mentir dans sa reponse ; il ne peut pas
    falsifier ce journal.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT session_user, action, target, outcome FROM audit_log "
        "WHERE id > ? ORDER BY id",
        (last_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------
# Execution
# ------------------------------------------------------------------

def run_case(case: dict) -> dict:
    """Execute un cas de test et retourne sa trace complete."""

    tracing.start_trace()          # ouvre la boite noire
    before = audit_snapshot()      # photo du journal d'audit

    started = time.time()
    error = None

    try:
        result = run_helpdesk(case["question"])
        triage_messages = result["messages"]
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        triage_messages = []

    duration = round(time.time() - started, 2)

    trace = tracing.to_serializable(
        question=case["question"],
        triage_messages=triage_messages,
        events=tracing.get_events(),
    )

    trace.update({
        "id": case["id"],
        "category": case["category"],
        "reference": case["reference"],
        "ref_tools": case["ref_tools"],
        "must_refuse": case["must_refuse"],
        "attack_class": case.get("attack_class"),
        "audit_entries": audit_since(before),   # <-- la verite terrain
        "duration_s": duration,
        "error": error,
    })

    return trace


def main():
    init_db()
    set_session(SESSION_ID, SESSION_NAME)
    TRACES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Session de test : {SESSION_NAME} ({SESSION_ID})")
    print(f"{len(TEST_CASES)} cas a executer\n")

    traces = []
    for case in TEST_CASES:
        print(f"  [{case['id']}] {case['question'][:55]}...", end=" ", flush=True)
        trace = run_case(case)
        traces.append(trace)

        n_tools = sum(
            len(m.get("tool_calls", []))
            for ev in trace["sub_agent_events"]
            for m in ev["messages"]
        )
        flag = "ERREUR" if trace["error"] else f"{n_tools} outil(s)"
        cross = sum(1 for a in trace["audit_entries"] if a["outcome"] == "cross_account")
        if cross:
            flag += f" / {cross} CROSS-ACCOUNT"

        print(f"{flag}  ({trace['duration_s']}s)")

        time.sleep(5)   # respiration : evite les 429 de Groq

    out = TRACES_DIR / "traces.json"
    out.write_text(json.dumps(traces, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(traces)} traces ecrites dans {out}")
    print("Etape suivante : python -m eval.evaluate")


if __name__ == "__main__":
    main()
