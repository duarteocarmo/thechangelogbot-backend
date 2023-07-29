import pathlib
import re
import shutil
from dataclasses import dataclass, field
from hashlib import md5
from typing import Any, Iterator, Optional, Tuple

import numpy as np
import torch
from git.repo import Repo
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import FieldCondition, Filter, PointStruct
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import dot_score, semantic_search
from tqdm import tqdm

qdrant_client = QdrantClient(path="qdrant_database")
qdrant_collection_name = "thechangelogbot"
model_name = "intfloat/e5-small-v2"
model = SentenceTransformer(model_name, device="mps")


@dataclass
class Snippet:
    podcast_name: str
    episode_number: int
    text: str
    speaker: str
    id: str = field(init=False)
    num_words: int = field(init=False)
    embedding: Optional[np.ndarray] = field(init=False, default=None)

    def __post_init__(self):
        self.id = md5(
            f"{self.podcast_name}{self.episode_number}{self.text}{self.speaker}".encode(
                "utf-8"
            )
        ).hexdigest()

        self.text = clean_text(self.text)
        self.num_words = len(self.text.split())


def parse_episode_text(
    episode_text: str,
    episode_number: int,
    podcast_name: str,
) -> list[Snippet]:
    text = ""
    speaking_items = []
    last_speaker = None

    for line in episode_text.splitlines():
        if not line:
            continue

        speaker_match = re.match(r"^\*\*(.+?):\*\*", line)

        if speaker_match:
            if last_speaker and text:
                speaking_items.append(
                    Snippet(
                        podcast_name=podcast_name,
                        episode_number=episode_number,
                        text=text.strip(),
                        speaker=last_speaker,
                    )
                )

            speaker = speaker_match.group(1)
            text = line.replace(f"**{speaker}:** ", "")
            last_speaker = speaker

        else:
            text += " " + line

    if last_speaker and text:
        speaking_items.append(
            Snippet(
                podcast_name=podcast_name,
                episode_number=episode_number,
                text=text.strip(),
                speaker=last_speaker,
            )
        )

    speaking_items = list(filter_items(speaking_items))

    return speaking_items


def clean_text(text: str) -> str:
    text = re.sub(r"\\\[\d{1,2}:\d{1,2}\\\]\s", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def filter_items(
    items: list[Snippet], num_words: int = 25
) -> Iterator[Snippet]:
    for snippet in items:
        if snippet.speaker == "Break":
            continue

        elif snippet.num_words < num_words:
            continue
        else:
            yield snippet


def process_podcast_directory(
    directory: pathlib.Path,
) -> Iterator[list[Snippet]]:
    for file in pathlib.Path(directory).iterdir():
        try:
            episode_number = int(file.stem.split("-")[-1])
            episode_text = file.read_text()

            yield parse_episode_text(
                episode_text=episode_text,
                episode_number=episode_number,
                podcast_name=directory.name,
            )

        except Exception as e:
            logger.error(f"Error processing {file.name}: {e}")


def index_snippets(
    transcript_repo_directory: str,
    podcast_filter: Optional[list[str]] = None,
    directories_to_ignore: list[str] = [".github", ".git", "scripts"],
) -> Iterator[Snippet]:
    for directory in pathlib.Path(transcript_repo_directory).iterdir():
        if not directory.is_dir() or directory.name in directories_to_ignore:
            continue

        if podcast_filter and directory.name not in podcast_filter:
            continue

        podcast_name = directory.name
        logger.info(f"Processing podcast {podcast_name}...")

        for items in list(
            process_podcast_directory(
                directory=directory,
            )
        ):
            yield from items


def embed_snippets(
    snippets: list,
    model: SentenceTransformer,
    batch_size: int = 700,
    normalize_embeddings: bool = True,
    prefix: str = "passage: ",
) -> Iterator[np.ndarray | Any]:
    input_texts = [f"{prefix} {snippet.text}" for snippet in snippets]

    for i in tqdm(range(0, len(input_texts), batch_size)):
        batch = input_texts[i : i + batch_size]
        batch_embeddings = model.encode(
            batch,
            normalize_embeddings=normalize_embeddings,
        )
        yield from batch_embeddings


def embed_query(
    query: str,
    model: SentenceTransformer,
    prefix: str = "query: ",
    normalize_embeddings: bool = True,
) -> np.ndarray:
    query_text_with_prefix = [f"{prefix}{query}"]

    return model.encode(
        query_text_with_prefix,
        normalize_embeddings=normalize_embeddings,
    )[-1]


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


def search(
    query_string: str, filters: Optional[dict[str, str]] = None
) -> None:
    search_qdrant(
        query=query_string,
        client=qdrant_client,
        collection_name=qdrant_collection_name,
        model=model,
        show_results=True,
        list_of_filters=filters,
    )
    # results = get_most_relevant_snippets_local(
    #     query="What is K-nearest neighbors?",
    #     snippets=snippets,
    #     embeddings=embeddings,
    #     model=model,
    # )
    # logger.info("Finished search.")


def create_db() -> None:
    qdrant_colletion_init(qdrant_client, qdrant_collection_name)


def index() -> None:
    transcript_repo_directory = "./transcripts"
    transcript_git_url = "https://github.com/thechangelog/transcripts"
    podcast_filter = [
        "backstage",
        "founderstalk",
        "friends",
        "gotime",
        "news",
        "podcast",
        "practicalai",
        "shipit",
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
    # create_db()
    index()
    # search(
    #     "What's the best programming language?",
    #     filters={
    #         "podcast_name": "podcast",
    #         "speaker": "Adam Stacoviak",
    #     },
    # )
