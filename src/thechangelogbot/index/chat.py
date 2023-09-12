import os
from typing import Generator

import openai
from loguru import logger
from superduperdb.db.mongodb.query import Collection
from tenacity import retry, stop_after_attempt, wait_random_exponential
from thechangelogbot.index.database import search_mongo
from thechangelogbot.index.snippet import Snippet

openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    raise ValueError("OPENAI_API_KEY is not set")


@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def get_person_response(
    question: str,
    context: list[Snippet],
    speaker: str,
    model: str = "gpt-3.5-turbo",
) -> Generator[str, None, None]:
    system_prompt = (
        f"Your name is {speaker}. Your goal is to answer a specific user question."
        " You will be given some context related to the question. This context are snippets of things you have said in the past."
        " Answer the question using the context, and use the same tone as the context. Your answer should be 100 words or less."
    )
    context_string = "\n".join([snippet.text for snippet in context])
    user_prompt = f"CONTEXT\n---------\n{context_string}\n\nQUESTION\n--------\n{question}"

    response = openai.ChatCompletion.create(
        model=model,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=300,
    )

    for chunk in response:
        text = chunk["choices"][-1]["delta"].get("content", None)
        if text:
            yield text


def respond_to_query(
    query: str,
    speaker: str,
    db,
    collection: Collection,
    config: dict,
    limit: int = 4,
) -> Generator[str, None, None]:
    logger.info("Starting to yield...")

    index_id = config["mongodb"]["index_id"]
    list_of_filters = {"speaker": speaker}

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

    yield from get_person_response(
        question=query, context=results, speaker=speaker
    )
