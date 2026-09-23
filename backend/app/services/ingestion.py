from dataclasses import dataclass
import json
from pathlib import Path
import threading
from time import perf_counter
from typing import Any, Literal

import pandas as pd

from app.services.paths import (
    DATASET_MANIFEST_PATH,
    DATASET_VALIDATION_PATH,
    DEFAULT_DATASET_PATH,
    NORMALIZED_STORAGE_ROOT,
)
from app.services.storage import NormalizedDatasetStorage, StorageResult
from app.services.validation import CANONICAL_FIELDS, RecordValidator


class DatasetIngestionError(RuntimeError):
    pass


class DatasetNotFoundError(DatasetIngestionError):
    pass


class DatasetStructureError(DatasetIngestionError):
    pass


class DatasetIntegrityError(DatasetIngestionError):
    pass


@dataclass(frozen=True)
class IngestionStatus:
    status: Literal["READY", "PARTIAL", "FAILED"]
    record_count: int
    valid_records: int
    invalid_records: int
    missing_fields: list[str]
    load_time_ms: float
    dataset_version: str


@dataclass
class IngestionResult:
    status: IngestionStatus
    records: pd.DataFrame
    errors: list[dict[str, Any]]
    reference_validation_status: str | None
    storage: StorageResult | None


class DatasetIngestionService:
    def __init__(
        self,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        manifest_path: Path = DATASET_MANIFEST_PATH,
        validation_report_path: Path = DATASET_VALIDATION_PATH,
        storage: NormalizedDatasetStorage | None = None,
        chunk_size: int = 10_000,
    ) -> None:
        self.dataset_path = dataset_path
        self.manifest_path = manifest_path
        self.validation_report_path = validation_report_path
        self.storage = storage or NormalizedDatasetStorage(NORMALIZED_STORAGE_ROOT)
        self.chunk_size = chunk_size
        self._result: IngestionResult | None = None
        self._lock = threading.Lock()

    def ingest(self) -> IngestionResult:
        with self._lock:
            if self._result is not None:
                return self._result

            started_at = perf_counter()
            manifest = self._read_json_object(self.manifest_path, "dataset manifest")
            dataset_version = str(manifest.get("dataset_version", "unknown"))

            if not self.dataset_path.is_file():
                raise DatasetNotFoundError(
                    f"Dataset file not found: {self.dataset_path.name}"
                )

            try:
                header = pd.read_csv(
                    self.dataset_path,
                    nrows=0,
                    dtype=str,
                    keep_default_na=False,
                )
            except Exception as exc:
                raise DatasetStructureError(
                    "Failed to read the dataset header"
                ) from exc

            missing_columns = [
                field for field in CANONICAL_FIELDS if field not in header.columns
            ]
            if missing_columns:
                raise DatasetStructureError(
                    f"Dataset is missing required columns: {', '.join(missing_columns)}"
                )

            validator = RecordValidator(
                time_start=manifest.get("time_start"),
                time_end=manifest.get("time_end"),
            )
            normalized_rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            missing_value_fields: set[str] = set()
            rows_seen = 0

            try:
                chunks = pd.read_csv(
                    self.dataset_path,
                    dtype=str,
                    keep_default_na=False,
                    chunksize=self.chunk_size,
                )
                for chunk in chunks:
                    for chunk_offset, (_, values) in enumerate(chunk.iterrows()):
                        row_number = rows_seen + chunk_offset + 2
                        rows_seen += 1
                        validated = validator.validate(row_number, values)
                        if validated.errors:
                            errors.extend(validated.errors)
                            missing_value_fields.update(validated.missing_fields)
                            continue
                        assert validated.record is not None
                        normalized_rows.append(validated.record)
            except DatasetIngestionError:
                raise
            except Exception as exc:
                raise DatasetStructureError("Failed while parsing the dataset") from exc

            expected_record_count = int(manifest.get("record_count", rows_seen))
            if rows_seen != expected_record_count:
                raise DatasetIntegrityError(
                    f"Dataset record count does not match manifest: "
                    f"found {rows_seen}, expected {expected_record_count}"
                )

            valid_records = len(normalized_rows)
            invalid_records = rows_seen - valid_records
            ingestion_status: Literal["READY", "PARTIAL", "FAILED"]
            if invalid_records == 0:
                ingestion_status = "READY"
            elif valid_records:
                ingestion_status = "PARTIAL"
            else:
                ingestion_status = "FAILED"

            storage_result: StorageResult | None = None
            if normalized_rows:
                records = pd.DataFrame.from_records(
                    normalized_rows,
                    columns=CANONICAL_FIELDS,
                )
                storage_result = self.storage.write(records, dataset_version)
            else:
                records = pd.DataFrame(columns=CANONICAL_FIELDS)

            reference_validation = self._read_json_object(
                self.validation_report_path,
                "validation report",
            )
            result = IngestionResult(
                status=IngestionStatus(
                    status=ingestion_status,
                    record_count=rows_seen,
                    valid_records=valid_records,
                    invalid_records=invalid_records,
                    missing_fields=sorted(missing_value_fields),
                    load_time_ms=round((perf_counter() - started_at) * 1000, 3),
                    dataset_version=dataset_version,
                ),
                records=records,
                errors=errors,
                reference_validation_status=(
                    str(reference_validation["status"])
                    if reference_validation.get("status") is not None
                    else None
                ),
                storage=storage_result,
            )
            self._result = result
            return result

    @staticmethod
    def _read_json_object(path: Path, description: str) -> dict[str, Any]:
        if not path.is_file():
            raise DatasetIntegrityError(f"{description} not found: {path.name}")
        try:
            with path.open("r", encoding="utf-8") as file:
                value = json.load(file)
        except Exception as exc:
            raise DatasetIntegrityError(f"Failed to read {description}") from exc
        if not isinstance(value, dict):
            raise DatasetIntegrityError(f"{description} must contain a JSON object")
        return value
