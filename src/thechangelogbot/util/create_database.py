import superduperdb
from loguru import logger
from superduperdb.db.mongodb.query import Collection
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import get_mongo_client, prepare_mongo


def prepare_database(config: dict = config) -> None:
    logger.info("Preparing mongodb.")

    mongodb_host = config["mongodb"]["host"]
    mongodb_port = config["mongodb"]["port"]
    mongodb_collection = config["mongodb"]["collection"]
    mongodb_server_api = config["mongodb"].get("server_api", None)
    index_id = config["mongodb"]["index_id"]
    model_id = config["model"]["name"]
    vector_size = config["model"]["vector_size"]

    client = get_mongo_client(
        host=mongodb_host, port=mongodb_port, server_api=mongodb_server_api
    )

    if input("This will drop existing collections, continue? (y/n)") != "y":
        return

    for db_name in client.list_database_names():
        for collection_name in client[db_name].list_collection_names():
            client[db_name].drop_collection(collection_name)
            logger.info(f"Dropped collection {collection_name}")

    db = superduperdb.superduper(client.documents)
    collection = Collection(name=mongodb_collection)

    prepare_mongo(
        db,
        collection=collection,
        model_id=model_id,
        vector_size=vector_size,
        index_id=index_id,
        key="text",
    )
    logger.info("Prepared mongodb.")


if __name__ == "__main__":
    prepare_database(config=config)
