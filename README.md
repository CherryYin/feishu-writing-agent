# README to Feishu Agent

Convert GitHub repository README (Markdown) to Feishu documents via a Web UI and an Attractor-compliant pipeline.

## Architecture

- **Frontend**: React + TypeScript + Vite + Semi Design. Upload README / GitHub URL, configure conversion, stream task progress via SSE.
- **Backend**: FastAPI. APIs: upload, fetch-readme, convert (async task), tasks list, SSE stream for task progress.
- **Pipeline**: Attractor DOT graph (`backend/pipelines/readme_to_feishu.dot`). Stages: fetch input → parse markdown → understand (LLM) → convert to Feishu blocks → publish to Feishu.

See [README-to-Feishu-Agent-Architecture.md](./README-to-Feishu-Agent-Architecture.md) for the full design. Pipeline and execution follow [attractor/attractor-spec.md](./attractor/attractor-spec.md).

## Quick start

### Backend

```bash
cd backend
poetry install
poetry run uvicorn readme_to_feishu.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
```

### Frontend

```bashnpm 
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Use “转换” to upload a README or paste a GitHub URL, set options (mode, language, filters, Feishu app credentials), then “开始转换”. Progress is streamed via SSE; on success you get a Feishu document link.

### Feishu

To publish to Feishu you need an app (App ID / App Secret) and optionally a folder token. Create an app in [Feishu Open Platform](https://open.feishu.cn/app), enable “Docx (document)” and get tenant token; put App ID and App Secret in the config panel. Without them, the pipeline still runs but the publish step will fail (you can test upload → parse → convert without Feishu).

## Project layout

- `backend/` – FastAPI app, pipeline engine (DOT parser, handlers, context, conditions), services (input, Feishu client, markdown parser, block converter), API routes, task store.
- `frontend/` – React app: ConvertPanel (upload, GitHub URL, config, convert, SSE progress, result link), TaskHistory.
- `attractor/` – Specs: attractor-spec, unified-llm-spec, coding-agent-loop-spec (constraints for the pipeline).
- `README-to-Feishu-Agent-Architecture.md` – Product/tech architecture.

## License

MIT
