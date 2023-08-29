import pathlib
import shutil
from dataclasses import asdict

import superduperdb
from git.repo import Repo
from loguru import logger
from superduperdb.db.mongodb.query import Collection
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import (
    get_mongo_client,
    get_uploaded_hashes,
    upload_to_mongo,
)
from thechangelogbot.index.parser import index_snippets


def index(config: dict = config) -> None:
    transcript_repo_directory = config["indexing"]["transcript_repo_directory"]
    transcript_git_url = config["indexing"]["transcript_git_url"]
    podcast_filter = config["indexing"]["podcasts"]

    if pathlib.Path(transcript_repo_directory).is_dir():
        shutil.rmtree(transcript_repo_directory)

    Repo.clone_from(transcript_git_url, transcript_repo_directory)

    snippets = list(
        index_snippets(
            transcript_repo_directory, podcast_filter=podcast_filter
        )
    )
    snippets = list(asdict(s) for s in snippets)

    mongodb_host = config["mongodb"]["host"]
    mongodb_port = config["mongodb"]["port"]
    mongodb_collection = config["mongodb"]["collection"]
    mongodb_server_api = config["mongodb"].get("server_api", None)

    client = get_mongo_client(
        host=mongodb_host, port=mongodb_port, server_api=mongodb_server_api
    )
    db = superduperdb.superduper(client.documents)
    collection = Collection(name=mongodb_collection)

    existing_hashes = get_uploaded_hashes(db=db, collection=collection)
    logger.info(f"Total snippets already in database: {len(existing_hashes)}")

    snippets_to_upload = [
        sn for sn in snippets if sn["_hash"] not in existing_hashes
    ]

    if len(snippets_to_upload) > 0:
        logger.info(f"Uploading {len(snippets_to_upload)} new snippets.")
        upload_to_mongo(db, collection, snippets_to_upload)

    else:
        logger.info("No new snippets to upload.")


if __name__ == "__main__":
    index(config=config)
