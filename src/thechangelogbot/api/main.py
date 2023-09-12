import time
from typing import Optional

import pkg_resources
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel
from ratelimiter import RateLimiter
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.chat import respond_to_query
from thechangelogbot.index.database import (
    get_speakers,
    get_superduperdb_components,
    search_database,
)

DATABASE, COLLECTION = get_superduperdb_components(config)
RATE_LIMIT_CALLS, RATE_LIMIT_SECONDS = 10, 60

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


def limited(until):
    duration = int(round(until - time.time()))
    logger.info(f"Sleeping for {duration:.2f} seconds")
    raise HTTPException(
        status_code=429,
        detail=f"Rate limited, sleeping for {duration:.2f} seconds",
    )


rate_limiter_search = RateLimiter(
    max_calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_SECONDS, callback=limited
)
rate_limiter_chat = RateLimiter(
    max_calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_SECONDS, callback=limited
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
    with rate_limiter_search:
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
    return get_speakers(
        database=DATABASE, collection_name=config["mongodb"]["collection"]
    )


@app.post("/chat")
def chat(request: ChatRequest):
    with rate_limiter_chat:
        logger.info(f"Query: {request}")
        return StreamingResponse(
            respond_to_query(
                query=request.query,
                speaker=request.speaker,
                db=DATABASE,
                config=config,
                collection=COLLECTION,
            ),
            media_type="text/plain",
        )
