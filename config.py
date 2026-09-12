"""
Configuration centralisee du LLM utilise par tous les agents.

Permet de basculer entre inference locale (Ollama) et cloud (Groq)
en changeant une seule variable, sans toucher au code des agents.
Utile pour comparer la fiabilite des deux backends sur une
architecture identique (exigence de reproductibilite).

Prerequis Groq :
1. Cle API sur https://console.groq.com
2. pip install langchain-groq python-dotenv
3. Fichier .env contenant : GROQ_API_KEY=gsk_...
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ------------------------------------------------------------------
# Choix du backend : "ollama" (local) ou "groq" (cloud)
# ------------------------------------------------------------------
LLM_BACKEND = os.getenv("LLM_BACKEND", "groq")

# modeles utilises selon le backend
OLLAMA_MODEL = "llama3.1"

# Note : llama-3.3-70b-versatile produit parfois des tool calls au
# mauvais format (<function=...>) rejetes par l'API avec un code 400
# (tool_use_failed). gpt-oss-120b est plus stable sur ce point et
# dispose de quotas journaliers de tokens plus eleves.
GROQ_MODEL = "openai/gpt-oss-120b"


def get_llm():
    """Retourne l'instance LLM configuree, avec tool calling active.

    Tous les agents appellent cette fonction : changer LLM_BACKEND
    change le modele partout, garantissant que les comparaisons
    portent bien sur le meme code."""

    if LLM_BACKEND == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=OLLAMA_MODEL, temperature=0)

    elif LLM_BACKEND == "groq":
        from langchain_groq import ChatGroq

        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError(
                "GROQ_API_KEY absente. Cree un fichier .env contenant :\n"
                "GROQ_API_KEY=gsk_ta_cle_ici"
            )

        return ChatGroq(model=GROQ_MODEL, temperature=0)

    raise ValueError(f"Backend inconnu : {LLM_BACKEND} (attendu 'ollama' ou 'groq')")


def get_embeddings():
    """Les embeddings restent TOUJOURS locaux (Ollama).

    Groq ne propose pas de modele d'embeddings : seule la generation
    bascule vers le cloud, la base vectorielle ChromaDB continue
    d'utiliser nomic-embed-text en local."""
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(model="nomic-embed-text")