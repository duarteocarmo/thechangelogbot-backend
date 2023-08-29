from typing import Optional

import pkg_resources
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
