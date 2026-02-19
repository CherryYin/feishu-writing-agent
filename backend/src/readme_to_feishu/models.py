"""Pydantic models for API request/response."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    file_id: str
    preview_markdown: str


class FetchReadmeRequest(BaseModel):
    github_url: str
    branch: str | None = None


class FetchReadmeResponse(BaseModel):
    file_id: str
    preview_markdown: str
    repo_meta: dict = Field(default_factory=dict)


class ConvertRequest(BaseModel):
    file_id: str
    mode: Literal["lightweight", "rewrite"] = "lightweight"
    target_lang: Literal["keep", "zh", "en"] = "keep"
    feishu_space_id: str | None = None
    feishu_folder_token: str | None = None
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    filters: list[str] = Field(default_factory=list)
    custom_prompt: str | None = None
    doc_title: str = "README"


class ConvertResponse(BaseModel):
    task_id: str


class TaskListItem(BaseModel):
    task_id: str
    status: str
    feishu_doc_url: str | None = None
    failure_reason: str | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskListItem]
    total: int
