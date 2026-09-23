"""Ground-truth-only anti-triviality audit.

This is a tuning artifact. It never feeds labels to the runtime pipeline.
"""
from __future__ import annotations
import math, statistics
from collections import defaultdict
try:
    from . import config
except ImportError:
    import config  # type: ignore

def _mean(xs): return sum(xs)/len(xs) if xs else 0.0

def audit(records, labels):
    label_map={x["source_record_id"]:x["scenario_family"] for x in labels}
    rows=[]
    # Simple scalar features intentionally audited offline only.
    for name,fn in [
        ("input_count",lambda r:len(r["input_addresses"])),
        ("output_count",lambda r:len(r["output_addresses"])),
        ("amount_sum",lambda r:sum(config.parse_btc(x) for x in r["input_amounts"])/config.SAT_PER_BTC),
        ("fee",lambda r:config.parse_btc(r["fee"])/config.SAT_PER_BTC),
        ("src_port",lambda r:int(r["src_port"])),
        ("dst_port",lambda r:int(r["dst_port"])),
    ]:
        bg=[];sc=[]
        for r in records:
            v=float(fn(r))
            (bg if label_map.get(r["source_record_id"])=="A" else sc).append(v)
        if not bg or not sc: continue
        # AUC-like rank separation using means, not a model metric.
        mb,ms=_mean(bg),_mean(sc)
        pooled=statistics.pstdev(bg+sc) or 1.0
        effect=abs(ms-mb)/pooled
        rows.append({"feature":name,"background_mean":mb,"scenario_mean":ms,"standardized_mean_difference":effect})
    return {
        "audit_scope":"ground_truth_only",
        "single_feature_audit":rows,
        "status":"PASS_WITH_REVIEW" if all(x["standardized_mean_difference"]<4 for x in rows) else "REVIEW_REQUIRED",
        "note":"This artifact is for generator tuning only and is never a runtime feature."
    }
