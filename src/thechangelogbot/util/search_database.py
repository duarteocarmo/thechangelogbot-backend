import superduperdb
from superduperdb.db.mongodb.query import Collection
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import get_mongo_client, search_mongo


def search_database(config: dict, query: str) -> None:
    mongodb_host = config["mongodb"]["host"]
    mongodb_port = config["mongodb"]["port"]
    mongodb_collection = config["mongodb"]["collection"]
    index_id = config["mongodb"]["index_id"]

    client = get_mongo_client(host=mongodb_host, port=mongodb_port)
    db = superduperdb.superduper(client.documents)
    collection = Collection(name=mongodb_collection)

    results = list(
        search_mongo(
            limit=10,
            query=query,
            db=db,
            index_id=index_id,
            collection=collection,
            list_of_filters={
                "podcast": "brainscience",
                "speaker": "Danielle",
            },
        )
    )

    for result in results:
        print(result)
        print()


if __name__ == "__main__":
    search_database(config=config, query="How are you feeling?")
