# README to Feishu Agent - Backend

FastAPI backend that runs the Attractor-compliant pipeline to convert README (Markdown) to Feishu documents.

## Setup

```bash
cd backend
poetry install
```

## Run

```bash
poetry run uvicorn readme_to_feishu.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
```

Or activate the venv (created at `backend/.venv`):

```bash
cd backend
poetry shell
uvicorn readme_to_feishu.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
```

API docs: http://127.0.0.1:8000/docs

## Tests

```bash
cd backend
poetry lock
poetry install --with dev
poetry run pytest
```

## Pipeline

The workflow is defined in `pipelines/readme_to_feishu.dot` (Attractor DOT):

- **start** → **fetch_input** (tool) → **parse** (tool) → **understand** (codergen/LLM) → **convert** (tool) → **publish** (tool) → **exit**

Tools are implemented in `services/run_pipeline.py` and wired via the pipeline engine.

## Env (optional)

- `FEISHU_APP_ID` / `FEISHU_APP_SECRET` – if you want default Feishu credentials (otherwise set in UI).

## Notes

- `requirements.txt` is kept for reference; Poetry (`pyproject.toml`) is the source of truth.
