# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Python FastAPI application for Korean survey free-response analysis. Source code lives in `survey_insight/`. Key modules include `api.py` for HTTP endpoints, `ui.py` for the browser UI, `pipeline.py` for orchestration, `topics.py` for topic modeling, `preprocessing.py` for Korean text preparation, `embeddings.py` and `llm_interpretation.py` for optional user-key provider analysis, and `exports.py` for Excel, Word, and PowerPoint output.

Tests live in `tests/` and follow the `test_*.py` naming pattern. Generated reports and local runtime artifacts should stay under `out*/` directories and should not be treated as source assets.

## Build, Test, and Development Commands

Use Python 3.11 or newer.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m survey_insight.cli demo --out .\out
python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port 8001
```

`pip install` installs runtime dependencies. `unittest discover` runs the full test suite. The CLI demo creates a sample workbook and report exports. `uvicorn` starts the local web app.

## Coding Style & Naming Conventions

Use 4-space indentation, type hints, and small functions with explicit names. Keep dataclass fields JSON-serializable because packages are stored in SQLite. Prefer deterministic local fallbacks when external services fail. Use `snake_case` for functions, variables, and module names; use `PascalCase` for dataclasses.

## Testing Guidelines

The project uses Python `unittest`. Add tests beside related behavior in `tests/test_*.py`. Cover API flows, storage round trips, export privacy, model-selection behavior, and fallback paths. When changing analysis logic, include a fixture or mock-based test that avoids live API keys.

## Commit & Pull Request Guidelines

No readable Git history is available in this workspace, so use clear imperative commits such as `Add Gemini provider support` or `Fix redacted Excel export`. Pull requests should describe the user-visible change, analysis or privacy impact, test commands run, and any generated report changes.

## Security & Configuration Tips

Never store API keys. The UI sends user-entered keys only for the current analysis request. Exports should use `redacted_text` by default. Treat `out/` and SQLite data as local artifacts that may contain survey content.
