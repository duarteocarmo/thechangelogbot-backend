import os
import time
from functools import cache
from typing import Optional

import sentence_transformers
import superduperdb
from loguru import logger
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from superduperdb.container.document import Document
from superduperdb.container.listener import Listener
from superduperdb.container.model import Model
from superduperdb.container.vector_index import VectorIndex
from superduperdb.db.mongodb.query import Collection
from superduperdb.ext.numpy.array import array
from thechangelogbot.index.snippet import Snippet


def get_mongo_client(
    host: str, port: int, server_api: Optional[str] = None
) -> MongoClient:
    if server_api is not None and "mongodb" in host:
        mongo_password = os.getenv("MONGO_PASSWORD")

        if mongo_password is None:
            raise ValueError("MONGO_PASSWORD is not set")

        host = host.replace("<password>", mongo_password)
        client = MongoClient(host, server_api=ServerApi(server_api))
        client.admin.command("ping")
        logger.info(
            "Pinged your deployment. You successfully connected to MongoDB!"
        )
        return client

    return MongoClient(host=host, port=port)


def get_superduperdb_components(config: dict) -> tuple:
    mongodb_host = config["mongodb"]["host"]
    mongodb_port = config["mongodb"]["port"]
    mongodb_collection = config["mongodb"]["collection"]
    mongodb_server_api = config["mongodb"].get("server_api", None)

    client = get_mongo_client(
        host=mongodb_host, port=mongodb_port, server_api=mongodb_server_api
    )
    db = superduperdb.superduper(client.documents)
    collection = Collection(name=mongodb_collection)

    return db, collection


def prepare_mongo(
    db,
    collection: Collection,
    model_id: str,
    vector_size: int,
    index_id: str,
    key: str,
) -> None:
    # TODO REPLACE THIS
    device = "cpu"
    # device = (
    #     "cuda"
    #     if torch.cuda.is_available()
    #     else "mps"
    #     if torch.backends.mps.is_available()
    #     else "cpu"
    # )

    logger.info(f"Using device {device} for indexing.")

    model = Model(
        identifier=model_id,
        object=sentence_transformers.SentenceTransformer(
            model_id, device=device
        ),
        encoder=array("float32", shape=(vector_size,)),
        predict_method="encode",
        batch_predict=True,
    )

    try:
        db.add(
            VectorIndex(
                identifier=index_id,
                indexing_listener=Listener(
                    model=model,
                    key=key,
                    select=collection.find(),
                ),
            )
        )
    except Exception as e:
        logger.error(e)
        logger.warning("Failed to prepare mongodb.")
        return

    logger.info(db.show("listener"))
    logger.info(db.show("model"))
    logger.info(db.show("vector_index"))
    logger.info("Prepared mongodb.")


def upload_to_mongo(db, collection: Collection, data: list[dict]):
    data = [Document(r) for r in data]
    db.execute(collection.insert_many(data))

    logger.info(f"Uploaded {len(data)} snippets to mongodb")


def get_uploaded_hashes(db, collection: Collection):
    return [
        doc["_hash"] for doc in db.execute(collection.find({}, {"_hash": 1}))
    ]


@cache
def get_speakers(
    database: superduperdb.superduper, collection_name
) -> list[str]:
    collection = Collection(name=collection_name)
    unique_speakers = {
        s["speaker"]
        for s in database.execute(collection.find({}, {"speaker": 1}))
    }
    unique_speakers = [
        speaker for speaker in unique_speakers if len(speaker.split(" ")) == 2
    ]
    unique_speakers.sort()
    return unique_speakers


def search_mongo(
    query: str,
    db,
    index_id: str,
    collection: Collection,
    limit: int = 4,
    list_of_filters: Optional[dict[str, str]] = None,
) -> list[Snippet]:
    q_filter = None

    if list_of_filters is not None:
        filtering_fields = [a for a in Snippet.__annotations__.keys()]
        q_filter = dict()

        for filter_key, filter_value in list_of_filters.items():
            assert (
                filter_key in filtering_fields
            ), f"{filter_key} is not a valid filter field (must be in {filtering_fields})"

            q_filter[filter_key] = {"$regex": filter_value}

    start_time = time.time()
    if q_filter is not None:
        logger.info(f"Filtering by {q_filter}")
        cur = db.execute(
            collection.find(q_filter).like(
                {"text": query}, n=limit, vector_index=index_id
            )
        )
    else:
        cur = db.execute(
            collection.like({"text": query}, n=limit, vector_index=index_id)
        )

    for doc in cur:
        doc_dict = doc.unpack()
        doc_dict = {
            k: v
            for k, v in doc_dict.items()
            if k in Snippet.__annotations__.keys()
        }
        yield Snippet(**doc_dict)

    end_time = time.time()
    logger.info(f"Query took {end_time - start_time} seconds")


def search_database(
    config: dict,
    query: str,
    initialize: bool = True,
    db=None,
    collection: Optional[Collection] = None,
    list_of_filters: Optional[dict[str, str]] = None,
    limit: int = 10,
) -> list[Snippet]:
    index_id = config["mongodb"]["index_id"]

    if initialize is False and db is None:
        raise ValueError("db must be provided if initialize is False")

    if initialize is False and collection is None:
        raise ValueError("client must be provided if initialize is False")

    if initialize is True:
        if db is not None or collection is not None:
            raise ValueError(
                "You are initializing the database, but you already provided db and collection"
            )
        db, collection = get_superduperdb_components(config)

    results = list(
        search_mongo(
            limit=limit,
            query=query,
            db=db,
            index_id=index_id,
            collection=collection,
            list_of_filters=list_of_filters,
        )
    )

    return results
