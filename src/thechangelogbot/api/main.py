import time
from typing import Optional

import pkg_resources
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import (
    get_superduperdb_components,
    search_database,
)

DATABASE, COLLECTION = get_superduperdb_components(config)


app = FastAPI(
    title="Changelogbot API",
    version=pkg_resources.get_distribution("thechangelogbot").version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config["api"]["origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return RedirectResponse("/docs")


class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict[str, str]] = None
    limit: int = 10

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "what are embeddings?",
                    "filters": {"speaker": "Adam Stacoviak"},
                }
            ]
        }
    }


@app.post("/search")
def search_endpoint(request: SearchRequest):
    return search_database(
        config=config,
        query=request.query,
        list_of_filters=request.filters,
        limit=request.limit,
        db=DATABASE,
        collection=COLLECTION,
        initialize=False,
    )


@app.get("/podcasts")
def podcasts():
    return config["indexing"]["podcasts"]


class ChatRequest(BaseModel):
    query: str
    speaker: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What is the best model I should use?",
                    "speaker": "Adam Stacoviak",
                }
            ]
        }
    }


@app.get("/speakers")
def speakers():
    return ["Adam Stacoviak", "Benjamin Dreyer"]


def fake_chat_streamer(query: str, speaker: str):
    logger.info("Starting to yield...")
    example_response = f"{speaker}: {query}" * 2
    for word in example_response.split(" "):
        to_yield = word + " "
        yield to_yield
        logger.info(to_yield)
        time.sleep(0.3)
    logger.info("Finished!")


@app.post("/chat")
def chat(request: ChatRequest):
    logger.info(f"Query: {request}")
    return StreamingResponse(
        fake_chat_streamer(query=request.query, speaker=request.speaker),
        media_type="text/plain",
    )
