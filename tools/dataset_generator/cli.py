"""Command-line entry point for the offline SIH dataset generator."""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from .generator import Generator, SCALE_PLANS
from .writers import write_csv, write_ndjson, write_sample, write_csv_rows, sha256_file
from .validation import validate_records
from .audit import audit
from . import config

def run(scale, output_root, seed):
    root=Path(output_root)
    generated=root/"generated"; validation=root/"validation"; metadata=root/"metadata"; raw=root/"raw"
    for d in (generated,validation,metadata,raw): d.mkdir(parents=True,exist_ok=True)
    g=Generator(scale,root,seed); g.build()
    records=g.canonical_records()

    csv_path=generated/f"synthetic_traffic_v{config.DATASET_VERSION}.csv"
    ndjson_path=generated/f"synthetic_traffic_v{config.DATASET_VERSION}.ndjson"
    sample_path=generated/f"sample_records_v{config.DATASET_VERSION}.json"
    write_csv(records,csv_path); write_ndjson(records,ndjson_path); write_sample(records,sample_path)

    labels=g.scenario_labels()
    entity=g.entity_labels()
    catalog=g.instance_catalog()
    write_csv_rows(labels,metadata/"scenario_labels.csv",
        ["source_record_id","txid","scenario_family","scenario_instance_id","ground_truth_role",
         "label_strength","expected_signals","expected_pattern_kind","contamination_note"])
    write_csv_rows(entity,metadata/"entity_labels.csv",
        ["address","expected_group","group_kind","family","role","label_strength",
         "ip_behaviour_class","expected_elevated_features"])
    write_csv_rows(catalog,metadata/"instance_catalog.csv",
        ["scenario_family","scenario_instance_id","start_timestamp","end_timestamp","record_count",
         "wallet_count","ip_count","expected_signals","expected_pattern_kind","label_strength",
         "contamination_note"])
    write_csv_rows(g.ip_geo_rows(),metadata/"ip_geo_mapping.csv",
        ["entity_id","ip","geo_country","asn","asn_org"])

    cfg_art={
        "master_seed":seed,"scale":scale,"plan":g.plan,
        "schema_version":config.SCHEMA_VERSION,"dataset_version":config.DATASET_VERSION,
        "generator_version":config.GENERATOR_VERSION,"config_version":config.CONFIG_VERSION,
        "canonical_fields":config.CANONICAL_FIELDS
    }
    (metadata/"generator_config.json").write_text(json.dumps(cfg_art,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    report=validate_records(records)
    (validation/"validation_report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (validation/"field_quality.json").write_text(json.dumps(report["field_quality"],indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (validation/"duplicate_report.json").write_text(json.dumps({
        "full_record_duplicate_count":report["duplicate_count"],"status":"PASS" if report["duplicate_count"]==0 else "FAIL"
    },indent=2)+"\n",encoding="utf-8")
    coverage={}
    for r in labels: coverage[r["scenario_family"]]=coverage.get(r["scenario_family"],0)+1
    (validation/"scenario_coverage.json").write_text(json.dumps({
        "record_counts":coverage,"instance_count":len(catalog),"manifest_record_count":len(records)
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")

    audit_result=audit(records,labels)
    (metadata/"anti_triviality_audit.json").write_text(json.dumps(audit_result,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    # Copy the generated canonical artifacts to raw only after validation passes.
    if report["status"]!="PASS":
        raise SystemExit(f"Validation failed with {report['error_count']} errors")
    for src in (csv_path,ndjson_path,sample_path):
        shutil.copy2(src,raw/src.name)

    hashes={p.name:sha256_file(p) for p in (
        csv_path,ndjson_path,sample_path,metadata/"scenario_labels.csv",
        metadata/"entity_labels.csv",metadata/"instance_catalog.csv",metadata/"ip_geo_mapping.csv",
        metadata/"generator_config.json")}
    manifest=g.manifest_base()
    manifest.update({"output_hashes":hashes,"validation_status":report["status"],
                     "scenario_instance_count":len(catalog),
                     "scenario_record_counts":coverage,
                     "ground_truth_files":[
                         "scenario_labels.csv","entity_labels.csv","instance_catalog.csv",
                         "ip_geo_mapping.csv"]})
    (metadata/"dataset_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    # Fingerprint is over canonical dataset plus config/ground truth hashes.
    import hashlib
    h=hashlib.sha256()
    for name in sorted(hashes):
        h.update(name.encode());h.update(hashes[name].encode())
    (metadata/"dataset_fingerprint.txt").write_text(h.hexdigest()+"\n",encoding="utf-8")

    # Determinism check: build a second in-memory copy and compare canonical bytes.
    g2=Generator(scale,root,seed);g2.build()
    a=json.dumps(g.canonical_records(),separators=(",",":"),ensure_ascii=False).encode()
    b=json.dumps(g2.canonical_records(),separators=(",",":"),ensure_ascii=False).encode()
    if a!=b:
        raise SystemExit("Determinism check failed: repeated canonical generation differs")
    (validation/"determinism_report.json").write_text(json.dumps({
        "status":"PASS","byte_identical_canonical_json":True,"master_seed":seed,"scale":scale
    },indent=2)+"\n",encoding="utf-8")
    return report,manifest

def main():
    ap=argparse.ArgumentParser(description="Offline SIH 26146 synthetic dataset generator")
    ap.add_argument("command",choices=["generate"])
    ap.add_argument("--scale",choices=sorted(SCALE_PLANS),default="dev")
    ap.add_argument("--output",default=str(Path(__file__).resolve().parents[2]/"datasets"))
    ap.add_argument("--seed",type=int,default=config.MASTER_SEED)
    args=ap.parse_args()
    report,manifest=run(args.scale,Path(args.output),args.seed)
    print(json.dumps({"status":report["status"],"records":manifest["record_count"],
                      "unique_txids":manifest["unique_txids"],"scale":args.scale},indent=2))
if __name__=="__main__":
    main()
