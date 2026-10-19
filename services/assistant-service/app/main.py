"""
assistant-service : assistant operateur RAG local (Ollama + LangChain).

Role : aider l'operateur a comprendre un incident et a retrouver la bonne procedure, en
s'appuyant sur les documents du projet (architecture, runbook, procedures SOC). Il repond
en citant ses sources et dit quand il ne sait pas.

Garde-fous : LECTURE SEULE. L'assistant n'a aucun acces privilegie au systeme, ne declenche
aucune remediation et ne manipule aucun secret. Il ne fait qu'interroger une base
documentaire vectorisee et un modele de langage local (<= 8B parametres).
"""
import os
import glob
import logging

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"assistant","msg":"%(message)s"}')
log = logging.getLogger("assistant")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH = os.getenv("CHROMA_PATH", "/data/chroma")
DOCS_PATH = os.getenv("DOCS_PATH", "/docs")

app = FastAPI(title="RESILIENCE-ALPHA assistant-service", version="1.0.0")
ASK_TOTAL = Counter("assistant_questions_total", "Questions posees")

_vectorstore = None
_llm = None
_ready = False
_error = None

SYSTEM_PROMPT = (
    "Tu es l'assistant operateur de la plateforme PayAlpha. Tu reponds en francais, de "
    "facon concise et factuelle, en t'appuyant UNIQUEMENT sur le contexte fourni. Si le "
    "contexte ne permet pas de repondre, dis-le clairement et invite a consulter le "
    "runbook. Tu ne proposes jamais d'action privilegiee : tu orientes vers la procedure."
)


class Question(BaseModel):
    question: str


def _load_documents():
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    docs = []
    for path in glob.glob(os.path.join(DOCS_PATH, "**", "*.md"), recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(path, DOCS_PATH)
            docs.append(Document(page_content=text, metadata={"source": rel}))
        except Exception as e:  # noqa: BLE001
            log.warning(f"lecture impossible {path}: {e}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    return splitter.split_documents(docs)


def build_index():
    """Construit la base vectorielle. Necessite Ollama disponible (embeddings)."""
    global _vectorstore, _llm, _ready, _error
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    from langchain_chroma import Chroma
    try:
        embeddings = OllamaEmbeddings(base_url=OLLAMA_URL, model=EMBED_MODEL)
        chunks = _load_documents()
        _vectorstore = Chroma.from_documents(
            chunks, embedding=embeddings, persist_directory=CHROMA_PATH)
        _llm = ChatOllama(base_url=OLLAMA_URL, model=OLLAMA_MODEL, temperature=0)
        _ready = True
        _error = None
        log.info(f"index construit : {len(chunks)} fragments")
    except Exception as e:  # noqa: BLE001
        _ready = False
        _error = str(e)
        log.warning(f"index indisponible (Ollama requis) : {e}")


@app.on_event("startup")
def startup():
    build_index()


@app.get("/health")
def health():
    return {"status": "ok" if _ready else "degraded",
            "model": OLLAMA_MODEL, "ready": _ready, "error": _error}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/reindex")
def reindex():
    build_index()
    return {"ready": _ready, "error": _error}


@app.post("/ask")
def ask(body: Question):
    ASK_TOTAL.inc()
    if not _ready:
        # Tentative de reconstruction si Ollama est revenu
        build_index()
    if not _ready:
        return {"answer": "Assistant indisponible : le modele local (Ollama) n'est pas joignable. "
                          "Consultez le runbook docs/runbook-remediation.md.",
                "sources": []}
    try:
        results = _vectorstore.similarity_search(body.question, k=4)
        context = "\n\n".join(f"[{d.metadata.get('source')}]\n{d.page_content}" for d in results)
        sources = sorted({d.metadata.get("source") for d in results})
        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", f"Contexte :\n{context}\n\nQuestion : {body.question}"),
        ]
        resp = _llm.invoke(messages)
        answer = resp.content if hasattr(resp, "content") else str(resp)
        return {"answer": answer, "sources": sources}
    except Exception as e:  # noqa: BLE001
        log.error(f"echec de reponse : {e}")
        return {"answer": "Erreur lors de la generation de la reponse. Consultez le runbook.",
                "sources": []}
