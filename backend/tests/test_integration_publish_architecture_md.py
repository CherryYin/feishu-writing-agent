import os
from pathlib import Path

import pytest


@pytest.mark.integration
def test_publish_readme_architecture_md():
    """Integration test: publishes README-to-Feishu-Agent-Architecture.md to Feishu.

    Requires env:
      FEISHU_APP_ID, FEISHU_APP_SECRET
    Optional:
      FEISHU_FOLDER_TOKEN
    """
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        pytest.skip("Missing FEISHU_APP_ID/FEISHU_APP_SECRET")

    repo_root = Path(__file__).resolve().parents[2]
    md_path = repo_root / "README-to-Feishu-Agent-Architecture.md"
    assert md_path.exists()

    from readme_to_feishu.services.input_layer import save_upload
    from readme_to_feishu.services.run_pipeline import run_task, get_task

    content = md_path.read_text(encoding="utf-8")
    up = save_upload(content, filename=md_path.name)

    task_id = run_task(
        file_id=up["file_id"],
        feishu_app_id=app_id,
        feishu_app_secret=app_secret,
        feishu_folder_token=os.environ.get("FEISHU_FOLDER_TOKEN"),
        doc_title="README-to-Feishu-Agent-Architecture",
    )
    t = get_task(task_id)
    assert t is not None
    assert t["status"] in ("completed", "failed")
    assert t["result"] is not None
    assert t["result"]["status"] == "success"
    assert t["result"]["feishu_document_id"]

