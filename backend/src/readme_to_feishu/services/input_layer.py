"""Input layer: local file upload and GitHub README fetch - Architecture 3.1."""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

# Default storage for uploaded files:
# - in-memory for fast path
# - persisted on disk so `convert` still works after server reload/restart
_upload_store: dict[str, dict[str, Any]] = {}

_BACKEND_DIR = Path(__file__).resolve().parents[3]  # backend/
_DEFAULT_DATA_DIR = _BACKEND_DIR / ".data"
_DATA_DIR = Path(os.environ.get("README_TO_FEISHU_DATA_DIR", str(_DEFAULT_DATA_DIR)))
_UPLOAD_DIR = _DATA_DIR / "uploads"


def _persist_upload(file_id: str, record: dict[str, Any]) -> None:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = _UPLOAD_DIR / f"{file_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def _load_upload_from_disk(file_id: str) -> dict[str, Any] | None:
    path = _UPLOAD_DIR / f"{file_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_upload(content: str | bytes, filename: str = "README.md") -> dict[str, Any]:
    """Store uploaded content and return file_id and preview_markdown."""
    file_id = str(uuid.uuid4())
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("utf-8", errors="replace")
    preview = content[:5000] + ("..." if len(content) > 5000 else "")
    record = {
        "content": content,
        "filename": filename,
        "preview_markdown": preview,
    }
    _upload_store[file_id] = record
    _persist_upload(file_id, record)
    return {"file_id": file_id, "preview_markdown": preview}


def get_upload(file_id: str) -> dict[str, Any] | None:
    """Retrieve stored upload by file_id."""
    rec = _upload_store.get(file_id)
    if rec is not None:
        return rec
    rec = _load_upload_from_disk(file_id)
    if rec is not None:
        _upload_store[file_id] = rec
    return rec


def fetch_readme_from_github(github_url: str, branch: str | None = None) -> dict[str, Any]:
    """
    Fetch README from GitHub API. GET /repos/{owner}/{repo}/readme.
    Returns file_id, preview_markdown, repo_meta (name, description, language, etc.).
    """
    # Parse owner/repo from URL
    url = github_url.rstrip("/")
    if "github.com" not in url:
        raise ValueError("Invalid GitHub URL")
    parts = url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
    if len(parts) < 2:
        raise ValueError("URL must be like https://github.com/owner/repo")
    owner, repo = parts[0], parts[1]
    if ".git" in repo:
        repo = repo.replace(".git", "")

    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    params = {}
    if branch:
        params["ref"] = branch
    headers = {"Accept": "application/vnd.github.raw+json"}
    with httpx.Client(timeout=30.0) as client:
        r = client.get(api_url, params=params or None, headers=headers)
        r.raise_for_status()
        # If we used raw, body is content; else we need to decode base64 from JSON
        if "application/vnd.github.raw" in r.headers.get("Content-Type", ""):
            content = r.text
        else:
            data = r.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
        file_id = str(uuid.uuid4())
        preview = content[:5000] + ("..." if len(content) > 5000 else "")
        record = {"content": content, "filename": "README.md", "preview_markdown": preview}
        _upload_store[file_id] = record
        _persist_upload(file_id, record)

    # Repo meta
    meta_url = f"https://api.github.com/repos/{owner}/{repo}"
    with httpx.Client(timeout=10.0) as client:
        rm = client.get(meta_url)
        repo_meta = rm.json() if rm.status_code == 200 else {}
    repo_meta_short = {
        "name": repo_meta.get("name"),
        "full_name": repo_meta.get("full_name"),
        "description": repo_meta.get("description"),
        "language": repo_meta.get("language"),
        "stargazers_count": repo_meta.get("stargazers_count"),
    }

    return {
        "file_id": file_id,
        "preview_markdown": preview,
        "repo_meta": repo_meta_short,
    }
