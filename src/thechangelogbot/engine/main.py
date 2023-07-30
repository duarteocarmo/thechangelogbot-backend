import pathlib
import shutil
from typing import Optional

import numpy as np
from git.repo import Repo
from loguru import logger
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from thechangelogbot.engine.database import (
    get_all_ids_in_db,
    search_qdrant,
    update_qdrant_collection_with_embeddings,
)
from thechangelogbot.engine.embeddings import embed_snippets
from thechangelogbot.engine.parser import index_snippets
from thechangelogbot.engine.snippet import Snippet

qdrant_client = QdrantClient(path="qdrant_database")
qdrant_collection_name = "thechangelogbot"
model_name = "intfloat/e5-small-v2"
model = SentenceTransformer(model_name, device="mps")


def search(
    query_string: str, filters: Optional[dict[str, str]] = None
) -> list[Snippet]:
    return search_qdrant(
        query=query_string,
        client=qdrant_client,
        collection_name=qdrant_collection_name,
        model=model,
        list_of_filters=filters,
    )
    # results = get_most_relevant_snippets_local(
    #     query="What is K-nearest neighbors?",
    #     snippets=snippets,
    #     embeddings=embeddings,
    #     model=model,
    # )
    # logger.info("Finished search.")


def index() -> None:
    transcript_repo_directory = "./transcripts"
    transcript_git_url = "https://github.com/thechangelog/transcripts"
    podcast_filter = [
        # "backstage",
        # "founderstalk",
        # "friends",
        # "gotime",
        # "news",
        "podcast",
        # "practicalai",
        # "shipit",
        # "afk",
        # "bigtent",
        # "brainscience",
        # "jsparty",
        # "rfc",
        # "spotlight",
    ]

    if pathlib.Path(transcript_repo_directory).is_dir():
        shutil.rmtree(transcript_repo_directory)

    Repo.clone_from(transcript_git_url, transcript_repo_directory)

    snippets = list(
        index_snippets(
            transcript_repo_directory, podcast_filter=podcast_filter
        )
    )
    logger.info(f"Indexed {len(snippets)} snippets")

    already_in_db = get_all_ids_in_db(
        client=qdrant_client, collection_name=qdrant_collection_name
    )
    snippets = [s for s in snippets if s.id not in already_in_db]
    logger.info(f"Embedding {len(snippets)} snippets")

    if len(snippets) == 0:
        logger.info("No new snippets to upload.")
        return

    embeddings = np.asarray(list(embed_snippets(snippets, model=model)))
    for s, e in zip(snippets, embeddings):
        s.embedding = e
    logger.info("Embedded.")

    update_qdrant_collection_with_embeddings(
        qdrant_client, qdrant_collection_name, snippets
    )
    logger.info("Uploaded.")


if __name__ == "__main__":
    # create_db(client=qdrant_client, collection_name=qdrant_collection_name)
    index()
    search(
        "What's the best programming language?",
        filters={
            "podcast_name": "podcast",
            "speaker": "Adam Stacoviak",
        },
    )
