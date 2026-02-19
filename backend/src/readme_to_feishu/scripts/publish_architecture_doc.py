"""Integration publish script.

Reads the repo's README-to-Feishu-Agent-Architecture.md and publishes it to Feishu.

Usage:
  poetry run python -m readme_to_feishu.scripts.publish_architecture_doc

Env:
  FEISHU_APP_ID
  FEISHU_APP_SECRET
  FEISHU_FOLDER_TOKEN (optional)
"""

from __future__ import annotations

import os
from pathlib import Path

from ..services.input_layer import save_upload
from ..services.run_pipeline import run_task, get_task


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    md_path = repo_root / "README-to-Feishu-Agent-Architecture.md"
    if not md_path.exists():
        raise SystemExit(f"File not found: {md_path}")

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    folder_token = os.environ.get("FEISHU_FOLDER_TOKEN")
    if not app_id or not app_secret:
        raise SystemExit("Missing FEISHU_APP_ID/FEISHU_APP_SECRET in environment")

    content = md_path.read_text(encoding="utf-8")
    up = save_upload(content, filename=md_path.name)
    task_id = run_task(
        file_id=up["file_id"],
        feishu_app_id=app_id,
        feishu_app_secret=app_secret,
        feishu_folder_token=folder_token,
        doc_title="README-to-Feishu-Agent-Architecture",
    )
    task = get_task(task_id) or {}
    print("task_id:", task_id)
    print("status:", task.get("status"))
    print("result:", task.get("result"))
    if task.get("result", {}).get("feishu_doc_url"):
        print("feishu_doc_url:", task["result"]["feishu_doc_url"])


if __name__ == "__main__":
    main()

