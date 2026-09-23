from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from app.services.paths import PROJECT_ROOT

RUNTIME_ROOT = PROJECT_ROOT / "backend" / "data" / "runtime"
REGISTRY_PATH = RUNTIME_ROOT / "datasets.json"
UPLOAD_ROOT = RUNTIME_ROOT / "datasets"
MAX_FILE_SIZE = 500 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".csv", ".json", ".xml"}
CANONICAL_FIELDS = {
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
    "input_addresses", "output_addresses", "input_amounts", "output_amounts",
    "fee", "script_type", "geo_country", "asn",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("._") or "dataset"


class DatasetRegistry:
    UPLOAD_ROOT = UPLOAD_ROOT

    def __init__(self) -> None:
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        if not REGISTRY_PATH.exists():
            self._write({"activeDatasetId": "synthetic_traffic_v1.0.0", "datasets": []})

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("activeDatasetId", "synthetic_traffic_v1.0.0")
                payload.setdefault("datasets", [])
                return payload
        except Exception:
            pass
        return {"activeDatasetId": "synthetic_traffic_v1.0.0", "datasets": []}

    def _write(self, payload: dict[str, Any]) -> None:
        temp = REGISTRY_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(REGISTRY_PATH)

    def _ensure_default(self) -> dict[str, Any]:
        payload = self._read()
        datasets = payload["datasets"]
        if not any(str(x.get("id")) == "synthetic_traffic_v1.0.0" for x in datasets):
            datasets.insert(0, {
                "id": "synthetic_traffic_v1.0.0",
                "filename": "synthetic_traffic_v1.0.0.csv",
                "format": "csv",
                "status": "analyzed",
                "analysisStatus": "completed",
                "records": 48000,
                "uploadedAt": "2026-09-22T00:00:00Z",
                "source": "bundled",
            })
            self._write(payload)
        return payload

    def catalog(self) -> dict[str, Any]:
        payload = self._ensure_default()
        return {
            "activeDatasetId": payload.get("activeDatasetId"),
            "datasets": payload.get("datasets", []),
        }

    def active_id(self) -> str:
        return str(self._ensure_default().get("activeDatasetId"))

    def set_active(self, dataset_id: str) -> dict[str, Any]:
        payload = self._ensure_default()
        item = next((x for x in payload["datasets"] if str(x.get("id")) == dataset_id), None)
        if item is None:
            raise KeyError(dataset_id)
        if str(item.get("analysisStatus", "stored")) != "completed":
            raise ValueError("Dataset must be analyzed before it can become the active investigation dataset")
        payload["activeDatasetId"] = dataset_id
        self._write(payload)
        return item

    def get(self, dataset_id: str) -> dict[str, Any] | None:
        payload = self._ensure_default()
        return next((x for x in payload["datasets"] if str(x.get("id")) == dataset_id), None)

    def register_upload(self, original_path: Path, original_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
        payload = self._ensure_default()
        dataset_id = metadata["id"]
        item = {
            "id": dataset_id,
            "filename": original_name,
            "format": metadata["format"],
            "status": "stored",
            "analysisStatus": "not_run",
            "records": int(metadata.get("records", 0)),
            "validRecords": int(metadata.get("validRecords", 0)),
            "invalidRecords": int(metadata.get("invalidRecords", 0)),
            "uniqueTxids": int(metadata.get("uniqueTxids", 0)),
            "wallets": int(metadata.get("wallets", 0)),
            "ips": int(metadata.get("ips", 0)),
            "countries": int(metadata.get("countries", 0)),
            "asns": int(metadata.get("asns", 0)),
            "timeRangeStart": metadata.get("timeRangeStart", ""),
            "timeRangeEnd": metadata.get("timeRangeEnd", ""),
            "fileSizeBytes": int(original_path.stat().st_size),
            "sha256": metadata.get("sha256", ""),
            "uploadedAt": _now(),
            "source": "upload",
            "originalPath": str(original_path.relative_to(PROJECT_ROOT)),
        }
        payload["datasets"] = [x for x in payload["datasets"] if str(x.get("id")) != dataset_id]
        payload["datasets"].insert(0, item)
        self._write(payload)
        return item

    def save_upload(self, source_path: Path, original_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError("Unsupported file format")
        dataset_id = metadata["id"]
        folder = UPLOAD_ROOT / dataset_id
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"original{suffix}"
        source_path.replace(destination)
        return self.register_upload(destination, original_name, metadata)

    def make_id(self, filename: str, digest: str) -> str:
        stem = _safe_name(Path(filename).stem).lower()[:50]
        return f"{stem}-{digest[:10]}"

    @staticmethod
    def inspect(path: Path, filename: str) -> dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return _inspect_csv(path)
        if suffix == ".json":
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                rows = raw if isinstance(raw, list) else raw.get("records", raw.get("data", [])) if isinstance(raw, dict) else []
                if not isinstance(rows, list):
                    rows = []
                df = pd.DataFrame(rows)
                return _inspect_frame(df)
            except Exception as exc:
                raise ValueError("JSON could not be parsed as a record collection") from exc
        if suffix == ".xml":
            try:
                df = pd.read_xml(path)
                return _inspect_frame(df)
            except Exception as exc:
                raise ValueError("XML could not be parsed as a tabular record collection") from exc
        raise ValueError("Unsupported file format")


def _inspect_csv(path: Path) -> dict[str, Any]:
    header = pd.read_csv(path, nrows=0)
    missing = sorted(CANONICAL_FIELDS - set(header.columns))
    if missing:
        raise ValueError(f"Dataset is missing required fields: {', '.join(missing)}")
    rows = 0
    unique_txids: set[str] = set()
    wallets: set[str] = set()
    ips: set[str] = set()
    countries: set[str] = set()
    asns: set[str] = set()
    first = ""
    last = ""
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=10000):
        rows += len(chunk)
        unique_txids.update(x for x in chunk["txid"].astype(str) if x)
        ips.update(x for x in chunk["src_ip"].astype(str) if x)
        ips.update(x for x in chunk["dst_ip"].astype(str) if x)
        countries.update(x for x in chunk["geo_country"].astype(str) if x)
        asns.update(x for x in chunk["asn"].astype(str) if x)
        # Wallet arrays are serialized in the frozen CSV; extract tokens conservatively.
        for col in ("input_addresses", "output_addresses"):
            for value in chunk[col].astype(str):
                for token in value.replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(","):
                    token = token.strip()
                    if token:
                        wallets.add(token)
        if "timestamp" in chunk.columns and not chunk.empty:
            first = first or str(chunk["timestamp"].iloc[0])
            last = str(chunk["timestamp"].iloc[-1])
    return {
        "records": rows,
        "validRecords": rows,
        "invalidRecords": 0,
        "uniqueTxids": len(unique_txids),
        "wallets": len(wallets),
        "ips": len(ips),
        "countries": len(countries),
        "asns": len(asns),
        "timeRangeStart": first,
        "timeRangeEnd": last,
    }


def _inspect_frame(df: pd.DataFrame) -> dict[str, Any]:
    missing = sorted(CANONICAL_FIELDS - set(df.columns))
    if missing:
        raise ValueError(f"Dataset is missing required fields: {', '.join(missing)}")
    return {
        "records": len(df),
        "validRecords": len(df),
        "invalidRecords": 0,
        "uniqueTxids": int(df["txid"].nunique()) if "txid" in df else 0,
        "wallets": 0,
        "ips": int(pd.concat([df["src_ip"], df["dst_ip"]]).nunique()) if len(df) else 0,
        "countries": int(df["geo_country"].nunique()) if len(df) else 0,
        "asns": int(df["asn"].nunique()) if len(df) else 0,
        "timeRangeStart": str(df["timestamp"].iloc[0]) if len(df) else "",
        "timeRangeEnd": str(df["timestamp"].iloc[-1]) if len(df) else "",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


dataset_registry = DatasetRegistry()
