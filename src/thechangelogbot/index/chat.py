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
        f"Your name is {speaker}. Your goal is answer a specific question from a user from your perspective."
        "You will be given some context of things you have said in the past related to the question."
        "Answer the question using information in the context. Your answer should be 100 words or less."
        "If nothing in the context is related to the question, then respond with 'I'm not sure', followed "
        "by a short summary of the context that is related to the question."
    )
    context_string = "\n".join([snippet._as_context() for snippet in context])
    user_prompt = f"CONTEXT\n---------\n{context_string}\n\nQUESTION\n--------\n{question}"

    response = openai.ChatCompletion.create(
        model=model,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=250,
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
    limit: int = 3,
) -> Generator[str, None, None]:
    logger.info("Starting to yield...")

    index_id = config["mongodb"]["index_id"]
    list_of_filters = {"speaker": speaker}

    results = list(
        search_mongo(
            limit=limit,
            query=query,
            query_prefix=config["model"]["prefix"].get("querying", None),
            db=db,
            index_id=index_id,
            collection=collection,
            list_of_filters=list_of_filters,
        )
    )

    breakpoint()

    yield from get_person_response(
        question=query, context=results, speaker=speaker
    )
