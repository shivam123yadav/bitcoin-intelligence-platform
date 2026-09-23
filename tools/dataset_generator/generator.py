"""Deterministic corpus generator for SIH 26146.

The generator is intentionally offline and stdlib-only. It combines the existing
entity pools with family A background traffic and scenario families B-H, then
assigns provenance IDs only after timestamp ordering.
"""
from __future__ import annotations
import hashlib, json, math, os
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from . import config
    from .entities import EntityPools
    from .background import make_background_records
    from . import scenarios
except ImportError:
    import config  # type: ignore
    from entities import EntityPools  # type: ignore
    from background import make_background_records  # type: ignore
    import scenarios  # type: ignore

START_7 = config.parse_ts("2024-11-01T00:00:00Z")
START_30 = START_7

SCALE_PLANS = {
    "dev": {
        "records": 5000, "days": 7, "wallets": 1200, "ips": 400,
        "families": {"A":4000,"B":250,"C":150,"D":100,"E":100,"F":200,"G":80,"H":120},
        "instances": {"B":2,"C":2,"D":1,"E":1,"F":2,"G":2,"H":2},
    },
    "demo": {
        "records": 48000, "days": 30, "wallets": 12000, "ips": 3800,
        "families": {"A":40900,"B":2000,"C":750,"D":300,"E":420,"F":1300,"G":430,"H":1900},
        "instances": {"B":14,"C":12,"D":15,"E":8,"F":20,"G":10,"H":6},
    },
    "stress": {
        "records": 250000, "days": 90, "wallets": 90000, "ips": 20000,
        "families": {"A":205000,"B":9000,"C":6500,"D":5000,"E":5000,"F":9000,"G":4500,"H":6000},
        "instances": {"B":8,"C":8,"D":8,"E":8,"F":8,"G":8,"H":8},
    },
}

def _txid(seed: int, namespace: str) -> str:
    return hashlib.sha256(f"{seed}|tx|{namespace}".encode()).hexdigest()

def _hash_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

class Generator:
    def __init__(self, scale="dev", output_root=None, seed=config.MASTER_SEED):
        if scale not in SCALE_PLANS:
            raise ValueError(f"unknown scale: {scale}")
        self.plan=SCALE_PLANS[scale]
        self.scale=scale
        self.seed=int(seed)
        self.output_root=Path(output_root or Path(__file__).resolve().parents[2]/"datasets")
        self.entities=EntityPools(self.seed,self.plan["wallets"],self.plan["ips"])
        self._records=[]
        self._truth=[]
        self._tx_seen={}
        self._record_counter=0

    def make_record(self, *, timestamp, src_ip_idx, dst_ip_idx,
                     input_wallet_indices, output_wallet_indices,
                     input_sats, output_sats, rng, script_type, tx_namespace):
        if len(input_wallet_indices)!=len(input_sats) or len(output_wallet_indices)!=len(output_sats):
            raise ValueError("array alignment violation")
        total_in=sum(int(x) for x in input_sats)
        total_out=sum(int(x) for x in output_sats)
        if total_in <= total_out:
            raise ValueError("inputs must exceed outputs before fee")
        fee=total_in-total_out
        # Keep fee below the documented 5% guardrail by increasing the last output
        # when there is room. This preserves exact value conservation.
        max_fee=max(1,int(total_in*config.MAX_FEE_RATIO_PERCENT/100))
        if fee>max_fee:
            desired_out=total_in-max_fee
            output_sats=list(output_sats)
            output_sats[-1]+=desired_out-total_out
            total_out=sum(output_sats)
            fee=total_in-total_out
        src=self.entities.endpoint(src_ip_idx)
        dst=self.entities.endpoint(dst_ip_idx)
        if src.ip==dst.ip:
            dst=self.entities.endpoint((dst_ip_idx+1)%self.entities.ip_pool.size)
        txid=self._tx_seen.get(tx_namespace)
        if txid is None:
            txid=_txid(self.seed,tx_namespace)
            self._tx_seen[tx_namespace]=txid
        rec={
            "timestamp":config.fmt_ts(timestamp),
            "src_ip":src.ip,
            "dst_ip":dst.ip,
            "src_port":rng.randint(config.PORT_MIN,config.PORT_MAX),
            "dst_port":rng.choices(config.APPROVED_DST_PORTS,weights=[0.82,0.10,0.05,0.03],k=1)[0],
            "txid":txid,
            "input_addresses":[self.entities.wallet_pool.address(i) for i in input_wallet_indices],
            "output_addresses":[self.entities.wallet_pool.address(i) for i in output_wallet_indices],
            "input_amounts":[config.fmt_btc(int(x)) for x in input_sats],
            "output_amounts":[config.fmt_btc(int(x)) for x in output_sats],
            "fee":config.fmt_btc(fee),
            "script_type":script_type,
            "geo_country":src.geo_country,
            "asn":f"AS{src.asn} {src.asn_org}",
            "source_record_id":"",
        }
        return {"record":rec, "timestamp_epoch":int(timestamp),
                "wallet_indices":sorted(set(input_wallet_indices+output_wallet_indices)),
                "ip_indices":sorted(set([src_ip_idx,dst_ip_idx])),
                "txid":txid, "tx_namespace":tx_namespace}

    def _ctx(self):
        return scenarios.ScenarioContext(self.entities,self.make_record,self.seed,
                                          START_7,self.plan["days"])

    def build(self):
        self._records=[];self._truth=[]
        bg_rng=config.make_rng(self.seed,"background",self.scale)
        bg,bt=make_background_records(
            self.plan["families"]["A"],self.entities,bg_rng,START_7,self.plan["days"],
            self.make_record)
        # Model a small peer-propagation effect: a few transactions are observed
        # more than once. The second observation keeps the transaction payload but
        # has its own network endpoint/ports and provenance row.
        for i in range(0, max(0, len(bg)-1), 40):
            if i + 1 >= len(bg):
                break
            first, second = bg[i], bg[i+1]
            second["record"]["txid"] = first["record"]["txid"]
            for field in ("input_addresses","output_addresses","input_amounts",
                          "output_amounts","fee","script_type"):
                second["record"][field] = json.loads(json.dumps(first["record"][field]))
            gap=config.make_rng(self.seed,"propagation",str(i)).randint(1,300)
            second["timestamp_epoch"]=min(
                START_7+self.plan["days"]*86400-1,
                first["timestamp_epoch"]+gap)
            second["record"]["timestamp"]=config.fmt_ts(second["timestamp_epoch"])
        self._records.extend(bg);self._truth.extend(bt)
        for family in "BCDEFGH":
            target=self.plan["families"][family]
            fn=scenarios.FAMILY_GENERATORS[family]
            recs,truth=fn(self._ctx(),target,self.plan["instances"][family])
            self._records.extend(recs);self._truth.extend(truth)
        if len(self._records)!=self.plan["records"]:
            raise RuntimeError(f"record count mismatch: {len(self._records)} != {self.plan['records']}")
        # Attach the family bookkeeping to each record using the same list order.
        for rec, truth in zip(self._records,self._truth):
            rec["truth"]=truth
        self._records.sort(key=lambda x:(x["timestamp_epoch"],x["txid"]))
        for n,item in enumerate(self._records,1):
            item["record"]["source_record_id"]=f"R{n:08d}"
        return self._records

    def canonical_records(self):
        if not self._records:self.build()
        return [x["record"] for x in self._records]

    def scenario_labels(self):
        rows=[]
        for item in self._records:
            t=item["truth"]; r=item["record"]
            rows.append({
                "source_record_id":r["source_record_id"],"txid":r["txid"],
                "scenario_family":t["family"],"scenario_instance_id":t["instance_id"],
                "ground_truth_role":t["role"],"label_strength":t["label_strength"],
                "expected_signals":t["expected_signals"],
                "expected_pattern_kind":t["expected_pattern_kind"],
                "contamination_note":t["contamination_note"],
            })
        return rows

    def entity_labels(self):
        # Every wallet gets an evaluation row; scenario memberships overwrite the
        # background placeholder for the relevant group(s).
        rows={}
        for idx in range(self.entities.wallet_pool.size):
            addr=self.entities.wallet_pool.address(idx)
            rows[(addr,"")]={
                "address":addr,"expected_group":"","group_kind":"none","family":"A",
                "role":"background","label_strength":"weak",
                "ip_behaviour_class":"stable","expected_elevated_features":""
            }
        for item in self._records:
            t=item["truth"]; fam=t["family"]; iid=t["instance_id"]
            if not iid: continue
            for w in t["wallet_indices"]:
                addr=self.entities.wallet_pool.address(w)
                key=(addr,iid)
                rows[key]={
                    "address":addr,"expected_group":iid,
                    "group_kind":{"F":"common_input_entity","H":"dense_community","E":"scenario_instance"}.get(fam,"scenario_instance"),
                    "family":fam,"role":t["role"],"label_strength":t["label_strength"],
                    "ip_behaviour_class":"churning" if fam=="G" else "stable",
                    "expected_elevated_features":t["expected_signals"]
                }
        out=list(rows.values())
        out.sort(key=lambda x:(x["address"],x["expected_group"]))
        return out

    def instance_catalog(self):
        agg={}
        for item in self._records:
            t=item["truth"]
            iid=t["instance_id"]
            if not iid: continue
            a=agg.setdefault(iid,{"scenario_family":t["family"],"instance_id":iid,
                "first_ts":None,"last_ts":None,"records":0,"wallets":set(),"ips":set(),
                "expected_signals":t["expected_signals"],"expected_pattern_kind":t["expected_pattern_kind"],
                "label_strength":t["label_strength"],"contamination_notes":set()})
            ts=item["timestamp_epoch"]
            a["first_ts"]=ts if a["first_ts"] is None else min(a["first_ts"],ts)
            a["last_ts"]=ts if a["last_ts"] is None else max(a["last_ts"],ts)
            a["records"]+=1;a["wallets"].update(item["wallet_indices"]);a["ips"].update(item["ip_indices"])
            if t["contamination_note"]:a["contamination_notes"].add(t["contamination_note"])
        rows=[]
        for iid,a in sorted(agg.items()):
            rows.append({
                "scenario_family":a["scenario_family"],"scenario_instance_id":iid,
                "start_timestamp":config.fmt_ts(a["first_ts"]),
                "end_timestamp":config.fmt_ts(a["last_ts"]),
                "record_count":a["records"],"wallet_count":len(a["wallets"]),"ip_count":len(a["ips"]),
                "expected_signals":a["expected_signals"],"expected_pattern_kind":a["expected_pattern_kind"],
                "label_strength":a["label_strength"],"contamination_note":";".join(sorted(a["contamination_notes"]))
            })
        return rows

    def ip_geo_rows(self):
        return self.entities.ip_pool.geo_mapping_rows()

    def manifest_base(self):
        recs=self.canonical_records()
        countries=sorted({r["geo_country"] for r in recs})
        asns=sorted({r["asn"] for r in recs})
        txids=len({r["txid"] for r in recs})
        return {
            "dataset_version":config.DATASET_VERSION,
            "schema_version":config.SCHEMA_VERSION,
            "generator_version":config.GENERATOR_VERSION,
            "config_version":config.CONFIG_VERSION,
            "master_seed":self.seed,"scale":self.scale,
            "record_count":len(recs),"unique_txids":txids,
            "wallet_pool_count":self.entities.wallet_pool.size,
            "ip_pool_count":self.entities.ip_pool.size,
            "observed_country_count":len(countries),"observed_asn_count":len(asns),
            "time_start":min(r["timestamp"] for r in recs),
            "time_end":max(r["timestamp"] for r in recs),
            "canonical_fields":config.CANONICAL_FIELDS,
        }

def generate(scale="dev", output_root=None, seed=config.MASTER_SEED):
    g=Generator(scale,output_root,seed)
    g.build()
    return g
