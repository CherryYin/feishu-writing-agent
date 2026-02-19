import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from readme_to_feishu.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_in_memory_stores(tmp_path, monkeypatch):
    # Ensure deterministic tests across runs.
    from readme_to_feishu.services import input_layer
    from readme_to_feishu.services import run_pipeline

    # Use a temp data dir for persisted uploads in tests
    monkeypatch.setenv("README_TO_FEISHU_DATA_DIR", str(tmp_path))

    input_layer._upload_store.clear()
    run_pipeline._task_store.clear()
    yield
