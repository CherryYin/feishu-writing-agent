"""FastAPI application entry - README to Feishu Agent."""

from . import config  # noqa: F401 - load .env on startup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI(
    title="README to Feishu Agent",
    description="Convert GitHub README (Markdown) to Feishu documents",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
async def root():
    return {"service": "readme-to-feishu-agent", "docs": "/docs"}
