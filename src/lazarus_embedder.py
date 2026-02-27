import json
import os
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Protocol


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> List[float]: ...


def _http_json(url: str, payload: dict, timeout_s: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


@dataclass
class OllamaEmbedder:
    base_url: str
    model: str
    timeout_s: int = 60
    dim: int = 0

    def embed(self, text: str) -> List[float]:
        url = f"{self.base_url.rstrip('/')}/api/embeddings"
        # Avoid absurd payload sizes; embeddings work fine on truncated context.
        prompt = text.strip()
        if len(prompt) > 8000:
            prompt = prompt[:8000]
        obj = _http_json(url, payload={"model": self.model, "prompt": prompt}, timeout_s=self.timeout_s)
        vec = obj.get("embedding") or []
        if not isinstance(vec, list) or not vec:
            raise RuntimeError("ollama embeddings returned empty vector")
        if not self.dim:
            self.dim = len(vec)
        return [float(x) for x in vec]


@dataclass
class SentenceTransformersEmbedder:
    model_name: str = "all-MiniLM-L6-v2"
    dim: int = 384

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(self.model_name)

    def embed(self, text: str) -> List[float]:
        return self._model.encode(text).tolist()


def build_embedder() -> Embedder:
    """
    Select an embedding backend.
    - Prefer sentence-transformers only when installed or explicitly requested.
    - Default to Ollama embeddings (fast to set up on Mac Studio; no torch).
    """
    backend = os.getenv("LAZARUS_EMBED_BACKEND", "auto").strip().lower()

    if backend in {"st", "sentence-transformers", "sentencetransformers"}:
        return SentenceTransformersEmbedder()

    if backend in {"ollama", "auto"}:
        base_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        model = os.getenv("LAZARUS_OLLAMA_EMBED_MODEL", "qwen2.5:3b")
        try:
            return OllamaEmbedder(base_url=base_url, model=model)
        except Exception:
            if backend == "ollama":
                raise

    # Auto fallback: try sentence-transformers last.
    return SentenceTransformersEmbedder()

