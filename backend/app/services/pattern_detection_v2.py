from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Any

import numpy as np
import pandas as pd

from app.services.analysis import analysis_service
from app.services.artifacts import load_artifact, save_artifact


@dataclass(frozen=True)
class PatternConfig:
    velocity_window_minutes: int = 60
    velocity_min_transactions: int = 8
    rapid_hop_window_hours: float = 24.0
    rapid_min_hops: int = 3
    peeling_min_hops: int = 3
    peeling_min_decline: float = 0.05
    mixing_min_inputs: int = 3
    mixing_min_outputs: int = 3
    mixing_similarity_cv: float = 0.15
    dense_min_wallets: int = 4
    dense_min_repeated_pair_count: int = 3
    max_per_type: int = 50
    max_total: int = 300


class PatternDetectionV2:
    """Non-destructive Phase 4A pattern-detection experiment.

    This service deliberately does not modify AnalysisService._patterns().
    It reads the frozen normalized observations and returns additional,
    structured candidate patterns for comparison before integration.
    """

    TYPES = (
        "high_velocity",
        "rapid_multi_hop",
        "peeling_chain",
        "mixing_like",
        "dense_wallet_interaction",
    )

    def __init__(self, config: PatternConfig | None = None) -> None:
        self.config = config or PatternConfig()
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, force: bool = False) -> dict[str, Any]:
        state = analysis_service.get_state()
        version = state.dataset_version
        with self._lock:
            if not force and version in self._cache:
                return self._cache[version]
        if not force:
            disk = load_artifact(version, "phase4a")
            if disk is not None:
                with self._lock:
                    self._cache[version] = disk
                return disk
        result = self._run(version)
        save_artifact(version, "phase4a", result)
        with self._lock:
            self._cache[version] = result
        return result

    def _run(self, version: str) -> dict[str, Any]:
        started = datetime.utcnow()
        df = analysis_service.load_observations_columns(
            version,
            ["timestamp", "txid", "input_addresses", "output_addresses", "input_amounts", "output_amounts"],
            order_by="timestamp",
        ).copy()
        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df[df["_ts"].notna()].sort_values(["_ts", "txid"], kind="mergesort").reset_index(drop=True)

        txs = self._transactions(df)
        patterns: list[dict[str, Any]] = []
        counts = {k: 0 for k in self.TYPES}
        detectors = (
            self._detect_velocity,
            self._detect_rapid_hops,
            self._detect_peeling,
            self._detect_mixing,
            self._detect_dense_interaction,
        )
        for detector in detectors:
            for pattern in detector(txs):
                kind = pattern["pattern_type"]
                if counts[kind] >= self.config.max_per_type or len(patterns) >= self.config.max_total:
                    continue
                patterns.append(pattern)
                counts[kind] += 1
            if len(patterns) >= self.config.max_total:
                break

        patterns.sort(key=lambda p: (-float(p["confidenceScore"]), p["firstSeen"], p["id"]))
        for i, p in enumerate(patterns, 1):
            p["rank"] = i

        duration_ms = round((datetime.utcnow() - started).total_seconds() * 1000, 2)
        result = {
            "datasetVersion": version,
            "method": "Phase 4A structured behavioral pattern experiment",
            "config": self.config.__dict__.copy(),
            "patternCount": len(patterns),
            "countsByType": counts,
            "durationMs": duration_ms,
            "patterns": patterns,
        }
        return result

    @staticmethod
    def _seq(value: Any) -> list[Any]:
        """Normalize parquet/pandas list-like cells without truth-value checks."""
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass
        return list(value) if isinstance(value, (pd.Series,)) else [value]

    @staticmethod
    def _transactions(df: pd.DataFrame) -> list[dict[str, Any]]:
        out = []
        for row in df.to_dict("records"):
            ins = [str(x) for x in PatternDetectionV2._seq(row.get("input_addresses")) if x]
            outs = [str(x) for x in PatternDetectionV2._seq(row.get("output_addresses")) if x]
            ia = [float(x) for x in PatternDetectionV2._seq(row.get("input_amounts"))]
            oa = [float(x) for x in PatternDetectionV2._seq(row.get("output_amounts"))]
            out.append({
                "txid": str(row["txid"]),
                "ts": row["_ts"],
                "timestamp": row["timestamp"],
                "inputs": ins,
                "outputs": outs,
                "input_amounts": ia,
                "output_amounts": oa,
                "fee": float(row.get("fee", 0) or 0),
            })
        return out

    @staticmethod
    def _pattern(pid: str, kind: str, confidence: float, description: str,
                 observations: list[str], wallets: list[str], txids: list[str],
                 first: Any, last: Any, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": pid,
            "pattern_type": kind,
            "confidenceScore": round(float(max(0.0, min(0.99, confidence))), 3),
            "confidence": "high" if confidence >= .80 else "medium" if confidence >= .60 else "low",
            "description": description,
            "observations": observations,
            "entityIds": sorted(set(wallets)),
            "transactionIds": sorted(set(txids)),
            "firstSeen": str(first),
            "lastSeen": str(last),
            "evidence": evidence,
        }

    def _detect_velocity(self, txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_wallet: dict[str, list[dict[str, Any]]] = {}
        for tx in txs:
            for w in set(tx["inputs"] + tx["outputs"]):
                by_wallet.setdefault(w, []).append(tx)
        results = []
        window = self.config.velocity_window_minutes * 60
        for wallet, rows in by_wallet.items():
            if len(rows) < self.config.velocity_min_transactions:
                continue
            rows = sorted(rows, key=lambda x: x["ts"])
            left = 0; best = 0; best_pair = (0, len(rows) - 1)
            for right in range(len(rows)):
                while (rows[right]["ts"] - rows[left]["ts"]).total_seconds() > window:
                    left += 1
                count = right - left + 1
                if count > best:
                    best = count; best_pair = (left, right)
            if best < self.config.velocity_min_transactions:
                continue
            density = min(best / 20.0, 1.0)
            confidence = 0.55 + 0.40 * density
            a, b = rows[best_pair[0]], rows[best_pair[1]]
            results.append(self._pattern(
                f"PAT4-VEL-{wallet[:10]}-{best}", "high_velocity", confidence,
                "High transaction velocity for a wallet within a short observed time window.",
                [f"{best} wallet-linked transactions observed within {self.config.velocity_window_minutes} minutes",
                 "Velocity is a behavioral signal and requires analyst review"],
                [wallet], [x["txid"] for x in rows[best_pair[0]:best_pair[1]+1]], a["timestamp"], b["timestamp"],
                [{"type": "velocity_window", "count": best, "windowMinutes": self.config.velocity_window_minutes}]
            ))
        return sorted(results, key=lambda p: p["confidenceScore"], reverse=True)

    def _build_hops(self, txs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        by_input: dict[str, list[dict[str, Any]]] = {}
        for tx in txs:
            for w in tx["inputs"]:
                by_input.setdefault(w, []).append(tx)
        for rows in by_input.values():
            rows.sort(key=lambda x: x["ts"])
        chains = []
        for start in txs:
            if not start["outputs"]:
                continue
            current = start
            chain = [start]
            used = {start["txid"]}
            for _ in range(5):
                candidates = []
                for out in current["outputs"]:
                    for nxt in by_input.get(out, []):
                        if nxt["txid"] in used or nxt["ts"] <= current["ts"]:
                            continue
                        candidates.append(nxt)
                if not candidates:
                    break
                nxt = min(candidates, key=lambda x: (x["ts"], x["txid"]))
                chain.append(nxt); used.add(nxt["txid"]); current = nxt
            if len(chain) >= self.config.rapid_min_hops:
                chains.append(chain)
        return chains

    def _detect_rapid_hops(self, txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for chain in self._build_hops(txs):
            span = (chain[-1]["ts"] - chain[0]["ts"]).total_seconds() / 3600.0
            if span > self.config.rapid_hop_window_hours:
                continue
            wallets = []
            for tx in chain:
                wallets.extend(tx["inputs"]); wallets.extend(tx["outputs"])
            confidence = 0.60 + 0.30 * min(len(chain) / 5.0, 1.0) + 0.09 * max(0, 1 - span / self.config.rapid_hop_window_hours)
            results.append(self._pattern(
                f"PAT4-HOP-{chain[0]['txid'][:10]}-{len(chain)}", "rapid_multi_hop", min(confidence, .99),
                "Candidate rapid transaction-linked multi-hop sequence.",
                [f"{len(chain)} chronological transaction hops observed", f"Sequence span: {span:.2f} hours", "Temporal linkage does not by itself prove fund movement"],
                wallets, [x["txid"] for x in chain], chain[0]["timestamp"], chain[-1]["timestamp"],
                [{"type":"hop_sequence", "hopCount":len(chain), "spanHours":round(span,3)}]
            ))
        return sorted(results, key=lambda p: p["confidenceScore"], reverse=True)

    def _detect_peeling(self, txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_input: dict[str, list[dict[str, Any]]] = {}
        for tx in txs:
            for w in tx["inputs"]:
                by_input.setdefault(w, []).append(tx)
        for rows in by_input.values(): rows.sort(key=lambda x: x["ts"])
        results=[]; seen=set()
        for start in txs:
            if not start["outputs"]: continue
            chain=[start]; current=start; amounts=[]; used={start["txid"]}
            for _ in range(4):
                if not current["outputs"]: break
                # choose the first output that is later spent; retain its amount
                candidates=[]
                for idx,w in enumerate(current["outputs"]):
                    for nxt in by_input.get(w,[]):
                        if nxt["txid"] not in used and nxt["ts"] > current["ts"]:
                            amt=current["output_amounts"][idx] if idx < len(current["output_amounts"]) else 0
                            candidates.append((nxt, float(amt), w))
                if not candidates: break
                nxt, amt, _ = min(candidates, key=lambda x:(x[0]["ts"],x[0]["txid"]))
                amounts.append(amt); chain.append(nxt); used.add(nxt["txid"]); current=nxt
            if len(chain)<self.config.peeling_min_hops: continue
            if len(amounts)>=2 and all(amounts[i+1] <= amounts[i]*(1-self.config.peeling_min_decline) for i in range(len(amounts)-1)):
                key=tuple(x["txid"] for x in chain)
                if key in seen: continue
                seen.add(key)
                decline=1-(amounts[-1]/max(amounts[0],1e-9))
                confidence=min(.95,.62 + .20*min(len(chain)/5,1) + .13*min(decline,1))
                wallets=[]
                for x in chain: wallets.extend(x["inputs"]); wallets.extend(x["outputs"])
                results.append(self._pattern(
                    f"PAT4-PEEL-{chain[0]['txid'][:10]}-{len(chain)}", "peeling_chain", confidence,
                    "Candidate peeling-chain structure with chronological output-to-input continuation and declining observed amounts.",
                    [f"{len(chain)} linked transactions", f"Observed amount decline: {decline:.1%}", "Pattern requires analyst review"],
                    wallets, [x["txid"] for x in chain], chain[0]["timestamp"], chain[-1]["timestamp"],
                    [{"type":"amount_decline","start":amounts[0],"end":amounts[-1],"decline":round(decline,4)}]
                ))
        return sorted(results, key=lambda p:p["confidenceScore"], reverse=True)

    def _detect_mixing(self, txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results=[]
        for tx in txs:
            ni,no=len(tx["inputs"]),len(tx["outputs"])
            if ni<self.config.mixing_min_inputs or no<self.config.mixing_min_outputs: continue
            vals=np.asarray(tx["output_amounts"],dtype=float)
            vals=vals[vals>0]
            cv=float(np.std(vals)/max(np.mean(vals),1e-12)) if len(vals)>=3 else 1.0
            fan_score=min((ni+no)/12,1.0)
            similar=cv <= self.config.mixing_similarity_cv
            if not similar and ni+no<8: continue
            confidence=.55 + .20*fan_score + (.20 if similar else .05)
            wallets=tx["inputs"]+tx["outputs"]
            results.append(self._pattern(
                f"PAT4-MIX-{tx['txid'][:16]}", "mixing_like", min(confidence,.95),
                "Candidate mixing-like fan-in/fan-out transaction structure.",
                [f"{ni} inputs and {no} outputs", f"Output-value coefficient of variation: {cv:.3f}", "This is a structural similarity signal, not proof of mixing"],
                wallets,[tx["txid"]],tx["timestamp"],tx["timestamp"],
                [{"type":"fan_in_out","inputs":ni,"outputs":no,"outputCv":round(cv,4)}]
            ))
        return sorted(results, key=lambda p:p["confidenceScore"], reverse=True)

    def _detect_dense_interaction(self, txs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pair_counts: dict[tuple[str,str],int] = {}
        pair_txs: dict[tuple[str,str],set[str]] = {}
        wallet_counts: dict[str,int] = {}
        for tx in txs:
            wallets=sorted(set(tx["inputs"]+tx["outputs"]))
            if len(wallets)<self.config.dense_min_wallets: continue
            for w in wallets: wallet_counts[w]=wallet_counts.get(w,0)+1
            for i,a in enumerate(wallets):
                for b in wallets[i+1:]:
                    k=(a,b); pair_counts[k]=pair_counts.get(k,0)+1; pair_txs.setdefault(k,set()).add(tx["txid"])
        results=[]
        for (a,b),count in sorted(pair_counts.items(), key=lambda kv:(-kv[1],kv[0])):
            if count<self.config.dense_min_repeated_pair_count: continue
            txids=sorted(pair_txs[(a,b)])
            confidence=min(.94,.58+.08*min(count,4))
            results.append(self._pattern(
                f"PAT4-DENSE-{a[:7]}-{b[:7]}", "dense_wallet_interaction", confidence,
                "Repeated wallet co-occurrence indicates a dense interaction candidate.",
                [f"Wallet pair co-occurred in {count} transactions", "Co-occurrence is an association signal and does not establish ownership"],
                [a,b],txids,txids[0] if txids else "",txids[-1] if txids else "",
                [{"type":"repeated_wallet_pair","walletA":a,"walletB":b,"transactionCount":count}]
            ))
            if len(results)>=self.config.max_per_type: break
        return results


pattern_detection_v2 = PatternDetectionV2()
