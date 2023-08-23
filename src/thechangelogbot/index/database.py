from typing import Optional

import sentence_transformers
from loguru import logger
from pymongo import MongoClient
from superduperdb.container.document import Document
from superduperdb.container.listener import Listener
from superduperdb.container.model import Model
from superduperdb.container.vector_index import VectorIndex
from superduperdb.db.mongodb.query import Collection
from superduperdb.ext.numpy.array import array
from thechangelogbot.index.snippet import Snippet


def get_mongo_client(host: str, port: int) -> MongoClient:
    return MongoClient(host=host, port=port)


def prepare_mongo(
    db,
    collection: Collection,
    model_id: str,
    vector_size: int,
    index_id: str,
    key: str,
    device: str = "cpu",
) -> None:
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
