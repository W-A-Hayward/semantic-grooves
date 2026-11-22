"""The embedding model, loaded on first use."""
import os

from .config import MODEL_NAME

# BGE retrieval models are trained to embed short queries with this
# instruction in front. Set SG_QUERY_PREFIX="" to disable it.
QUERY_PREFIX = os.environ.get(
    "SG_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
)

_model = None


def resolve_device():
    """The torch device: $SG_DEVICE ("cpu", "cuda", ...) or CUDA/ROCm when available."""
    device = os.environ.get("SG_DEVICE")
    if device:
        return device
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_model():
    """Load the embedding model on first use (keeps imports and tests cheap)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME, device=resolve_device())
    return _model


def embed_query(text):
    """Embed a search query (with the BGE retrieval instruction prefix)."""
    return get_model().encode(
        QUERY_PREFIX + text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
