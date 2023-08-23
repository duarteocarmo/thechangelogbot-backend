from typing import Any, Iterator

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def embed_query(
    query: str,
    model: SentenceTransformer,
    prefix: str,
    normalize_embeddings: bool = True,
) -> np.ndarray:
    query_text_with_prefix = [f"{prefix}{query}"]

    return model.encode(
        query_text_with_prefix,
        normalize_embeddings=normalize_embeddings,
    )[-1]


def embed_snippets(
    snippets: list,
    model: SentenceTransformer,
    prefix: str,
    batch_size: int = 700,
    normalize_embeddings: bool = True,
) -> Iterator[np.ndarray | Any]:
    input_texts = [f"{prefix} {snippet.text}" for snippet in snippets]

    for i in tqdm(range(0, len(input_texts), batch_size)):
        batch = input_texts[i : i + batch_size]
        batch_embeddings = model.encode(
            batch,
            normalize_embeddings=normalize_embeddings,
        )
        yield from batch_embeddings
