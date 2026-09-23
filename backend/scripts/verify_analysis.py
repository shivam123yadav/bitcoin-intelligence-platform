"""Compact end-to-end verification for the backend analysis pipeline.

The script runs ``AnalysisService`` from the project structure (``backend`` is
the application root, exactly like ``python -m uvicorn app.main:app``), prints
only summary counters, and can optionally probe the HTTP API.

Commands (project virtual environment, run from the ``backend`` directory):

    ..\\.venv\\Scripts\\python.exe scripts\\verify_analysis.py
    ..\\.venv\\Scripts\\python.exe scripts\\verify_analysis.py --force
    ..\\.venv\\Scripts\\python.exe scripts\\verify_analysis.py --api-base http://127.0.0.1:8000
    ..\\.venv\\Scripts\\python.exe scripts\\verify_analysis.py --api-only --api-base http://127.0.0.1:8000

Only compact summary information is printed; the analysis state object and the
feature frames are never dumped to the terminal.

Note: the pipeline is memory hungry (Isolation Forest, DBSCAN and the feature
frames for 48,000 observations). Use ``--api-only`` when a backend server already
holds a completed run, because running the pipeline a second time in parallel can
exhaust memory (OpenBLAS allocation failures on a 16 GB machine).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.paths import (  # noqa: E402
    DATASET_MANIFEST_PATH,
    DEFAULT_DATASET_PATH,
)


API_CHECKS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/health"),
    ("GET", "/api/v1/analysis/status"),
    ("GET", "/api/v1/analysis/stages"),
    ("GET", "/api/v1/analysis/result"),
    ("GET", "/api/v1/leads"),
    ("GET", "/api/v1/clusters"),
    ("GET", "/api/v1/patterns"),
    ("GET", "/api/v1/transactions/flow-patterns"),
    ("GET", "/api/v1/dashboard/stats"),
    ("GET", "/api/v1/dashboard/timeline"),
    ("GET", "/api/v1/dashboard/system"),
    ("GET", "/api/v1/dataset/quality"),
    ("GET", "/api/v1/search?q=bc1"),
)

# Analysis-backed entity sub-resources, probed for the top lead entity.
LEAD_ENDPOINT_TEMPLATES: tuple[str, ...] = (
    "/api/v1/entities/wallet/{entity_id}",
    "/api/v1/entities/{entity_id}/evidence",
    "/api/v1/entities/{entity_id}/findings",
    "/api/v1/entities/{entity_id}/indicators",
    "/api/v1/entities/{entity_id}/timeline",
)



class VerificationError(RuntimeError):
    """Raised when the pipeline or the queried API returns something unexpected."""


def _line(label: str, value: Any) -> None:
    print(f"{label:<20}: {value}")


def _payload_shape(payload: Any) -> str:
    if isinstance(payload, list):
        return f"{len(payload)} item(s)"
    if isinstance(payload, dict):
        keys = ", ".join(sorted(payload)[:6])
        return f"object keys [{keys}]"
    return type(payload).__name__


def _validate_payload(path: str, payload: Any) -> str | None:
    """Return an error message when a probed endpoint contract is broken."""

    if path.endswith("/health"):
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return "health payload is not ok"
        return None
    if path.endswith("/analysis/result"):
        if not isinstance(payload, dict):
            return "analysis result is not an object"
        if not payload.get("recordsProcessed"):
            return "analysis result is missing recordsProcessed"
        if not payload.get("stages"):
            return "analysis result is missing stages"
        return None
    if path.endswith("/analysis/stages") or path.endswith("/analysis/status"):
        if not payload:
            return "analysis stages/status payload is empty"
        return None
    if path.endswith("/leads"):
        if not isinstance(payload, list) or not payload:
            return "no investigative leads returned"
        return None if payload[0].get("leadId") else "lead contract is missing leadId"
    if path.endswith("/clusters"):
        if not isinstance(payload, list) or not payload:
            return "no clusters returned"
        return (
            None
            if "memberWalletIds" in payload[0]
            else "cluster contract is missing memberWalletIds"
        )
    if path.endswith("/patterns"):
        if not isinstance(payload, list) or not payload:
            return "no patterns returned"
        return None if "steps" in payload[0] else "pattern contract is missing steps"
    if path.endswith("/flow-patterns"):
        if not isinstance(payload, list) or not payload:
            return "no transaction-flow patterns returned"
        return None
    if path.endswith("/dashboard/stats"):
        if not isinstance(payload, dict) or "leads" not in payload:
            return "dashboard stats are missing the lead counter"
        return None
    if "/entities/" in path and path.endswith(
        ("/evidence", "/findings", "/indicators", "/timeline")
    ):
        if not isinstance(payload, list) or not payload:
            return "analysis-backed entity payload is empty"
        return None
    if path.endswith("/dashboard/system"):
        if not isinstance(payload, list) or not payload:
            return "dashboard system readiness list is empty"
        return None
    return None


def _fetch_json(base_url: str, path: str, timeout: float) -> tuple[Any, str | None]:
    request = urllib.request.Request(base_url.rstrip("/") + path)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - the verification reports the failure
        return None, f"{type(exc).__name__}: {exc}"


def _probe_api(base_url: str, method: str, path: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(base_url.rstrip("/") + path, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - the verification reports the failure
        return False, f"{type(exc).__name__}: {exc}"

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001 - non-JSON payloads are reported, not parsed
        payload = None

    problem = _validate_payload(path, payload)
    if problem:
        return False, f"HTTP {status_code} but {problem}"
    return True, f"HTTP {status_code} ({_payload_shape(payload)})"


def _build_checks(
    *,
    record_count: int,
    entity_count: int,
    transaction_count: int,
    cluster_count: int,
    pattern_count: int,
    lead_count: int,
    stages: list[dict[str, Any]],
) -> dict[str, bool]:
    return {
        "records_loaded": record_count > 0,
        "entities_engineered": entity_count > 0,
        "transactions_analyzed": transaction_count > 0,
        "clusters_detected": cluster_count > 0,
        "patterns_detected": pattern_count > 0,
        "leads_generated": lead_count > 0,
        "all_stages_completed": all(
            stage.get("status") == "completed" for stage in stages
        ),
    }


def _report_from_api(
    payload: Any,
    status_payload: Any,
    dataset_version: str,
    stats_payload: Any = None,
) -> dict[str, Any]:
    """Build a report shaped like ``AnalysisState.describe()`` from API payloads."""

    if not isinstance(payload, dict):
        raise VerificationError(
            "/api/v1/analysis/result did not return an analysis summary"
        )

    stats = stats_payload if isinstance(stats_payload, dict) else {}
    record_count = int(payload.get("recordsProcessed", 0))
    entity_count = int(payload.get("entitiesAnalyzed", 0))
    transaction_count = int(payload.get("transactionsAnalyzed", 0))
    cluster_count = int(payload.get("clusterCount", 0))
    pattern_count = int(payload.get("patternCount", 0))
    lead_count = int(payload.get("leadsGenerated", 0))
    stages = [
        {
            "id": stage.get("id"),
            "name": stage.get("name"),
            "status": stage.get("status"),
            "detail": stage.get("detail"),
        }
        for stage in payload.get("stages", [])
    ]

    checks = _build_checks(
        record_count=record_count,
        entity_count=entity_count,
        transaction_count=transaction_count,
        cluster_count=cluster_count,
        pattern_count=pattern_count,
        lead_count=lead_count,
        stages=stages,
    )
    warnings = [f"verification check failed: {name}" for name, ok in checks.items() if not ok]

    return {
        "status": "FAIL" if not all(checks.values()) else "WARN" if warnings else "PASS",
        "run_id": (status_payload or {}).get("run_id") or "served by API",
        "dataset_version": dataset_version,
        "started_at": "not exposed by /api/v1/analysis/result",
        "completed_at": payload.get("completedAt", "unknown"),
        "duration_ms": round(float(payload.get("durationMs", 0.0)), 2),
        "record_count": record_count,
        "entity_count": entity_count,
        "wallet_count": int(stats.get("wallets", entity_count)),
        "ip_count": int(stats.get("ips", 0)),
        "transaction_count": transaction_count,
        "cluster_count": cluster_count,
        "pattern_count": pattern_count,
        "lead_count": lead_count,
        "anomaly_count": int(payload.get("anomalyCount", 0)),
        "checks": checks,
        "stages": stages,
        "warnings": warnings,
        "errors": [],
    }


def _run_pipeline(force: bool) -> tuple[Any, str | None, float]:
    """Import and run ``AnalysisService`` lazily and report failures as text.

    The import is deferred so that ``--api-only`` mode never loads numpy/sklearn
    (loading them while a backend server already holds a completed run can exhaust
    memory on a 16 GB machine).
    """

    started = time.perf_counter()
    try:
        from app.services.analysis import AnalysisError, analysis_service
    except Exception as exc:  # noqa: BLE001 - import failures are reported, not raised
        return None, f"could not import the analysis service: {exc}", 0.0
    try:
        state = analysis_service.run(force=force)
    except AnalysisError as exc:
        return None, str(exc), round((time.perf_counter() - started) * 1000, 2)
    except MemoryError as exc:
        return (
            None,
            f"MemoryError: {exc} (re-run with --api-only --api-base <url> when a "
            "backend server already holds a completed run)",
            round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:  # noqa: BLE001 - unexpected pipeline failures are reported
        return (
            None,
            f"{type(exc).__name__}: {exc}",
            round((time.perf_counter() - started) * 1000, 2),
        )
    return state, None, round((time.perf_counter() - started) * 1000, 2)


def _runs_root() -> Path:
    from app.services.analysis import analysis_service

    return Path(analysis_service.runs_root)


def _probe_lead_endpoints(base_url: str, timeout: float) -> list[tuple[str, bool, str]]:
    """Probe the analysis-backed entity sub-resources for the top lead entity."""

    payload, problem = _fetch_json(base_url, "/api/v1/leads", timeout)
    if problem or not isinstance(payload, list) or not payload:
        return [
            ("/api/v1/leads (lead discovery)", False, problem or "no leads returned")
        ]
    entity_id = str(payload[0].get("entityId") or "")
    if not entity_id:
        return [("/api/v1/leads (lead discovery)", False, "lead has no entityId")]

    results: list[tuple[str, bool, str]] = []
    for template in LEAD_ENDPOINT_TEMPLATES:
        path = template.format(entity_id=urllib.parse.quote(entity_id))
        ok, detail = _probe_api(base_url, "GET", path, timeout)
        results.append((path, ok, detail))
    return results


def _dataset_expectation() -> tuple[str, int]:
    name = DEFAULT_DATASET_PATH.name
    try:
        manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
        return name, int(manifest.get("record_count", 0))
    except Exception:  # noqa: BLE001 - a missing manifest is reported as a warning
        return name, 0


def _dataset_version() -> str:
    try:
        manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
        return str(manifest.get("dataset_version", "unknown"))
    except Exception:  # noqa: BLE001 - a missing manifest is reported as a warning
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the backend analysis pipeline and print a compact report.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-run the analysis even when the service already holds a completed run",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="optional running backend base URL, e.g. http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help=(
            "read the verification counters from a running backend instead of running "
            "the pipeline locally (recommended when a server already holds the results)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="per-request timeout in seconds for --api-base checks",
    )
    args = parser.parse_args(argv)
    if args.api_only and not args.api_base:
        parser.error("--api-only requires --api-base")

    dataset_name, expected_records = _dataset_expectation()

    print("=== Analysis pipeline verification ===")
    _line("dataset", dataset_name)
    _line("expected records", f"{expected_records:,}" if expected_records else "unknown")

    wall_ms: float | None = None
    if args.api_only:
        _line("source", f"running backend {args.api_base}")
        payload, problem = _fetch_json(
            args.api_base, "/api/v1/analysis/result", args.timeout
        )
        if problem:
            _line("overall status", "FAIL")
            _line("errors", f"/api/v1/analysis/result -> {problem}")
            return 2
        status_payload, _ = _fetch_json(
            args.api_base, "/api/v1/analysis/status", args.timeout
        )
        stats_payload, _ = _fetch_json(
            args.api_base, "/api/v1/dashboard/stats", args.timeout
        )
        try:
            report = _report_from_api(
                payload, status_payload, _dataset_version(), stats_payload
            )
        except VerificationError as exc:
            _line("overall status", "FAIL")
            _line("errors", str(exc))
            return 2
        warnings = list(report["warnings"])
    else:
        state, problem, wall_ms = _run_pipeline(args.force)
        if state is None:
            _line("overall status", "FAIL")
            _line("errors", problem or "analysis did not return a state")
            return 2
        report = state.describe()
        warnings = list(report["warnings"])

    if expected_records and report["record_count"] != expected_records:
        warnings.append(
            f"analyzed {report['record_count']:,} records but the frozen dataset "
            f"manifest declares {expected_records:,}"
        )
    if not args.api_only:
        persisted = _runs_root() / f"{report['run_id']}.json"
        if not persisted.is_file():
            warnings.append(f"run artifact was not persisted: {persisted.name}")

    _line("run id", report["run_id"])
    _line("dataset version", report["dataset_version"])
    _line("record count", f"{report['record_count']:,}")
    entity_text = f"{report['entity_count']:,}"
    if report["ip_count"]:
        entity_text += f" (wallets {report['wallet_count']:,} / ips {report['ip_count']:,})"
    _line("entity count", entity_text)
    _line("transaction count", f"{report['transaction_count']:,}")
    _line("cluster count", f"{report['cluster_count']:,}")
    _line("pattern count", f"{report['pattern_count']:,}")
    _line("lead count", f"{report['lead_count']:,}")
    _line("anomaly count", f"{report['anomaly_count']:,}")
    duration_text = f"{report['duration_ms']:,} ms"
    if wall_ms is not None:
        duration_text += f" (wall {wall_ms:,} ms)"
    _line("analysis duration", duration_text)
    _line("started at", report["started_at"])
    _line("completed at", report["completed_at"])

    print("stages:")
    for stage in report["stages"]:
        print(
            f"  {stage['id']}. {stage['name']:<26} {stage['status']:<10} "
            f"{stage.get('detail') or ''}"
        )

    print("checks:")
    for name, passed in report["checks"].items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    _line("errors", "; ".join(report["errors"]) if report["errors"] else "none")
    _line("warnings", "; ".join(warnings) if warnings else "none")

    api_failures: list[str] = []
    if args.api_base:
        print(f"api checks ({args.api_base}):")
        for method, path in API_CHECKS:
            ok, detail = _probe_api(args.api_base, method, path, args.timeout)
            print(f"  [{'PASS' if ok else 'FAIL'}] {method} {path} -> {detail}")
            if not ok:
                api_failures.append(f"{method} {path} ({detail})")
        for path, ok, detail in _probe_lead_endpoints(args.api_base, args.timeout):
            print(f"  [{'PASS' if ok else 'FAIL'}] GET {path} -> {detail}")
            if not ok:
                api_failures.append(f"GET {path} ({detail})")

    status = report["status"]
    if api_failures or warnings:
        status = "FAIL" if report["status"] == "FAIL" or api_failures else "WARN"
    _line("overall status", status)
    if api_failures:
        _line("api errors", "; ".join(api_failures))

    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
