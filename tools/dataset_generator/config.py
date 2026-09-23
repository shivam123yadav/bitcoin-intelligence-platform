"""Configuration, constants and deterministic helpers for the SIH 26146
synthetic Bitcoin traffic dataset generator.

Source of truth: ``docs/17_SYNTHETIC_DATASET.md``.

This module owns:

* the canonical schema field list and schema-level constants (Section 2),
* the approved IP ranges, countries and private-ASN table (Section 15),
* deterministic sub-seed derivation from the master seed (Section 12),
* exact satoshi / BTC and UTC timestamp formatting shared by the generator and
  the validator,
* the scale configurations (Section 8: dev / demo / stress).

Only the Python standard library is used.  Nothing here reads the network, the
wall clock or any locale-dependent API.
"""

from __future__ import annotations

import hashlib
import json
import random
from decimal import Decimal
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Versions and schema (docs/17 Sections 2, 12)
# ---------------------------------------------------------------------------

MASTER_SEED = 26146  # SIH problem-statement number; docs/17 Section 12
SCHEMA_VERSION = "1"
DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "0.1.0"
CONFIG_VERSION = "1"

#: Canonical field order.  Exactly these 15 fields, in this order, everywhere.
CANONICAL_FIELDS: List[str] = [
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "txid",
    "input_addresses",
    "output_addresses",
    "input_amounts",
    "output_amounts",
    "fee",
    "script_type",
    "geo_country",
    "asn",
    "source_record_id",
]

#: The 14 data fields (everything except the provenance key) used by DU-01.
OBSERVATION_FIELDS: List[str] = [
    f for f in CANONICAL_FIELDS if f != "source_record_id"
]

#: CSV header, exactly once, fixed column order (docs/17 Section 3).
CSV_HEADER = ",".join(CANONICAL_FIELDS)

ALLOWED_SCRIPT_TYPES = (
    "P2PKH",
    "P2SH",
    "P2WPKH",
    "P2WSH",
    "P2TR",
    "MultiSig",
    "OP_RETURN",
)

#: Destination ports approved by PT-03.
APPROVED_DST_PORTS = (8333, 18333, 8332, 18332)
PORT_MIN = 1024
PORT_MAX = 65535

SAT_PER_BTC = 100_000_000
MAX_AMOUNT_SAT = 21_000_000 * SAT_PER_BTC  # AM-03 supply bound
FEE_TOLERANCE_SAT = 1  # AM-05 tolerance is 1e-8 BTC == 1 satoshi
MAX_FEE_RATIO_PERCENT = 5  # AM-07

#: docs/17 Section 15 rule 2 - the only IP blocks the dataset may use.
RESERVED_IP_RANGES = (
    "192.0.2.0/24",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)

#: docs/17 Section 15 rule 3 - synthetic countries and private ASNs with
#: clearly fictional organisation names (AS64512-AS65534 is the private range).
COUNTRY_ASN_TABLE = (
    ('AU', 64512, 'Synthetic AU Transit Cooperative 1'),
    ('AU', 64513, 'Synthetic AU Transit Cooperative 2'),
    ('BR', 64514, 'Synthetic BR Transit Cooperative 1'),
    ('BR', 64515, 'Synthetic BR Transit Cooperative 2'),
    ('CA', 64516, 'Synthetic CA Transit Cooperative 1'),
    ('CA', 64517, 'Synthetic CA Transit Cooperative 2'),
    ('DE', 64518, 'Synthetic DE Transit Cooperative 1'),
    ('DE', 64519, 'Synthetic DE Transit Cooperative 2'),
    ('FR', 64520, 'Synthetic FR Transit Cooperative 1'),
    ('FR', 64521, 'Synthetic FR Transit Cooperative 2'),
    ('GB', 64522, 'Synthetic GB Transit Cooperative 1'),
    ('GB', 64523, 'Synthetic GB Transit Cooperative 2'),
    ('IN', 64524, 'Synthetic IN Transit Cooperative 1'),
    ('IN', 64525, 'Synthetic IN Transit Cooperative 2'),
    ('JP', 64526, 'Synthetic JP Transit Cooperative 1'),
    ('JP', 64527, 'Synthetic JP Transit Cooperative 2'),
    ('NL', 64528, 'Synthetic NL Transit Cooperative 1'),
    ('NL', 64529, 'Synthetic NL Transit Cooperative 2'),
    ('SG', 64530, 'Synthetic SG Transit Cooperative 1'),
    ('SG', 64531, 'Synthetic SG Transit Cooperative 2'),
    ('US', 64532, 'Synthetic US Transit Cooperative 1'),
    ('US', 64533, 'Synthetic US Transit Cooperative 2'),
    ('ZA', 64534, 'Synthetic ZA Transit Cooperative 1'),
    ('ZA', 64535, 'Synthetic ZA Transit Cooperative 2'),
    ('AE', 64536, 'Synthetic AE Transit Cooperative 1'),
    ('AE', 64537, 'Synthetic AE Transit Cooperative 2'),
    ('AR', 64538, 'Synthetic AR Transit Cooperative 1'),
    ('AR', 64539, 'Synthetic AR Transit Cooperative 2'),
    ('AT', 64540, 'Synthetic AT Transit Cooperative 1'),
    ('AT', 64541, 'Synthetic AT Transit Cooperative 2'),
    ('BE', 64542, 'Synthetic BE Transit Cooperative 1'),
    ('BE', 64543, 'Synthetic BE Transit Cooperative 2'),
    ('CH', 64544, 'Synthetic CH Transit Cooperative 1'),
    ('CH', 64545, 'Synthetic CH Transit Cooperative 2'),
    ('CL', 64546, 'Synthetic CL Transit Cooperative 1'),
    ('CL', 64547, 'Synthetic CL Transit Cooperative 2'),
    ('CN', 64548, 'Synthetic CN Transit Cooperative 1'),
    ('CN', 64549, 'Synthetic CN Transit Cooperative 2'),
    ('CO', 64550, 'Synthetic CO Transit Cooperative 1'),
    ('CO', 64551, 'Synthetic CO Transit Cooperative 2'),
    ('CZ', 64552, 'Synthetic CZ Transit Cooperative 1'),
    ('CZ', 64553, 'Synthetic CZ Transit Cooperative 2'),
    ('DK', 64554, 'Synthetic DK Transit Cooperative 1'),
    ('DK', 64555, 'Synthetic DK Transit Cooperative 2'),
    ('ES', 64556, 'Synthetic ES Transit Cooperative 1'),
    ('ES', 64557, 'Synthetic ES Transit Cooperative 2'),
    ('FI', 64558, 'Synthetic FI Transit Cooperative 1'),
    ('FI', 64559, 'Synthetic FI Transit Cooperative 2'),
    ('GR', 64560, 'Synthetic GR Transit Cooperative 1'),
    ('GR', 64561, 'Synthetic GR Transit Cooperative 2'),
    ('HK', 64562, 'Synthetic HK Transit Cooperative 1'),
    ('HK', 64563, 'Synthetic HK Transit Cooperative 2'),
    ('ID', 64564, 'Synthetic ID Transit Cooperative 1'),
    ('ID', 64565, 'Synthetic ID Transit Cooperative 2'),
    ('IE', 64566, 'Synthetic IE Transit Cooperative 1'),
    ('IE', 64567, 'Synthetic IE Transit Cooperative 2'),
    ('IL', 64568, 'Synthetic IL Transit Cooperative 1'),
    ('IL', 64569, 'Synthetic IL Transit Cooperative 2'),
    ('IT', 64570, 'Synthetic IT Transit Cooperative 1'),
    ('IT', 64571, 'Synthetic IT Transit Cooperative 2'),
    ('KR', 64572, 'Synthetic KR Transit Cooperative 1'),
    ('KR', 64573, 'Synthetic KR Transit Cooperative 2'),
    ('MX', 64574, 'Synthetic MX Transit Cooperative 1'),
    ('MX', 64575, 'Synthetic MX Transit Cooperative 2'),
    ('MY', 64576, 'Synthetic MY Transit Cooperative 1'),
    ('MY', 64577, 'Synthetic MY Transit Cooperative 2'),
    ('NO', 64578, 'Synthetic NO Transit Cooperative 1'),
    ('NO', 64579, 'Synthetic NO Transit Cooperative 2'),
    ('NZ', 64580, 'Synthetic NZ Transit Cooperative 1'),
    ('NZ', 64581, 'Synthetic NZ Transit Cooperative 2'),
    ('PL', 64582, 'Synthetic PL Transit Cooperative 1'),
    ('PL', 64583, 'Synthetic PL Transit Cooperative 2'),
    ('PT', 64584, 'Synthetic PT Transit Cooperative 1'),
    ('PT', 64585, 'Synthetic PT Transit Cooperative 2'),
    ('RO', 64586, 'Synthetic RO Transit Cooperative 1'),
    ('RO', 64587, 'Synthetic RO Transit Cooperative 2'),
    ('SE', 64588, 'Synthetic SE Transit Cooperative 1'),
    ('SE', 64589, 'Synthetic SE Transit Cooperative 2'),
    ('TH', 64590, 'Synthetic TH Transit Cooperative 1'),
    ('TH', 64591, 'Synthetic TH Transit Cooperative 2'),
    ('TR', 64592, 'Synthetic TR Transit Cooperative 1'),
    ('TR', 64593, 'Synthetic TR Transit Cooperative 2'),
    ('UA', 64594, 'Synthetic UA Transit Cooperative 1'),
    ('UA', 64595, 'Synthetic UA Transit Cooperative 2'),
    ('VN', 64596, 'Synthetic VN Transit Cooperative 1'),
    ('VN', 64597, 'Synthetic VN Transit Cooperative 2'),
    ('KE', 64598, 'Synthetic KE Transit Cooperative 1'),
    ('KE', 64599, 'Synthetic KE Transit Cooperative 2'),
    ('NG', 64600, 'Synthetic NG Transit Cooperative 1'),
    ('NG', 64601, 'Synthetic NG Transit Cooperative 2'),
)

COUNTRIES = sorted({entry[0] for entry in COUNTRY_ASN_TABLE})

#: docs/17 Section 13, WA-02.  The four published example addresses from
#: docs/17 Sections 2 and 4.  The list is configurable through
#: ``address_denylist`` in generator_config.json so frontend mock-data
#: placeholders can be appended without touching code.
PUBLISHED_EXAMPLE_DENYLIST = (
    "bc1qk3fz9v2mnt4r7xwq8pd0hay6cj5uslzb1e2g3t4",
    "bc1qq7vd5n8s2w1kre6tx9m4pa0lzjc7hf3byug6dq9",
    "bc1qm2pa4t7k9v2xs1wq8rd0jz6hn5clb3euya7gf2",
    "bc1qt9xw6r3n8s5m2vd1kp9j4lz7hc0byu3feqatg6m",
)

#: Address shape (docs/17 WA-01): "bc1q" + 38 lowercase bech32 data characters.
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
ADDRESS_PREFIX = "bc1q"
ADDRESS_DATA_LEN = 38
ADDRESS_TOTAL_LEN = len(ADDRESS_PREFIX) + ADDRESS_DATA_LEN  # 42

#: IP address space: reserved/documentation blocks only (Section 15 rule 2).
IP_DOCUMENTATION_BLOCKS = ("192.0.2.", "198.51.100.", "203.0.113.")
IP_DOC_BLOCK_HOSTS = 254
IP_PRIVATE_BLOCKS = 768  # 10.20.k.0/24, 172.16.k.0/24, 192.168.k.0/24


def ip_for_index(index: int) -> str:
    """Deterministically map a pool index to a reserved-range IPv4 literal."""
    if index < 0:
        raise ValueError("index must be >= 0")
    doc_capacity = len(IP_DOCUMENTATION_BLOCKS) * IP_DOC_BLOCK_HOSTS
    if index < doc_capacity:
        block, host = divmod(index, IP_DOC_BLOCK_HOSTS)
        return "{0}{1}".format(IP_DOCUMENTATION_BLOCKS[block], host + 1)
    private_index = index - doc_capacity
    block, host = divmod(private_index, IP_DOC_BLOCK_HOSTS)
    block = block % IP_PRIVATE_BLOCKS
    if block < 256:
        prefix = "10.20.{0}.".format(block)
    elif block < 512:
        prefix = "172.16.{0}.".format(block - 256)
    else:
        prefix = "192.168.{0}.".format(block - 512)
    return "{0}{1}".format(prefix, host + 1)

# ---------------------------------------------------------------------------
# Deterministic helpers (docs/17 Section 12)
# ---------------------------------------------------------------------------


def sub_seed(master_seed: int, stage: str, instance_id: str = "") -> int:
    """Derive a stage/instance sub-seed from the master seed.

    Each stage and each scenario instance derives its own generator, so adding
    a new instance never changes previously generated instances (Section 12.1).
    """
    payload = "{0}|{1}|{2}".format(int(master_seed), stage, instance_id)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def make_rng(master_seed: int, stage: str, instance_id: str = "") -> random.Random:
    """Return an independent ``random.Random`` for a stage/instance."""
    return random.Random(sub_seed(master_seed, stage, instance_id))


def weighted_choice(rng: random.Random, weights) -> int:
    """Index choice from a sequence of non-negative weights.

    Implemented on top of ``random.Random.random`` so selection is stable
    across Python versions and never depends on set iteration order.
    """
    total = 0.0
    for weight in weights:
        if weight < 0:
            raise ValueError("negative weight")
        total += weight
    if total <= 0:
        raise ValueError("all weights are zero")
    draw = rng.random() * total
    acc = 0.0
    for index, weight in enumerate(weights):
        acc += weight
        if draw < acc:
            return index
    return len(weights) - 1


def zipf_weights(n: int, alpha: float) -> List[float]:
    """Weights ``1 / (k + 1) ** alpha`` for ``k`` in ``range(n)``."""
    return [1.0 / ((k + 1) ** alpha) for k in range(n)]


def largest_remainder(total: int, weights: List[float]) -> List[int]:
    """Allocate ``total`` units proportionally to weights, exactly.

    Ties break by index, so the allocation is fully reproducible and always
    sums to ``total``.
    """
    if total < 0:
        raise ValueError("total must be >= 0")
    weight_sum = float(sum(weights))
    if weight_sum <= 0:
        raise ValueError("weights must sum to a positive value")
    exact = [total * (w / weight_sum) for w in weights]
    floors = [int(value) for value in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return floors


# ---------------------------------------------------------------------------
# Amount and timestamp formatting (docs/17 Sections 3, 4, 12)
# ---------------------------------------------------------------------------


def fmt_btc(sat: int) -> str:
    """Format integer satoshis as a BTC decimal literal with 8 decimals.

    One canonical formatter is used for CSV and JSON so the round-trips
    required by AR-04 are byte-identical (see config "assumptions").
    """
    if not isinstance(sat, int):
        raise TypeError("sat must be an int")
    sign = "-" if sat < 0 else ""
    sat = abs(sat)
    return "{0}{1}.{2:08d}".format(sign, sat // SAT_PER_BTC, sat % SAT_PER_BTC)


def parse_btc(text: str) -> int:
    """Parse a BTC decimal literal into integer satoshis (exact, no float)."""
    value = Decimal(str(text).strip())
    scaled = value * SAT_PER_BTC
    if scaled != scaled.to_integral_value():
        raise ValueError("more than 8 decimal places: {0!r}".format(text))
    return int(scaled)


def fmt_ts(epoch_seconds: int) -> str:
    """Format an epoch second as ``YYYY-MM-DDTHH:MM:SSZ`` (TS-01)."""
    seconds = int(epoch_seconds)
    days, rem = divmod(seconds, 86400)
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)
    year, month, day = _civil_from_days(days)
    return "{0:04d}-{1:02d}-{2:02d}T{3:02d}:{4:02d}:{5:02d}Z".format(
        year, month, day, hour, minute, second
    )


def parse_ts(text: str) -> int:
    """Parse ``YYYY-MM-DDTHH:MM:SSZ`` into an epoch second."""
    value = str(text).strip()
    if len(value) != 20 or not value.endswith("Z") or value[10] != "T":
        raise ValueError(
            "not an ISO 8601 UTC second-precision timestamp: {0!r}".format(text)
        )
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    hour = int(value[11:13])
    minute = int(value[14:16])
    second = int(value[17:19])
    days = _days_from_civil(year, month, day)
    return days * 86400 + hour * 3600 + minute * 60 + second


def _days_from_civil(year: int, month: int, day: int) -> int:
    """Days since 1970-01-01 (Howard Hinnant's algorithm, integer maths)."""
    y = year - (1 if month <= 2 else 0)
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    mp = (month + 9) % 12
    doy = (153 * mp + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil_from_days(z: int):
    """Inverse of :func:`_days_from_civil`."""
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + (3 if mp < 10 else -9)
    year = y + (1 if month <= 2 else 0)
    return year, month, day


def config_hash(config: Dict[str, Any]) -> str:
    """SHA-256 over the canonical JSON form of a configuration artifact."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def script_type_weights(config: Dict[str, Any], day_index: int, total_days: int) -> List[float]:
    """Interpolate the script-type drift table for one day of the window."""
    drift = config["script_type_drift"]
    fraction = 0.0 if total_days <= 1 else day_index / float(total_days - 1)
    weights = []
    for script_type in ALLOWED_SCRIPT_TYPES:
        start, end = drift[script_type]
        weights.append(start + (end - start) * fraction)
    return weights

# ---------------------------------------------------------------------------
# Scale plans, distributions and family parameters (docs/17 Sections 8, 14)
# ---------------------------------------------------------------------------

#: Diurnal envelope: quiet overnight hours, busy working hours (Section 14).
HOUR_WEIGHTS = (
    0.55, 0.40, 0.30, 0.25, 0.25, 0.30, 0.45, 0.65,
    0.90, 1.15, 1.25, 1.30, 1.25, 1.30, 1.35, 1.40,
    1.35, 1.20, 1.10, 1.05, 1.00, 0.95, 0.85, 0.70,
)

#: 7-day dev window: 2024-11-01 is a Friday, so days 1-2 are the weekend.
DAY_WEIGHTS_7 = (1.10, 0.80, 0.75, 1.30, 1.15, 1.05, 1.60)

#: 30-day demo window day weights (weekends lower, three peak days).
DAY_WEIGHTS_30 = tuple(
    1.25 if (day % 7) in (1, 2) else (1.45 if day in (8, 19, 26) else 1.0)
    for day in range(30)
)

#: Mild realistic script-type drift (Section 14): newer types later.
SCRIPT_TYPE_DRIFT = {
    "P2PKH": (0.20, 0.09),
    "P2SH": (0.09, 0.05),
    "P2WPKH": (0.42, 0.45),
    "P2WSH": (0.06, 0.06),
    "P2TR": (0.12, 0.27),
    "MultiSig": (0.06, 0.04),
    "OP_RETURN": (0.005, 0.004),
}

#: Fee model: virtual size from input/output counts times a sat/vB rate.
FEE_MODEL = {
    "sats_per_vbyte_min": 4.0,
    "sats_per_vbyte_max": 26.0,
    "overhead_vbytes": 11,
    "input_vbytes": 68,
    "output_vbytes": 31,
    "script_type_factor": {
        "P2PKH": 1.15,
        "P2SH": 1.05,
        "P2WPKH": 1.0,
        "P2WSH": 1.08,
        "P2TR": 0.95,
        "MultiSig": 1.30,
        "OP_RETURN": 1.02,
    },
}

#: Per-observation multiplicity: one txid may appear in several rows
#: (docs/17 Section 3, "Multiple observations of one transaction").
PROPAGATION_DEFAULTS = {
    "p_two_observations": 0.035,
    "p_three_observations": 0.005,
    "gap_min_seconds": 1,
    "gap_max_seconds": 300,
}

#: Family A (background) defaults.
BACKGROUND_DEFAULTS: Dict[str, Any] = {
    "amount": {
        "median_btc": 0.05,
        "sigma": 2.2,
        "max_btc": 40.0,
        "min_input_sat": 50000,
        "round_rate": 0.08,
        "dust_rate": 0.01,
        "dust_min_sat": 10000,
        "dust_max_sat": 100000,
    },
    "shape": {
        "p_multi_input": 0.22,
        "p_multi_output": 0.31,
        "p_consolidation": 0.02,
        "p_payout_chain": 0.03,
        "payout_chain_hops_min": 3,
        "payout_chain_hops_max": 4,
        "op_return_rate": 0.004,
        "burst_group_rate": 0.02,
        "burst_size_min": 5,
        "burst_size_max": 15,
        "burst_window_seconds": 600,
        "max_inputs": 12,
        "max_outputs": 4,
    },
    "reuse": {
        "service_output_rate": 0.35,
        "input_reuse_rate": 0.45,
        "hub_spend_rate": 0.06,
        "zipf_alpha_wallets": 0.85,
        "zipf_alpha_ips": 0.70,
        "service_wallets": 45,
        "hub_spend_wallets": 20,
    },
    "benign_extreme": {
        "wallets": 8,
        "amount_min_btc": 8.0,
        "amount_max_btc": 38.0,
        "ips_per_wallet_min": 4,
        "ips_per_wallet_max": 6,
        "burst_txs_min": 6,
        "burst_txs_max": 12,
    },
    "post_scenario_records_per_instance": 3,
}
