"""Section 13 validator for generated canonical observations."""
from __future__ import annotations
import csv, json, re
from collections import Counter, defaultdict
from pathlib import Path
try:
    from . import config
except ImportError:
    import config  # type: ignore

TX_RE=re.compile(r"^[0-9a-f]{64}$")
ADDR_RE=re.compile(r"^bc1q["+re.escape(config.BECH32_CHARSET)+r"]{38}$")
RID_RE=re.compile(r"^R\d{8}$")
IP_RE=re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
ALLOWED=set(config.ALLOWED_SCRIPT_TYPES)

def _ip_ok(ip):
    if not IP_RE.match(ip): return False
    try: return all(0<=int(x)<=255 for x in ip.split("."))
    except: return False

def _btc_sat(v): return config.parse_btc(v)

def validate_records(records):
    errors=[]; warnings=[]; dup=Counter(); missing=Counter()
    field_counts=defaultdict(Counter)
    ids=set()
    for i,r in enumerate(records,1):
        for f in config.CANONICAL_FIELDS:
            if f not in r or r[f] in (None,""):
                missing[f]+=1;errors.append({"row":i,"rule":"MV-01","field":f,"message":"missing required field"})
        if not RID_RE.match(str(r.get("source_record_id",""))):
            errors.append({"row":i,"rule":"PR-01","message":"invalid source_record_id"})
        if not _ip_ok(str(r.get("src_ip",""))) or not _ip_ok(str(r.get("dst_ip",""))):
            errors.append({"row":i,"rule":"IP-01","message":"invalid IPv4"})
        if r.get("src_ip")==r.get("dst_ip"):
            errors.append({"row":i,"rule":"IP-03","message":"src_ip equals dst_ip"})
        for pf in ("src_port","dst_port"):
            try:
                p=int(r[pf])
                if not (config.PORT_MIN<=p<=config.PORT_MAX):
                    errors.append({"row":i,"rule":"PT-01","field":pf,"message":"port outside range"})
            except: errors.append({"row":i,"rule":"PT-01","field":pf,"message":"port not integer"})
        if int(r.get("dst_port",0)) not in config.APPROVED_DST_PORTS:
            errors.append({"row":i,"rule":"PT-03","message":"unsupported destination port"})
        if not TX_RE.match(str(r.get("txid",""))):
            errors.append({"row":i,"rule":"TX-01","message":"invalid txid"})
        try:
            ia=r["input_addresses"];oa=r["output_addresses"];iv=r["input_amounts"];ov=r["output_amounts"]
            if not (len(ia)==len(iv) and len(oa)==len(ov) and len(ia)>=1 and len(oa)>=1):
                errors.append({"row":i,"rule":"AR-01","message":"array length/alignment violation"})
            if any(not ADDR_RE.match(str(x)) for x in ia+oa):
                errors.append({"row":i,"rule":"WA-01","message":"invalid synthetic wallet address"})
            ins=[_btc_sat(x) for x in iv]; outs=[_btc_sat(x) for x in ov]; fee=_btc_sat(r["fee"])
            if any(x<=0 for x in ins+outs):
                errors.append({"row":i,"rule":"AM-02","message":"non-positive amount"})
            if sum(ins)-sum(outs)!=fee:
                errors.append({"row":i,"rule":"AM-05","message":"fee identity mismatch"})
            if sum(ins)>config.MAX_AMOUNT_SAT or sum(outs)>config.MAX_AMOUNT_SAT:
                errors.append({"row":i,"rule":"AM-03","message":"amount exceeds supply bound"})
            if fee>sum(ins)*config.MAX_FEE_RATIO_PERCENT/100:
                errors.append({"row":i,"rule":"AM-07","message":"fee ratio exceeds guardrail"})
        except Exception as exc:
            errors.append({"row":i,"rule":"AM-01","message":f"amount parse error: {exc}"})
        if r.get("script_type") not in ALLOWED:
            errors.append({"row":i,"rule":"MV-03","message":"unsupported script type"})
        if not re.match(r"^[A-Z]{2}$",str(r.get("geo_country",""))):
            errors.append({"row":i,"rule":"GQ-01","message":"invalid country"})
        if not re.match(r"^AS\d{5} .+$",str(r.get("asn",""))):
            errors.append({"row":i,"rule":"GQ-01","message":"invalid ASN"})
        dup[tuple(json.dumps(r.get(f), sort_keys=True) if isinstance(r.get(f),(list,dict)) else r.get(f) for f in config.CANONICAL_FIELDS)] += 1
        for f in config.CANONICAL_FIELDS: field_counts[f]["present" if r.get(f) not in (None,"") else "missing"]+=1
    duplicate_rows=sum(n-1 for n in dup.values() if n>1)
    if duplicate_rows:
        errors.append({"rule":"DU-01","message":f"{duplicate_rows} full-record duplicates"})
    report={
        "status":"FAIL" if errors else "PASS",
        "record_count":len(records),
        "valid_records":len(records) if not errors else None,
        "error_count":len(errors),"warning_count":len(warnings),
        "duplicate_count":duplicate_rows,"missing_field_counts":dict(missing),
        "errors":errors[:2000],"warnings":warnings[:2000],
        "field_quality":{k:dict(v) for k,v in field_counts.items()},
    }
    return report

def validate_csv(path):
    with open(path,encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    # JSON arrays need parsing; ports are strings from CSV.
    for r in rows:
        for f in ("input_addresses","output_addresses","input_amounts","output_amounts"):
            r[f]=json.loads(r[f])
        for f in ("src_port","dst_port"): r[f]=int(r[f])
    return validate_records(rows)
