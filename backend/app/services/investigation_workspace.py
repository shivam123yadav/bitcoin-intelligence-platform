from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import duckdb

from app.services.analysis import analysis_service
from app.services.artifacts import load_artifact
from app.services.paths import NORMALIZED_STORAGE_ROOT


class InvestigationWorkspace:
    """Read persisted Phase 3/4 artifacts and store lightweight analyst cases.

    Read-only analytical endpoints are artifact-backed and never trigger the
    expensive analysis pipeline. Cases are intentionally local to the SIH
    prototype and persisted as JSON beside the normalized dataset.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._cases_path = Path(__file__).resolve().parents[2] / "data" / "runtime" / "cases.json"
        self._legacy_cases_path = Path(__file__).resolve().parents[2] / "data" / "cases.json"

    def _version(self) -> str:
        # Read the dataset version from the persisted run manifest first.
        # Cluster pages are read-only and must remain usable even when the
        # in-memory analysis state is unavailable after a restart.
        latest = Path(__file__).resolve().parents[2] / "data" / "runs" / "latest.json"
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            return str(payload["dataset_version"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return analysis_service.get_state().dataset_version

    @staticmethod
    def _as_iterable(value: Any) -> list[Any]:
        """Normalize pandas/NumPy/list-like cells without ambiguous truth tests."""
        if value is None:
            return []
        # NumPy arrays and pandas extension values may not support boolean
        # evaluation (e.g. ``value or []`` raises for multi-element arrays).
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

    def clusters(self) -> list[dict[str, Any]]:
        """Return persisted graph-aware clusters without requiring a full analysis state.

        Phase 3 is already persisted as ``phase3_graph_clusters.json``.  The
        previous implementation required the large in-memory wallet feature
        table to be restored before it could return even the cluster records.
        If that enrichment state was unavailable, the endpoint could appear
        empty in the UI even though the Phase 3 artifact contained 10 clusters.
        We now treat the artifact as the source of truth and enrich it when the
        wallet table is available.
        """
        version = self._version()
        artifact = load_artifact(version, "phase3_graph_clusters") or {}
        persisted = artifact.get("clusters", [])
        if not persisted:
            return []

        wallet_df = None
        completed_at = ""
        try:
            state = analysis_service.get_state()
            wallet_df = state.wallet_features
            completed_at = state.completed_at
        except Exception:
            # Artifact-backed read endpoint: enrichment is optional.
            pass

        result: list[dict[str, Any]] = []
        for cluster in persisted:
            members = [str(x) for x in cluster.get("memberWalletIds", [])]
            subset = None
            if wallet_df is not None and not wallet_df.empty and "entity_id" in wallet_df.columns:
                subset = wallet_df[wallet_df["entity_id"].isin(members)]

            ips: list[str] = []
            countries: list[str] = []
            txids: list[str] = []
            tags: list[str] = []
            if subset is not None and not subset.empty:
                if "ips" in subset.columns:
                    ips = sorted({str(ip) for values in subset["ips"] for ip in self._as_iterable(values) if ip is not None and str(ip)})
                if "countries" in subset.columns:
                    countries = sorted({str(c) for values in subset["countries"] for c in self._as_iterable(values) if c is not None and str(c)})
                if "transaction_ids" in subset.columns:
                    txids = sorted({str(tx) for values in subset["transaction_ids"] for tx in self._as_iterable(values) if tx is not None and str(tx)})[:500]
                if "transactions_per_day" in subset.columns and float(subset["transactions_per_day"].mean()) > 20:
                    tags.append("high velocity")
                if "unique_ip_count" in subset.columns and float(subset["unique_ip_count"].mean()) > 2:
                    tags.append("network diversity")
                if "anomaly_score" in subset.columns and float(subset["anomaly_score"].mean()) > 0.45:
                    tags.append("anomalous behavior")

            # Artifact metrics are always available, so use them for useful
            # graph evidence even when optional wallet enrichment is absent.
            if float(cluster.get("avgGraphDegree", 0.0)) > 100:
                tags.append("graph-connected")
            if float(cluster.get("avgCommonInputStrength", 0.0)) > 0.2:
                tags.append("common-input association")
            if not tags:
                tags.append("graph similarity")

            result.append({
                "id": str(cluster.get("id")),
                "name": cluster.get("name", cluster.get("id")),
                "walletCount": int(cluster.get("walletCount", len(members))),
                "ipCount": len(ips),
                "countries": len(countries),
                "countriesList": countries,
                "totalVolumeBtc": float(cluster.get("totalVolumeBtc", 0.0)),
                "avgAnomalyScore": float(cluster.get("avgAnomalyScore", 0.0)),
                "behavioralTags": list(dict.fromkeys(tags)),
                "memberWalletIds": members,
                "associatedIpIds": ips,
                "associatedTxIds": txids,
                "created": completed_at,
            })
        return result

    @staticmethod
    def _pattern_kind(pattern_type: str) -> str:
        return {
            "peeling_chain": "peeling",
            "mixing_like": "mixing",
            "high_velocity": "fan-out",
            "rapid_multi_hop": "fan-out",
            "dense_wallet_interaction": "fan-in",
        }.get(pattern_type, "fan-out")

    def _transaction_details(self, txids: list[str], version: str) -> dict[str, dict[str, Any]]:
        unique = list(dict.fromkeys(str(x) for x in txids if x))
        if not unique:
            return {}
        path = NORMALIZED_STORAGE_ROOT / f"observations_v{version}.duckdb"
        if not path.is_file():
            return {}
        placeholders = ",".join("?" for _ in unique)
        con = duckdb.connect(str(path), read_only=True)
        try:
            rows = con.execute(
                f"SELECT txid, timestamp, output_addresses, output_amounts, input_addresses, input_amounts, fee "
                f"FROM observations WHERE txid IN ({placeholders})",
                unique,
            ).fetchall()
        finally:
            con.close()
        out: dict[str, dict[str, Any]] = {}
        for txid, timestamp, outs, amounts, ins, in_amounts, fee in rows:
            outs = list(outs or [])
            amounts = list(amounts or [])
            ins = list(ins or [])
            in_amounts = list(in_amounts or [])
            out[str(txid)] = {
                "timestamp": str(timestamp),
                "outputs": [str(x) for x in outs],
                "output_amounts": [float(x) for x in amounts],
                "inputs": [str(x) for x in ins],
                "input_amounts": [float(x) for x in in_amounts],
                "fee": float(fee or 0),
            }
        return out

    def flow_patterns(self) -> list[dict[str, Any]]:
        version = self._version()
        refined = load_artifact(version, "phase4c") or {}
        phase4a = load_artifact(version, "phase4a") or {}
        source = {str(x.get("id")): x for x in phase4a.get("patterns", [])}
        promoted = [x for x in refined.get("patterns", []) if x.get("validationStatus") == "promoted_candidate"]
        txids = [tx for p in promoted for tx in p.get("transactionIds", [])[:6]]
        txmap = self._transaction_details(txids, version)
        result: list[dict[str, Any]] = []

        for item in promoted:
            pid = str(item.get("patternId"))
            raw = source.get(pid, {})
            pattern_type = str(item.get("patternType", raw.get("pattern_type", "")))
            confidence = str(raw.get("confidence", "high" if float(item.get("confidenceScore", 0)) >= 0.8 else "medium"))
            entity_ids = [str(x) for x in raw.get("entityIds", item.get("walletIds", []))]
            tx_ids = [str(x) for x in raw.get("transactionIds", item.get("transactionIds", []))]
            steps: list[dict[str, Any]] = []

            # Use the persisted transaction observations to make the flow view
            # concrete without loading the complete 48k-row dataset.
            for txid in tx_ids[:6]:
                tx = txmap.get(txid)
                if not tx:
                    continue
                wallets = tx["outputs"] or tx["inputs"] or entity_ids
                amounts = tx["output_amounts"] or tx["input_amounts"]
                for idx, wallet in enumerate(wallets[:2] if pattern_type == "mixing_like" else wallets[:1]):
                    steps.append({
                        "id": f"{txid}:{idx}",
                        "walletId": wallet,
                        "walletLabel": wallet,
                        "amount": float(amounts[idx]) if idx < len(amounts) else 0.0,
                        "txId": txid,
                        "timestamp": tx["timestamp"],
                        "fee": tx["fee"],
                    })
                    if len(steps) >= 6:
                        break
                if len(steps) >= 6:
                    break

            # Velocity/dense patterns can have many transactions but only one
            # or two wallets. Keep the UI compact and deterministic.
            if not steps:
                for idx, txid in enumerate(tx_ids[:6]):
                    wallet = entity_ids[0] if entity_ids else "unknown"
                    tx = txmap.get(txid, {})
                    steps.append({
                        "id": f"{txid}:{idx}",
                        "walletId": wallet,
                        "walletLabel": wallet,
                        "amount": float((tx.get("output_amounts") or [0])[0]),
                        "txId": txid,
                        "timestamp": tx.get("timestamp", item.get("firstSeen", "")),
                        "fee": float(tx.get("fee", 0)),
                    })

            result.append({
                "id": pid,
                "name": {
                    "peeling_chain": "Potential peeling-chain pattern",
                    "mixing_like": "Potential mixing-like transaction structure",
                    "high_velocity": "High transaction velocity pattern",
                    "rapid_multi_hop": "Rapid multi-hop transaction pattern",
                    "dense_wallet_interaction": "Dense wallet interaction candidate",
                }.get(pattern_type, "Candidate transaction-flow pattern"),
                "confidence": confidence,
                "description": raw.get("description", "Candidate behavioral transaction-flow pattern requiring analyst review."),
                "observations": list(raw.get("observations", [])),
                "steps": steps,
                "kind": self._pattern_kind(pattern_type),
                "patternType": pattern_type,
                "priorityScore": float(item.get("priorityScore", 0)),
                "evidenceSupportScore": float(item.get("evidenceSupportScore", 0)),
                "validationStatus": item.get("validationStatus"),
                "reviewRequired": bool(item.get("reviewRequired", False)),
                "rank": int(item.get("rank", 0)),
                "firstSeen": raw.get("firstSeen"),
                "lastSeen": raw.get("lastSeen"),
                "walletIds": entity_ids,
                "transactionIds": tx_ids,
            })
        return result

    def _read_cases(self) -> list[dict[str, Any]]:
        # Runtime analyst data lives outside the packaged analytical artifacts.
        # On first use, migrate an older data/cases.json if one exists.
        if not self._cases_path.is_file() and self._legacy_cases_path.is_file():
            try:
                legacy = json.loads(self._legacy_cases_path.read_text(encoding="utf-8"))
                if isinstance(legacy, list) and legacy:
                    self._write_cases(legacy)
                    return legacy
            except (OSError, json.JSONDecodeError):
                pass
        if not self._cases_path.is_file():
            return []
        try:
            payload = json.loads(self._cases_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write_cases(self, cases: list[dict[str, Any]]) -> None:
        self._cases_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cases_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._cases_path)

    def cases(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_cases()

    def case(self, case_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((x for x in self._read_cases() if x.get("id") == case_id), None)

    def create_case(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            cases = self._read_cases()
            now = datetime.now(timezone.utc).isoformat()
            case_id = str(payload.get("id") or f"INV-{len(cases) + 1:04d}")
            record = {
                "id": case_id,
                "primaryEntity": str(payload.get("primaryEntity", "")),
                "primaryEntityLabel": str(payload.get("primaryEntityLabel", payload.get("primaryEntity", ""))),
                "priority": payload.get("priority", "medium"),
                "priorityScore": float(payload.get("priorityScore", 0)),
                "status": payload.get("status", "open"),
                "created": payload.get("created", now),
                "updated": now,
                "analyst": payload.get("analyst", "Analyst-01"),
                "summary": payload.get("summary", "Analyst-created investigation case."),
                "evidenceIds": list(payload.get("evidenceIds", [])),
                "patternIds": list(payload.get("patternIds", [])),
                "relatedEntities": list(payload.get("relatedEntities", [])),
                "modelFindings": list(payload.get("modelFindings", [])),
                "notes": list(payload.get("notes", [])),
            }
            cases.insert(0, record)
            self._write_cases(cases)
            return record

    def add_note(self, case_id: str, note: str) -> dict[str, Any] | None:
        with self._lock:
            cases = self._read_cases()
            for record in cases:
                if record.get("id") == case_id:
                    record.setdefault("notes", []).append({"text": note, "created": datetime.now(timezone.utc).isoformat()})
                    record["updated"] = datetime.now(timezone.utc).isoformat()
                    self._write_cases(cases)
                    return record
            return None

    def add_evidence(self, case_id: str, evidence_id: str) -> dict[str, Any] | None:
        with self._lock:
            cases = self._read_cases()
            for record in cases:
                if record.get("id") == case_id:
                    ids = record.setdefault("evidenceIds", [])
                    if evidence_id not in ids:
                        ids.append(evidence_id)
                    record["updated"] = datetime.now(timezone.utc).isoformat()
                    self._write_cases(cases)
                    return record
            return None


investigation_workspace = InvestigationWorkspace()
