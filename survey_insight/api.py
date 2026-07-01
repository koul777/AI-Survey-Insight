from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .edits import apply_edit
from .exports import export_excel, export_powerpoint, export_word
from .ingestion import load_table_bytes
from .llm_interpretation import enhance_with_user_llm
from .models import AnalysisPackage, DatasetProfile, TableData, new_id, to_jsonable
from .pipeline import analyze_table
from .profiling import profile_table
from .storage import StorageRepository
from .ui import app_html

app = FastAPI(title="AI Survey Insight", version="0.1.0")

_TABLES: dict[str, TableData] = {}
_PROFILES: dict[str, DatasetProfile] = {}
_RUNS: dict[str, AnalysisPackage] = {}
_EXPORT_DIR = Path("out/api_exports")
_STORE = StorageRepository(os.environ.get("SURVEY_INSIGHT_DB_PATH", "out/app.db"))


class ModelRunRequest(BaseModel):
    dataset_id: str
    project_name: str = "Survey Insight Project"
    text_column: str | None = None
    group_columns: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    azure_api_version: str | None = None


class EditRequest(BaseModel):
    edit_type: str
    payload: dict[str, Any]
    user_id: str = "api-user"


class ExportRequest(BaseModel):
    run_id: str
    type: str = Field(pattern="^(excel|word|powerpoint)$")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return app_html()


@app.post("/datasets/upload")
async def upload_dataset(
    request: Request,
    filename: str = Query(...),
    sheet_name: str | None = None,
) -> dict[str, Any]:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Request body is empty.")
    dataset_id = new_id("dataset")
    try:
        table = load_table_bytes(body, filename, sheet_name=sheet_name)
        profile = profile_table(table, dataset_id=dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _TABLES[dataset_id] = table
    _PROFILES[dataset_id] = profile
    _STORE.save_dataset(
        data=body,
        filename=filename,
        content_type=request.headers.get("content-type"),
        profile=profile,
        metadata={"sheet_name": table.sheet_name, "header_row_index": table.header_row_index},
    )
    return {"dataset_id": dataset_id, "profile": to_jsonable(profile)}


@app.get("/datasets/{dataset_id}/profile")
def get_profile(dataset_id: str) -> dict[str, Any]:
    profile = _get_profile(dataset_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return to_jsonable(profile)


@app.post("/model-runs")
def create_model_run(payload: ModelRunRequest) -> dict[str, Any]:
    table = _get_table(payload.dataset_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        package = analyze_table(
            table,
            project_name=payload.project_name,
            text_column=payload.text_column,
            group_columns=payload.group_columns or None,
            dataset_id=payload.dataset_id,
            embedding_provider=payload.llm_provider,
            embedding_api_key=payload.llm_api_key,
            embedding_base_url=payload.llm_base_url,
            embedding_model=payload.embedding_model,
            azure_api_version=payload.azure_api_version,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    package.project["llm_provider"] = payload.llm_provider or "none"
    package.project["llm_api_key_provided"] = bool(payload.llm_api_key)
    llm_warnings = enhance_with_user_llm(
        package,
        payload.llm_provider,
        payload.llm_api_key,
        base_url=payload.llm_base_url,
        model=payload.llm_model,
        azure_api_version=payload.azure_api_version,
    )
    package.project["llm_interpretation_status"] = _llm_status(payload.llm_provider, payload.llm_api_key, llm_warnings)
    package.project["llm_interpretation_warnings"] = llm_warnings
    for warning in llm_warnings:
        if warning not in package.recommendation.quality_warnings:
            package.recommendation.quality_warnings.append(warning)
    run_id = package.recommendation.run_id
    _RUNS[run_id] = package
    _STORE.save_run(
        package=package,
        dataset_id=payload.dataset_id,
        metadata={
            "project_name": payload.project_name,
            "text_column": package.text_column,
            "group_columns": package.group_columns,
            "llm_provider": payload.llm_provider or "none",
            "llm_api_key_provided": bool(payload.llm_api_key),
            "llm_base_url_provided": bool(payload.llm_base_url),
            "llm_model_provided": bool(payload.llm_model),
            "embedding_model_provided": bool(payload.embedding_model),
            "llm_interpretation_status": package.project["llm_interpretation_status"],
        },
    )
    return {"run_id": run_id, "recommendation": to_jsonable(package.recommendation)}


@app.get("/model-runs/{run_id}/recommendation")
def get_recommendation(run_id: str) -> dict[str, Any]:
    package = _get_package(run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Model run not found.")
    return to_jsonable(package.recommendation)


@app.post("/model-runs/{run_id}/edits")
def edit_run(run_id: str, payload: EditRequest) -> dict[str, Any]:
    package = _get_package(run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Model run not found.")
    try:
        edit = apply_edit(package, payload.edit_type, payload.payload, payload.user_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _RUNS[run_id] = package
    _STORE.save_run(package=package, run_id=run_id, metadata={"last_edit_type": payload.edit_type})
    return {"edit": to_jsonable(edit), "topics": to_jsonable(package.selected_topics)}


@app.post("/exports")
def create_export(payload: ExportRequest) -> dict[str, Any]:
    package = _get_package(payload.run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Model run not found.")
    path = _build_export(package, payload.run_id, payload.type)
    return {
        "type": payload.type,
        "file_path": str(path),
        "download_url": f"/exports/{payload.run_id}/{payload.type}/download",
    }


@app.get("/exports/{run_id}/{export_type}/download")
def download_export(run_id: str, export_type: str) -> FileResponse:
    if export_type not in {"excel", "word", "powerpoint"}:
        raise HTTPException(status_code=400, detail="Export type must be excel, word, or powerpoint.")
    package = _get_package(run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Model run not found.")
    path = _build_export(package, run_id, export_type)
    suffix, media_type = _export_file_type(export_type)
    return FileResponse(path, media_type=media_type, filename=f"survey_insight_{run_id}.{suffix}")


@app.get("/projects/recent")
def recent_projects(limit: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    for stored in _STORE.list_runs()[:limit]:
        package = stored.to_analysis_package()
        projects.append(
            {
                "run_id": stored.run_id,
                "dataset_id": stored.dataset_id,
                "project_name": package.project.get("name", "Survey Insight Project"),
                "created_at": stored.created_at,
                "updated_at": stored.updated_at,
                "mode": package.recommendation.mode,
                "valid_response_count": package.recommendation.valid_response_count,
                "recommended_topic_count": len(package.selected_topics),
                "text_column": package.text_column,
                "summary": package.recommendation.plain_language_summary or package.methodology_note,
            }
        )
    return {"projects": projects}


def _build_export(package: AnalysisPackage, run_id: str, export_type: str) -> Path:
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    if export_type == "excel":
        return export_excel(package, _EXPORT_DIR / f"{run_id}.xlsx")
    if export_type == "word":
        return export_word(package, _EXPORT_DIR / f"{run_id}.docx")
    if export_type == "powerpoint":
        return export_powerpoint(package, _EXPORT_DIR / f"{run_id}.pptx")
    raise HTTPException(status_code=400, detail="Export type must be excel, word, or powerpoint.")


def _export_file_type(export_type: str) -> tuple[str, str]:
    if export_type == "excel":
        return "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if export_type == "word":
        return "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if export_type == "powerpoint":
        return "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    raise HTTPException(status_code=400, detail="Export type must be excel, word, or powerpoint.")



def _llm_status(provider: str | None, api_key: str | None, warnings: list[str]) -> str:
    if not provider:
        return "not_requested"
    if not api_key:
        return "missing_key"
    if warnings:
        return "local_fallback"
    return "enhanced"


def _get_profile(dataset_id: str) -> DatasetProfile | None:
    profile = _PROFILES.get(dataset_id)
    if profile is not None:
        return profile
    stored = _STORE.get_dataset(dataset_id)
    if stored is None:
        return None
    profile = stored.to_profile()
    _PROFILES[dataset_id] = profile
    return profile


def _get_table(dataset_id: str) -> TableData | None:
    table = _TABLES.get(dataset_id)
    if table is not None:
        return table
    stored = _STORE.get_dataset(dataset_id)
    if stored is None:
        return None
    try:
        table = load_table_bytes(stored.data, stored.filename, sheet_name=stored.metadata_json.get("sheet_name"))
    except Exception:
        table = load_table_bytes(stored.data, stored.filename)
    _TABLES[dataset_id] = table
    _PROFILES[dataset_id] = stored.to_profile()
    return table


def _get_package(run_id: str) -> AnalysisPackage | None:
    package = _RUNS.get(run_id)
    if package is not None:
        return package
    stored = _STORE.get_run(run_id)
    if stored is None:
        return None
    package = stored.to_analysis_package()
    _RUNS[run_id] = package
    return package
