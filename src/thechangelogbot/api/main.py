from typing import Optional

import pkg_resources
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import (
    fetch_qdrant_client_from_config,
    get_all_podcasts,
    search_qdrant,
)

QDRANT_CLIENT_STR = config["qdrant"]["client_str"]
QDRANT_CLIENT = fetch_qdrant_client_from_config(QDRANT_CLIENT_STR)
MODEL = SentenceTransformer(config["model"]["name"], device="mps")


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
async def root():
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
    return search_qdrant(
        query=request.query,
        client=QDRANT_CLIENT,
        collection_name=config["qdrant"]["collection_name"],
        model=MODEL,
        limit=request.limit,
        list_of_filters=request.filters,
        prefix=config["model"]["prefix"]["querying"],
    )


@app.get("/podcasts")
async def podcasts():
    return get_all_podcasts(
        client=QDRANT_CLIENT,
        collection_name=config["qdrant"]["collection_name"],
    )
