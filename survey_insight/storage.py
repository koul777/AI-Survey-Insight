from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from types import UnionType
from typing import Any, Iterator, Mapping, Union, get_args, get_origin, get_type_hints

from .models import AnalysisPackage, DatasetProfile, to_jsonable, utc_now

DEFAULT_DB_PATH = Path("out/app.db")


@dataclass(frozen=True)
class StoredDatasetSummary:
    dataset_id: str
    filename: str
    content_type: str | None
    byte_size: int
    metadata_json: dict[str, Any]
    profile_json: dict[str, Any]
    created_at: str
    updated_at: str

    def to_profile(self) -> DatasetProfile:
        return from_jsonable(self.profile_json, DatasetProfile)


@dataclass(frozen=True)
class StoredDataset(StoredDatasetSummary):
    data: bytes


@dataclass(frozen=True)
class StoredRunSummary:
    run_id: str
    dataset_id: str | None
    metadata_json: dict[str, Any]
    package_json: dict[str, Any]
    created_at: str
    updated_at: str

    def to_analysis_package(self) -> AnalysisPackage:
        return from_jsonable(self.package_json, AnalysisPackage)


@dataclass(frozen=True)
class StoredRun(StoredRunSummary):
    pass


@dataclass(frozen=True)
class StoredRunOverview:
    run_id: str
    dataset_id: str | None
    project_name: str
    mode: str
    valid_response_count: int
    recommended_topic_count: int
    human_review_status: str
    text_column: str
    summary: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RunDeleteResult:
    run_id: str
    deleted: bool


@dataclass(frozen=True)
class DatasetDeleteResult:
    dataset_id: str
    deleted: bool
    deleted_run_ids: tuple[str, ...] = ()
    blocked_by_run_ids: tuple[str, ...] = ()


def dumps_json(value: Any) -> str:
    """Serialize app dataclasses and plain JSON values for SQLite storage."""

    return json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_json(value: str) -> Any:
    return json.loads(value)


def from_jsonable(value: Any, target_type: type[Any] | Any) -> Any:
    """Rehydrate stored JSON into the app's dataclasses when callers need them."""

    restored = _coerce_jsonable(value, target_type)
    if isinstance(restored, AnalysisPackage):
        restored.recommendation.sentiment_summary = _sentiment_summary_defaults(
            restored.recommendation.sentiment_summary, restored.project.get("chat_preprocessing")
        )
    return restored


class StorageRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_dataset(
        self,
        *,
        data: bytes,
        filename: str,
        profile: DatasetProfile | Mapping[str, Any],
        dataset_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        content_type: str | None = None,
    ) -> StoredDataset:
        profile_json = _json_object(profile, "profile")
        dataset_id = dataset_id or _optional_str(profile_json.get("dataset_id"))
        if not dataset_id:
            raise ValueError("dataset_id is required when profile does not contain one.")
        metadata_json = _json_object(metadata or {}, "metadata")
        payload = bytes(data)
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO datasets (
                    dataset_id, filename, content_type, data, metadata_json,
                    profile_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset_id) DO UPDATE SET
                    filename = excluded.filename,
                    content_type = excluded.content_type,
                    data = excluded.data,
                    metadata_json = excluded.metadata_json,
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (
                    dataset_id,
                    filename,
                    content_type,
                    sqlite3.Binary(payload),
                    dumps_json(metadata_json),
                    dumps_json(profile_json),
                    now,
                    now,
                ),
            )
        saved = self.get_dataset(dataset_id)
        if saved is None:
            raise RuntimeError(f"Dataset was not saved: {dataset_id}")
        return saved

    def list_datasets(self) -> list[StoredDatasetSummary]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    dataset_id, filename, content_type, length(data) AS byte_size,
                    metadata_json, profile_json, created_at, updated_at
                FROM datasets
                ORDER BY created_at DESC, dataset_id DESC
                """
            ).fetchall()
        return [_dataset_summary_from_row(row) for row in rows]

    def get_dataset(self, dataset_id: str) -> StoredDataset | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT
                    dataset_id, filename, content_type, data, length(data) AS byte_size,
                    metadata_json, profile_json, created_at, updated_at
                FROM datasets
                WHERE dataset_id = ?
                """,
                (dataset_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredDataset(
            dataset_id=row["dataset_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            byte_size=int(row["byte_size"]),
            data=bytes(row["data"]),
            metadata_json=loads_json(row["metadata_json"]),
            profile_json=loads_json(row["profile_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_run(
        self,
        *,
        package: AnalysisPackage | Mapping[str, Any],
        run_id: str | None = None,
        dataset_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> StoredRun:
        package_json = _json_object(package, "package")
        run_id = run_id or _optional_str(_nested_get(package_json, "recommendation", "run_id"))
        if not run_id:
            raise ValueError("run_id is required when package.recommendation.run_id is absent.")
        dataset_id = dataset_id or _optional_str(_nested_get(package_json, "dataset_profile", "dataset_id"))
        metadata_json = _json_object(metadata or {}, "metadata")
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, dataset_id, metadata_json, package_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    metadata_json = excluded.metadata_json,
                    package_json = excluded.package_json,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    dataset_id,
                    dumps_json(metadata_json),
                    dumps_json(package_json),
                    now,
                    now,
                ),
            )
        saved = self.get_run(run_id)
        if saved is None:
            raise RuntimeError(f"Run was not saved: {run_id}")
        return saved

    def list_runs(self, dataset_id: str | None = None) -> list[StoredRunSummary]:
        sql = """
            SELECT run_id, dataset_id, metadata_json, package_json, created_at, updated_at
            FROM runs
        """
        params: tuple[str, ...] = ()
        if dataset_id is not None:
            sql += " WHERE dataset_id = ?"
            params = (dataset_id,)
        sql += " ORDER BY created_at DESC, run_id DESC"
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_run_summary_from_row(row) for row in rows]

    def list_run_overviews(self, limit: int = 10) -> list[StoredRunOverview]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    run_id,
                    dataset_id,
                    COALESCE(json_extract(package_json, '$.project.name'), 'Survey Insight Project')
                        AS project_name,
                    COALESCE(json_extract(package_json, '$.recommendation.mode'), '') AS mode,
                    COALESCE(json_extract(package_json, '$.recommendation.valid_response_count'), 0)
                        AS valid_response_count,
                    COALESCE(json_array_length(package_json, '$.selected_topics'), 0)
                        AS recommended_topic_count,
                    COALESCE(json_extract(package_json, '$.project.human_review.status'), 'not_reviewed')
                        AS human_review_status,
                    COALESCE(json_extract(package_json, '$.text_column'), '') AS text_column,
                    COALESCE(
                        NULLIF(json_extract(package_json, '$.recommendation.plain_language_summary'), ''),
                        json_extract(package_json, '$.methodology_note'),
                        ''
                    ) AS summary,
                    created_at,
                    updated_at
                FROM runs
                ORDER BY created_at DESC, run_id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            StoredRunOverview(
                run_id=str(row["run_id"]),
                dataset_id=row["dataset_id"],
                project_name=str(row["project_name"]),
                mode=str(row["mode"]),
                valid_response_count=int(row["valid_response_count"]),
                recommended_topic_count=int(row["recommended_topic_count"]),
                human_review_status=str(row["human_review_status"]),
                text_column=str(row["text_column"]),
                summary=str(row["summary"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def get_run(self, run_id: str) -> StoredRun | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT run_id, dataset_id, metadata_json, package_json, created_at, updated_at
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredRun(
            run_id=row["run_id"],
            dataset_id=row["dataset_id"],
            metadata_json=loads_json(row["metadata_json"]),
            package_json=loads_json(row["package_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_run_recommendation_json(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT json_extract(package_json, '$.recommendation') AS recommendation_json,
                       json_extract(package_json, '$.project.chat_preprocessing') AS chat_preprocessing_json
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None or row["recommendation_json"] is None:
            return None
        value = loads_json(row["recommendation_json"])
        if not isinstance(value, dict):
            return None
        chat_preprocessing = (
            loads_json(row["chat_preprocessing_json"]) if row["chat_preprocessing_json"] is not None else None
        )
        value["sentiment_summary"] = _sentiment_summary_defaults(value.get("sentiment_summary"), chat_preprocessing)
        return value

    def delete_run(self, run_id: str) -> RunDeleteResult:
        """Delete exactly one analysis run and report whether it existed."""

        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        return RunDeleteResult(run_id=run_id, deleted=cursor.rowcount == 1)

    def delete_dataset(self, dataset_id: str, *, delete_runs: bool = False) -> DatasetDeleteResult:
        """Delete a dataset, optionally deleting its linked runs in one transaction.

        The conservative default refuses to delete a dataset that still has runs.
        Callers must explicitly opt in to the cascade.
        """

        with self._connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM datasets WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
            if exists is None:
                return DatasetDeleteResult(dataset_id=dataset_id, deleted=False)
            linked_run_ids = tuple(
                str(row["run_id"])
                for row in conn.execute(
                    "SELECT run_id FROM runs WHERE dataset_id = ? ORDER BY run_id",
                    (dataset_id,),
                ).fetchall()
            )
            if linked_run_ids and not delete_runs:
                return DatasetDeleteResult(
                    dataset_id=dataset_id,
                    deleted=False,
                    blocked_by_run_ids=linked_run_ids,
                )
            if linked_run_ids:
                conn.execute("DELETE FROM runs WHERE dataset_id = ?", (dataset_id,))
            cursor = conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
        return DatasetDeleteResult(
            dataset_id=dataset_id,
            deleted=cursor.rowcount == 1,
            deleted_run_ids=linked_run_ids,
        )

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT,
                    data BLOB NOT NULL,
                    metadata_json TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT,
                    metadata_json TEXT NOT NULL,
                    package_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_dataset_id ON runs(dataset_id);
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _dataset_summary_from_row(row: sqlite3.Row) -> StoredDatasetSummary:
    return StoredDatasetSummary(
        dataset_id=row["dataset_id"],
        filename=row["filename"],
        content_type=row["content_type"],
        byte_size=int(row["byte_size"]),
        metadata_json=loads_json(row["metadata_json"]),
        profile_json=loads_json(row["profile_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run_summary_from_row(row: sqlite3.Row) -> StoredRunSummary:
    return StoredRunSummary(
        run_id=row["run_id"],
        dataset_id=row["dataset_id"],
        metadata_json=loads_json(row["metadata_json"]),
        package_json=loads_json(row["package_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _json_object(value: Any, label: str) -> dict[str, Any]:
    json_value = loads_json(dumps_json(value))
    if not isinstance(json_value, dict):
        raise TypeError(f"{label} must serialize to a JSON object.")
    return json_value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _nested_get(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _sentiment_summary_defaults(summary: Any, chat_preprocessing: Any) -> dict[str, Any]:
    """Recover known analysis units in memory; never invent historical row maps."""
    result = dict(summary) if isinstance(summary, Mapping) else {}
    is_chat = isinstance(chat_preprocessing, Mapping) and bool(chat_preprocessing)
    result.setdefault("analysis_unit", "context_segment" if is_chat else "response")
    result.setdefault("source_message_count", chat_preprocessing.get("retained_messages") if is_chat else None)
    return result


def _coerce_jsonable(value: Any, target_type: type[Any] | Any) -> Any:
    if target_type is Any or target_type is object:
        return value
    if value is None:
        return None

    origin = get_origin(target_type)
    if origin in (Union, UnionType):
        for candidate in get_args(target_type):
            if candidate is type(None):
                continue
            return _coerce_jsonable(value, candidate)
        return value

    if origin is list:
        args = get_args(target_type)
        item_type = args[0] if args else Any
        return [_coerce_jsonable(item, item_type) for item in value]

    if origin is dict:
        args = get_args(target_type)
        value_type = args[1] if len(args) == 2 else Any
        return {str(key): _coerce_jsonable(item, value_type) for key, item in value.items()}

    if origin is tuple:
        args = get_args(target_type)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_coerce_jsonable(item, args[0]) for item in value)
        return tuple(
            _coerce_jsonable(item, args[idx] if idx < len(args) else Any)
            for idx, item in enumerate(value)
        )

    if isinstance(target_type, type) and is_dataclass(target_type):
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected object for {target_type.__name__}.")
        hints = get_type_hints(target_type)
        kwargs = {}
        for field in fields(target_type):
            if field.name in value:
                kwargs[field.name] = _coerce_jsonable(value[field.name], hints.get(field.name, Any))
        return target_type(**kwargs)

    if target_type in {str, int, float, bool} and not isinstance(value, target_type):
        return target_type(value)
    return value
