import json
import time


class InlineExecutor:
    """Run background tasks inline (deterministic tests)."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

        class _Dummy:
            def result(self):
                return None

        return _Dummy()


def test_convert_creates_task_and_lists_it(monkeypatch, client):
    from readme_to_feishu.api import routes
    from readme_to_feishu.services import run_pipeline

    # Prepare an uploaded file_id
    up = client.post(
        "/api/upload",
        files={"file": ("README.md", b"# Title\n\nHello", "text/markdown")},
    ).json()
    file_id = up["file_id"]

    # Patch executor to run inline
    monkeypatch.setattr(routes, "_executor", InlineExecutor())

    # Patch run_task to complete immediately and write deterministic task data
    def fake_run_task(*, file_id: str, task_id: str, **_):
        run_pipeline._task_store[task_id]["events"] = [
            {"kind": "progress", "data": {"step": "publishing", "progress": 100}}
        ]
        run_pipeline._task_store[task_id]["result"] = {
            "feishu_doc_url": "docx://dummy",
            "feishu_document_id": "doc_dummy",
            "status": "success",
            "failure_reason": "",
        }
        run_pipeline._task_store[task_id]["status"] = "completed"
        return task_id

    monkeypatch.setattr(routes, "run_task", fake_run_task)

    # Start conversion
    resp = client.post(
        "/api/convert",
        json={
            "file_id": file_id,
            "mode": "lightweight",
            "target_lang": "keep",
            "filters": [],
            "feishu_app_id": "x",
            "feishu_app_secret": "y",
            "doc_title": "README",
        },
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    assert task_id

    # List tasks
    tasks = client.get("/api/tasks?page=1&size=20").json()
    assert tasks["total"] >= 1
    ids = [t["task_id"] for t in tasks["tasks"]]
    assert task_id in ids


def test_sse_stream_returns_result(monkeypatch, client):
    from readme_to_feishu.api import routes
    from readme_to_feishu.services import run_pipeline

    # Seed a completed task directly
    task_id = "testtask"
    run_pipeline._task_store[task_id] = {
        "status": "completed",
        "events": [{"kind": "progress", "data": {"step": "publishing", "progress": 100}}],
        "result": {"feishu_doc_url": "docx://dummy", "status": "success"},
    }

    with client.stream("GET", f"/api/tasks/{task_id}/stream") as r:
        assert r.status_code == 200
        body = b"".join(list(r.iter_bytes()))
        text = body.decode("utf-8", errors="replace")
        assert "docx://dummy" in text
        assert "\"kind\": \"result\"" in text


def test_sse_stream_404(client):
    r = client.get("/api/tasks/nope/stream")
    assert r.status_code == 404
