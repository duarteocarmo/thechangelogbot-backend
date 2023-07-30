import pkg_resources
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from thechangelogbot.engine.main import hello_world

app = FastAPI(
    title="Changelogbot API",
    version=pkg_resources.get_distribution("thechangelogbot").version,
)


@app.get("/")
async def root():
    return RedirectResponse("/docs")


@app.post(
    "/hello",
)
async def hello():
    return hello_world()
