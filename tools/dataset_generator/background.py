"""Family A: normal background traffic.

This module deliberately creates a broad, heavy-tailed baseline rather than
"clean" normal rows. It is the false-positive reservoir for the demo.
"""
from __future__ import annotations
import math
from typing import Callable, Dict, List, Tuple

try:
    from . import config
except ImportError:
    import config  # type: ignore

def choose_weighted_index(rng, count: int, alpha: float) -> int:
    # Inverse-CDF Zipf-like selection without materialising a huge weight list.
    u = max(rng.random(), 1e-12)
    x = int((u ** (-1.0 / max(alpha, 0.1))) - 1)
    return min(max(x, 0), count - 1)

def make_background_records(
    count: int,
    entities,
    rng,
    start_epoch: int,
    days: int,
    make_record: Callable,
    role_prefix: str = "A",
) -> Tuple[List[dict], List[dict]]:
    """Return (records, bookkeeping) for family A."""
    records: List[dict] = []
    truth: List[dict] = []
    wallets = entities.wallet_pool
    ips = entities.ip_pool
    reuse = config.BACKGROUND_DEFAULTS["reuse"]
    shape = config.BACKGROUND_DEFAULTS["shape"]
    amount_cfg = config.BACKGROUND_DEFAULTS["amount"]

    # Reserve a stable service/hub subset and a broad general population.
    service = list(range(wallets.service_wallet_count))
    hub = list(range(wallets.service_wallet_count, wallets.background_reserved_count))
    normal_limit = max(wallets.background_reserved_count + 1, min(wallets.size, 10500))

    for i in range(count):
        day = rng.randrange(days)
        base = start_epoch + day * 86400
        hour = rng.choices(range(24), weights=config.HOUR_WEIGHTS, k=1)[0]
        ts = base + hour * 3600 + rng.randrange(3600)

        # Heavy-tailed input/output cardinality.
        r = rng.random()
        if r < shape["p_consolidation"]:
            n_in = rng.randint(8, min(12, max(8, wallets.size // 1000 + 8)))
            n_out = rng.randint(1, 2)
        else:
            n_in = 1 + (1 if rng.random() < shape["p_multi_input"] else 0)
            if rng.random() < shape["p_multi_input"] * 0.25:
                n_in += 1
            n_out = 1 + (1 if rng.random() < shape["p_multi_output"] else 0)
            if rng.random() < shape["p_multi_output"] * 0.12:
                n_out += 1
            n_in = min(n_in, 3)
            n_out = min(n_out, 3)

        # Occasionally use service/hub wallets as recurring counterparts.
        in_ids = []
        for _ in range(n_in):
            if service and rng.random() < 0.08:
                idx = rng.choice(service)
            elif hub and rng.random() < reuse["hub_spend_rate"]:
                idx = rng.choice(hub)
            else:
                idx = choose_weighted_index(rng, normal_limit, reuse["zipf_alpha_wallets"])
            if idx not in in_ids:
                in_ids.append(idx)
        while len(in_ids) < n_in:
            idx = rng.randrange(normal_limit)
            if idx not in in_ids:
                in_ids.append(idx)

        out_ids = []
        for _ in range(n_out):
            if service and rng.random() < reuse["service_output_rate"]:
                idx = rng.choice(service)
            else:
                idx = rng.randrange(normal_limit)
            if idx not in out_ids:
                out_ids.append(idx)
        while len(out_ids) < n_out:
            idx = rng.randrange(normal_limit)
            if idx not in out_ids:
                out_ids.append(idx)

        median = amount_cfg["median_btc"]
        sigma = amount_cfg["sigma"]
        amount = min(amount_cfg["max_btc"], max(0.0005, rng.lognormvariate(math.log(median), sigma)))
        # 8-12 input consolidations are allowed to be genuinely large.
        if n_in >= 8:
            amount = min(amount_cfg["max_btc"], max(amount, rng.uniform(2, 25)))

        total_sat = max(amount_cfg["min_input_sat"], int(round(amount * config.SAT_PER_BTC)))
        # Split input value across inputs with a Dirichlet-like exponential draw.
        weights = [max(0.01, rng.expovariate(1.0)) for _ in range(n_in)]
        wsum = sum(weights)
        inputs = [max(1, int(total_sat * w / wsum)) for w in weights]
        inputs[-1] += total_sat - sum(inputs)

        fee = max(1, int((11 + n_in * 68 + n_out * 31) * rng.uniform(4, 26)))
        if fee >= total_sat:
            fee = max(1, total_sat // 1000)
        available = total_sat - fee
        # Output weights, with occasional dust/change-like small output.
        oweights = [max(0.05, rng.expovariate(1.0)) for _ in range(n_out)]
        osum = sum(oweights)
        outputs = [max(1, int(available * w / osum)) for w in oweights]
        outputs[-1] += available - sum(outputs)
        if outputs[-1] <= 0:
            outputs[-1] = 1
            outputs[0] = max(1, outputs[0]-1)

        src_idx = choose_weighted_index(rng, ips.size, config.BACKGROUND_DEFAULTS["reuse"]["zipf_alpha_ips"])
        dst_idx = rng.randrange(ips.size)
        if dst_idx == src_idx:
            dst_idx = (dst_idx + 1) % ips.size

        script_weights = config.script_type_weights(
            {"script_type_drift": config.SCRIPT_TYPE_DRIFT}, day, days
        )
        script_type = config.ALLOWED_SCRIPT_TYPES[config.weighted_choice(rng, script_weights)]
        if rng.random() < shape["op_return_rate"]:
            script_type = "OP_RETURN"

        rec = make_record(
            timestamp=ts,
            src_ip_idx=src_idx,
            dst_ip_idx=dst_idx,
            input_wallet_indices=in_ids,
            output_wallet_indices=out_ids,
            input_sats=inputs,
            output_sats=outputs,
            rng=rng,
            script_type=script_type,
            tx_namespace=f"background:{i}",
        )
        records.append(rec)
        truth.append({
            "family": "A",
            "instance_id": "",
            "role": "background",
            "label_strength": "weak",
            "expected_signals": "",
            "expected_pattern_kind": "none",
            "contamination_note": "",
            "wallet_indices": sorted(set(in_ids + out_ids)),
            "ip_indices": sorted(set([src_idx, dst_idx])),
        })

    # A small number of explicit benign extremes helps calibration.
    # They are still ordinary A records, not separate scenario labels.
    return records, truth
