from typing import Optional, Tuple

import numpy as np
import torch
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import FieldCondition, Filter, PointStruct
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import dot_score, semantic_search
from tqdm import tqdm

from thechangelogbot.engine.embeddings import embed_query
from thechangelogbot.engine.snippet import Snippet


def get_most_relevant_snippets_local(
    query: str,
    snippets: list[Snippet],
    embeddings: np.ndarray,
    model: SentenceTransformer,
    top_k: int = 5,
) -> list[Tuple[Snippet, float]]:
    query_embedding = embed_query(query, model=model)

    results = semantic_search(
        torch.from_numpy(query_embedding),
        torch.from_numpy(embeddings),
        score_function=dot_score,
        top_k=top_k,
    )[-1]

    return [(snippets[r.get("corpus_id")], r.get("score")) for r in results]


def qdrant_colletion_init(
    client: QdrantClient,
    collection_name: str,
    distance_model: models.Distance = models.Distance.DOT,
    vector_size: int = 384,
) -> None:
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size, distance=distance_model
        ),
    )


def get_all_ids_in_db(client: QdrantClient, collection_name: str) -> list[str]:
    scroll = client.scroll(
        collection_name=collection_name,
        with_payload=True,
        with_vectors=False,
        limit=5_000_000,
    )

    uploaded_ids = [str(s.id) for s in scroll[0]]

    logger.info(f"Found {len(uploaded_ids)} snippets already in the DB")

    return uploaded_ids


def update_qdrant_collection_with_embeddings(
    client: QdrantClient,
    collection_name: str,
    snippets: list[Snippet],
    batch_size: int = 500,
) -> None:
    points = [
        PointStruct(
            id=s.id,
            vector=s.embedding.tolist(),
            payload={
                "podcast_name": s.podcast_name,
                "episode_number": s.episode_number,
                "text": s.text,
                "speaker": s.speaker,
            },
        )
        for s in snippets
    ]

    logger.info(f"Uploading {len(points)} snippets")

    for i in tqdm(range(0, len(points), batch_size)):
        batch = points[i : i + batch_size]

        client.upsert(collection_name=collection_name, points=batch)

    logger.info("Done.")


def search_qdrant(
    query: str,
    client: QdrantClient,
    collection_name: str,
    model: SentenceTransformer,
    limit: int = 4,
    list_of_filters: Optional[dict[str, str]] = None,
    show_results: bool = False,
) -> list[Snippet]:
    if list_of_filters is not None:
        filtering_fields = [a for a in Snippet.__annotations__.keys()]
        conditions = list()

        for filter_key, filter_value in list_of_filters.items():
            assert (
                filter_key in filtering_fields
            ), f"{filter_key} is not a valid filter field (must be in {filtering_fields})"

            conditions.append(
                FieldCondition(
                    key=filter_key,
                    match=models.MatchText(text=filter_value),
                )
            )

        query_filter = Filter(must=conditions)

    else:
        query_filter = None

    query_vector = embed_query(query, model=model)
    hits = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
    )

    snippets = [Snippet(**hit.payload) for hit in hits]

    if show_results is True:
        for snippet in snippets:
            print(snippet)
            print("------")
    return snippets


def create_db(client: QdrantClient, collection_name: str) -> None:
    qdrant_colletion_init(client, collection_name)
