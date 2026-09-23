"""Deterministic CSV/NDJSON/metadata writers."""
from __future__ import annotations
import csv, json, hashlib
from pathlib import Path
try:
    from . import config
except ImportError:
    import config  # type: ignore

def write_csv(records,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=config.CANONICAL_FIELDS,lineterminator="\n",quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in records:
            row=dict(r)
            for k in ("input_addresses","output_addresses","input_amounts","output_amounts"):
                row[k]=json.dumps(row[k],separators=(",",":"),ensure_ascii=False)
            w.writerow(row)

def write_ndjson(records,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="\n") as f:
        for r in records:
            f.write(json.dumps(r,separators=(",",":"),ensure_ascii=False)+"\n")

def write_sample(records,path,n=25):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="\n") as f:
        json.dump(records[:n],f,indent=2,ensure_ascii=False);f.write("\n")

def write_csv_rows(rows,path,fieldnames):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,lineterminator="\n")
        w.writeheader();w.writerows(rows)

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
