"""Run README-to-Feishu pipeline: wire tool executors and codergen backend, execute with SSE events."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from ..pipeline import (
    Context,
    Graph,
    Outcome,
    StageStatus,
    PipelineEngine,
    parse_dot,
)
from ..pipeline.handlers import CodergenHandler
from ..pipeline.handlers.tool import ToolExecutor
from ..config import (
    FEISHU_APP_ID as _CFG_APP_ID,
    FEISHU_APP_SECRET as _CFG_APP_SECRET,
    FEISHU_FOLDER_TOKEN as _CFG_FOLDER_TOKEN,
    FEISHU_DOC_BASE_URL as _CFG_DOC_BASE_URL,
    OPENAI_API_KEY as _CFG_OPENAI_KEY,
)
from .input_layer import get_upload
from .markdown_parser import parse_markdown_to_ast
from .block_converter import build_feishu_blocks_schema
from .html_parser import parse_html_to_ast
from .llm_blog_rewrite import rewrite_readme_to_blog_html
from .feishu_client import (
    get_tenant_access_token,
    create_document,
    get_document,
    get_root_block_id,
    append_document_blocks,
)

# In-memory task store for status and result
_task_store: dict[str, dict[str, Any]] = {}
BATCH_SIZE = 50


def _append_with_isolation(token: str, document_id: str, root_id: str, blocks: list[dict[str, Any]]) -> None:
    """Append blocks. If Feishu rejects a batch with invalid params, isolate the offending block."""
    # Try normal batching first
    for i in range(0, len(blocks), BATCH_SIZE):
        batch = blocks[i : i + BATCH_SIZE]
        try:
            append_document_blocks(token, document_id, root_id, batch, index=None)
        except Exception as e:
            # If we see invalid param, isolate by trying smaller batches down to single block.
            msg = str(e)
            if "invalid param" not in msg and "1770001" not in msg:
                raise
            _isolate_and_raise(token, document_id, root_id, batch, prefix=f"batch_offset={i}")  # noqa: F821


def _isolate_and_raise(token: str, document_id: str, root_id: str, blocks: list[dict[str, Any]], prefix: str = "") -> None:
    if not blocks:
        raise RuntimeError(f"{prefix} invalid param but empty batch")
    if len(blocks) == 1:
        # Re-raise with the exact offending block payload
        import json

        raise RuntimeError(
            f"{prefix} Feishu rejected a single block (invalid param). offending_block={json.dumps(blocks[0], ensure_ascii=False)[:4000]}"
        )
    mid = len(blocks) // 2
    left = blocks[:mid]
    right = blocks[mid:]
    try:
        append_document_blocks(token, document_id, root_id, left, index=None)
    except Exception:
        _isolate_and_raise(token, document_id, root_id, left, prefix=prefix + " left")
        return
    try:
        append_document_blocks(token, document_id, root_id, right, index=None)
    except Exception:
        _isolate_and_raise(token, document_id, root_id, right, prefix=prefix + " right")
        return


def _tool_fetch_input(
    _name: str,
    node: Any,
    context: Any,
    _graph: Any,
    logs_root: Path,
) -> Outcome:
    file_id = context.get("file_id")
    if not file_id:
        return Outcome(status=StageStatus.FAIL, failure_reason="Missing file_id in context")
    upload = get_upload(file_id)
    if not upload:
        return Outcome(status=StageStatus.FAIL, failure_reason=f"Upload not found: {file_id}")
    content = upload.get("content", "")
    context.set("input.markdown", content)
    context.set("input.filename", upload.get("filename", "README.md"))
    return Outcome(
        status=StageStatus.SUCCESS,
        context_updates={"input.markdown": content, "input.filename": upload.get("filename", "README.md")},
        notes="Fetched input",
    )


def _tool_parse_markdown(
    _name: str,
    node: Any,
    context: Any,
    _graph: Any,
    logs_root: Path,
) -> Outcome:
    content = context.get_string("input.markdown")
    if not content:
        return Outcome(status=StageStatus.FAIL, failure_reason="No input.markdown in context")
    ast = parse_markdown_to_ast(content)
    context.set("ast", ast)
    return Outcome(status=StageStatus.SUCCESS, context_updates={"ast": ast}, notes=f"Parsed {len(ast)} blocks")


def _tool_convert_to_blocks(
    _name: str,
    node: Any,
    context: Any,
    _graph: Any,
    logs_root: Path,
) -> Outcome:
    mode = context.get_string("mode") or "lightweight"
    # When mode=rewrite and LLM is configured, rewrite README as blog-style HTML then convert HTML→blocks
    if mode == "rewrite" and _CFG_OPENAI_KEY:
        content = context.get_string("input.markdown")
        if not content:
            return Outcome(status=StageStatus.FAIL, failure_reason="No input.markdown for rewrite")
        try:
            html = rewrite_readme_to_blog_html(content)
            ast = parse_html_to_ast(html)
        except ValueError as e:
            return Outcome(status=StageStatus.FAIL, failure_reason=str(e))
        except Exception as e:
            return Outcome(status=StageStatus.FAIL, failure_reason=f"LLM blog rewrite failed: {e}")
    else:
        ast = context.get("ast")
        if not ast:
            return Outcome(status=StageStatus.FAIL, failure_reason="No ast in context")
    filters_str = context.get_string("filters")
    filters = set()
    if filters_str:
        try:
            filters = set(json.loads(filters_str)) if filters_str.startswith("[") else set(filters_str.split(","))
        except Exception:
            pass
    blocks = build_feishu_blocks_schema(ast, filters=filters or None)
    context.set("feishu_blocks", blocks)
    return Outcome(status=StageStatus.SUCCESS, context_updates={"feishu_blocks": blocks}, notes=f"Built {len(blocks)} blocks")


def _tool_publish_to_feishu(
    _name: str,
    node: Any,
    context: Any,
    _graph: Any,
    logs_root: Path,
) -> Outcome:
    blocks = context.get("feishu_blocks", None)
    # If the key is missing, the convert step likely failed or was skipped.
    # An empty list is valid (it would publish an empty doc).
    if blocks is None:
        return Outcome(status=StageStatus.FAIL, failure_reason="No feishu_blocks in context")
    app_id = context.get_string("feishu_app_id") or _CFG_APP_ID
    app_secret = context.get_string("feishu_app_secret") or _CFG_APP_SECRET
    if not app_id or not app_secret:
        return Outcome(status=StageStatus.FAIL, failure_reason="Missing feishu_app_id or feishu_app_secret (set in request or .env)")
    title = context.get_string("doc_title") or "README"
    folder_token = context.get_string("feishu_folder_token") or _CFG_FOLDER_TOKEN
    try:
        token = get_tenant_access_token(app_id, app_secret)
        doc_data = create_document(token, folder_token=folder_token, title=title)
        document_id = doc_data.get("document_id") or (doc_data.get("document") or {}).get("document_id")
        if not document_id:
            return Outcome(status=StageStatus.FAIL, failure_reason="No document_id in create response")
        root_id = get_root_block_id(token, document_id)
        _append_with_isolation(token, document_id, root_id, blocks)
        # Try to get a real web URL for the document.
        url = ""
        try:
            meta = get_document(token, document_id)
            url = (
                meta.get("url")
                or meta.get("document_url")
                or (meta.get("document") or {}).get("url")
                or (meta.get("document") or {}).get("document_url")
                or ""
            )
        except Exception:
            url = ""

        # If Feishu doesn't provide a URL, construct one from tenant domain.
        # NOTE: This MUST be your tenant domain (e.g. https://xxx.feishu.cn), not open.feishu.cn.
        if not url:
            base = context.get_string("feishu_doc_base_url") or _CFG_DOC_BASE_URL or "https://zcnjr028kg08.feishu.cn"
            if base:
                url = f"{base.rstrip('/')}/docx/{document_id}"
            else:
                # Fallback: keep a non-clickable scheme but correct token; callers should configure base URL.
                url = f"docx://{document_id}"
        context.set("feishu_doc_url", url)
        context.set("feishu_document_id", document_id)
        return Outcome(
            status=StageStatus.SUCCESS,
            context_updates={"feishu_doc_url": url, "feishu_document_id": document_id},
            notes=f"Published: {url}",
        )
    except Exception as e:
        return Outcome(status=StageStatus.FAIL, failure_reason=str(e))


def _default_codergen_backend(node: Any, prompt: str, context: Any) -> str:
    """Default: no LLM; return a static suggestion so pipeline can continue."""
    return json.dumps({
        "keep_sections": ["all"],
        "remove_sections": [],
        "translate": False,
        "filters": [],
    }, ensure_ascii=False)


def create_engine(
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    codergen_backend: Callable[[Any, str, Any], str] | None = None,
) -> tuple[PipelineEngine, Graph]:
    """Build pipeline engine with README-to-Feishu tool executors and optional LLM backend."""
    pipeline_path = Path(__file__).resolve().parent.parent / "pipelines" / "readme_to_feishu.dot"
    graph = parse_dot(pipeline_path)
    tool_executors: dict[str, ToolExecutor] = {
        "fetch_input": _tool_fetch_input,
        "parse_markdown": _tool_parse_markdown,
        "convert_to_blocks": _tool_convert_to_blocks,
        "publish_to_feishu": _tool_publish_to_feishu,
    }
    codergen = CodergenHandler(backend=codergen_backend or _default_codergen_backend)
    engine = PipelineEngine(
        codergen_backend=codergen,
        tool_executors=tool_executors,
        on_event=on_event,
    )
    return engine, graph


def run_task(
    file_id: str,
    mode: str = "lightweight",
    target_lang: str = "keep",
    feishu_space_id: str | None = None,
    feishu_app_id: str = "",
    feishu_app_secret: str = "",
    feishu_folder_token: str | None = None,
    filters: list[str] | None = None,
    custom_prompt: str | None = None,
    doc_title: str = "README",
    task_id: str | None = None,
) -> str:
    """Run a conversion task. If task_id is provided, use it and append events to that task's store."""
    task_id = task_id or str(uuid.uuid4())
    events: list[dict[str, Any]] = []
    step_progress = {"parsing": 25, "understanding": 50, "converting": 75, "publishing": 100}
    step_names = {"fetch_input": "parsing", "parse": "parsing", "understand": "understanding", "convert": "converting", "publish": "publishing"}

    def on_event(kind: str, data: dict[str, Any]) -> None:
        events.append({"kind": kind, "data": data})
        node_id = data.get("node_id", "")
        step = step_names.get(node_id)
        if step:
            events.append({"kind": "progress", "data": {"step": step, "progress": step_progress.get(step, 0)}})
        if task_id in _task_store:
            _task_store[task_id]["events"] = list(events)

    _task_store[task_id] = {"status": "running", "events": events, "result": None}
    ctx = Context()
    ctx.set("file_id", file_id)
    ctx.set("mode", mode)
    ctx.set("target_lang", target_lang)
    ctx.set("filters", json.dumps(filters or []))
    ctx.set("doc_title", doc_title)
    ctx.set("feishu_app_id", feishu_app_id or _CFG_APP_ID)
    ctx.set("feishu_app_secret", feishu_app_secret or _CFG_APP_SECRET)
    if feishu_folder_token or _CFG_FOLDER_TOKEN:
        ctx.set("feishu_folder_token", feishu_folder_token or _CFG_FOLDER_TOKEN)
    if _CFG_DOC_BASE_URL:
        ctx.set("feishu_doc_base_url", _CFG_DOC_BASE_URL)
    if custom_prompt:
        ctx.set("custom_prompt", custom_prompt)
    engine, graph = create_engine(on_event=on_event)
    logs_root = Path("/tmp") / "readme_feishu" / task_id
    logs_root.mkdir(parents=True, exist_ok=True)
    try:
        outcome = engine.run(graph, context=ctx, logs_root=logs_root)
        result = {
            "feishu_doc_url": ctx.get_string("feishu_doc_url"),
            "feishu_document_id": ctx.get_string("feishu_document_id"),
            "status": "success" if outcome.status == StageStatus.SUCCESS else "failed",
            "failure_reason": outcome.failure_reason,
        }
        _task_store[task_id]["result"] = result
        _task_store[task_id]["status"] = "completed"
        events.append({"kind": "progress", "data": {"step": "publishing", "progress": 100, "result": result}})
    except Exception as e:
        _task_store[task_id]["status"] = "failed"
        _task_store[task_id]["result"] = {"status": "failed", "failure_reason": str(e)}
        events.append({"kind": "error", "data": {"message": str(e)}})
    return task_id


def get_task(task_id: str) -> dict[str, Any] | None:
    return _task_store.get(task_id)


def list_tasks(page: int = 1, size: int = 20) -> dict[str, Any]:
    items = list(_task_store.items())
    items.reverse()
    total = len(items)
    start = (page - 1) * size
    end = start + size
    tasks = []
    for tid, data in items[start:end]:
        row = {"task_id": tid, "status": data.get("status", "unknown")}
        result = data.get("result")
        if result:
            row["feishu_doc_url"] = result.get("feishu_doc_url")
            row["failure_reason"] = result.get("failure_reason")
        tasks.append(row)
    return {"tasks": tasks, "total": total}
