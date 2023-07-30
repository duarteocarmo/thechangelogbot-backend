from typing import Optional

import pkg_resources
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from thechangelogbot.engine.main import search

app = FastAPI(
    title="Changelogbot API",
    version=pkg_resources.get_distribution("thechangelogbot").version,
)


@app.get("/")
async def root():
    return RedirectResponse("/docs")


class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict[str, str]] = None

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


@app.get("/search")
def search_endpoint(request: SearchRequest):
    return search(query_string=request.query, filters=request.filters)
