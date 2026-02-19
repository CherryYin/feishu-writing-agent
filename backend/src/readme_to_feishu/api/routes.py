"""API routes - Architecture 3.0.4."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, File, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from ..models import (
    ConvertRequest,
    ConvertResponse,
    FetchReadmeRequest,
    FetchReadmeResponse,
    TaskListResponse,
    UploadResponse,
)
from ..services.input_layer import save_upload, fetch_readme_from_github
from ..services.run_pipeline import run_task, get_task, list_tasks, _task_store

router = APIRouter(prefix="/api", tags=["api"])
_executor = ThreadPoolExecutor(max_workers=4)


@router.post("/upload", response_model=UploadResponse)
async def api_upload(file: UploadFile = File(...)):
    """Upload README file. Returns file_id and preview_markdown."""
    if not file.filename or not (file.filename.endswith(".md") or file.filename.endswith(".txt")):
        raise HTTPException(400, "File must be .md or .txt")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")
    result = save_upload(text, file.filename or "README.md")
    return UploadResponse(**result)


@router.post("/fetch-readme", response_model=FetchReadmeResponse)
async def api_fetch_readme(body: FetchReadmeRequest):
    """Fetch README from GitHub URL. Returns file_id, preview_markdown, repo_meta."""
    try:
        result = fetch_readme_from_github(body.github_url, body.branch)
        return FetchReadmeResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, str(e))


@router.post("/convert", response_model=ConvertResponse)
async def api_convert(body: ConvertRequest):
    """Start conversion task. Returns task_id immediately. Subscribe to GET /api/tasks/{task_id}/stream for progress."""
    task_id = uuid.uuid4().hex
    _task_store[task_id] = {"status": "running", "events": [], "result": None}
    _executor.submit(
        run_task,
        file_id=body.file_id,
        mode=body.mode,
        target_lang=body.target_lang,
        feishu_folder_token=body.feishu_folder_token,
        feishu_app_id=body.feishu_app_id or "",
        feishu_app_secret=body.feishu_app_secret or "",
        filters=body.filters,
        custom_prompt=body.custom_prompt,
        doc_title=body.doc_title or "README",
        task_id=task_id,
    )
    return ConvertResponse(task_id=task_id)


@router.get("/tasks/{task_id}/stream")
async def api_task_stream(task_id: str):
    """SSE stream for task progress. Events: progress (step, progress), result (feishu_doc_url), error."""
    if not get_task(task_id):
        raise HTTPException(404, "Task not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        import asyncio
        last_index = 0
        while True:
            t = get_task(task_id)
            if not t:
                break
            events = t.get("events", [])
            for ev in events[last_index:]:
                yield f"data: {json.dumps(ev)}\n\n"
            last_index = len(events)
            status = t.get("status", "running")
            if status != "running":
                result = t.get("result")
                if result:
                    yield f"data: {json.dumps({'kind': 'result', 'data': result})}\n\n"
                break
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@router.get("/tasks", response_model=TaskListResponse)
async def api_tasks_list(page: int = 1, size: int = 20):
    """List task history."""
    data = list_tasks(page=page, size=size)
    return TaskListResponse(**data)
