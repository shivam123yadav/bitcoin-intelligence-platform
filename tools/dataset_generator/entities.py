"""Synthetic entity pools for the SIH 26146 dataset generator.

Source of truth: ``docs/17_SYNTHETIC_DATASET.md``.

Scope - **Section 17 step 2 only** ("Create entities"), i.e. the entity layer that
must exist before any record may be created:

* deterministic wallet addresses with the WA-01 shape and the WA-02 denylist
  redraw (Section 13),
* deterministic observing IP endpoints restricted to the approved
  reserved/documentation ranges, produced through :func:`config.ip_for_index`
  (Section 15 rule 2),
* the per-IP ``(geo_country, asn, organisation)`` mapping built from
  ``config.COUNTRY_ASN_TABLE`` with private ASNs and fictional organisation names
  (Section 15 rule 3; conflict C3 refers to ``metadata/ip_geo_mapping.csv``),
* generator-side entity identifiers (Section 5): bookkeeping for merging and
  ground truth only, never written into a dataset record.

Deliberately **not** implemented in this module: the scenario families
(Section 7 and Section 17 step 4), transaction/observation records
(Sections 2-4), background traffic (step 3), merging and ``source_record_id``
assignment (step 5), ground-truth emission (step 6), the Section 13 validator
(step 7) and CSV/JSON/NDJSON serialization (steps 8-9).  This module creates
entities; it never creates a record.

Determinism (Section 12.1).  Every value derives from the master seed
(:data:`config.MASTER_SEED`, ``26146`` by default) through
:func:`config.sub_seed` / :func:`config.make_rng`, using a stage name plus the
entity's own pool index or IP literal, so no value depends on pool size, call
order or iteration order ("adding a new instance must not change previously
generated instances").

Only the Python standard library is used.  Nothing here reads the network, the
wall clock or any locale-dependent API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

try:  # imported as ``tools.dataset_generator.entities``
    from . import config
except ImportError:  # executed directly from inside the tool directory
    import config  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Stage names used for sub-seed derivation (docs/17 Section 12.1)
# ---------------------------------------------------------------------------

STAGE_ADDRESSES = "entities:addresses"
STAGE_IPS = "entities:ips"
STAGE_GEO = "entities:geo"

# ---------------------------------------------------------------------------
# Generator-side entity identifiers (docs/17 Section 5)
# ---------------------------------------------------------------------------

#: Identity in the dataset is the address literal / IPv4 literal.  These IDs are
#: internal bookkeeping (merge, ground truth, evidence lookup) and are never a
#: canonical field.
KIND_WALLET = "wallet"
KIND_IP = "ip"

WALLET_ID_PREFIX = "W"
IP_ID_PREFIX = "IP"
ENTITY_ID_DIGITS = 6
MAX_POOL_INDEX = (10 ** ENTITY_ID_DIGITS) - 1

KIND_PREFIXES = {KIND_WALLET: WALLET_ID_PREFIX, KIND_IP: IP_ID_PREFIX}

# ---------------------------------------------------------------------------
# Pool defaults (docs/17 Section 8, "SIH demo dataset", the recommended default)
# ---------------------------------------------------------------------------

DEFAULT_WALLET_POOL_SIZE = 12_000  # Section 8: wallets = approx. 12,000
DEFAULT_IP_POOL_SIZE = 3_800  # Section 8: IPs = approx. 3,800

#: WA-02: a denylist collision is redrawn deterministically with the next attempt
#: number.  The address space is 32 ** 38 against a four-entry denylist, so this
#: bound exists to make the behaviour finite and testable, not because it is
#: expected ever to be reached.
ADDRESS_DRAW_ATTEMPTS = 64

#: Private-use ASN range (docs/17 Section 15 rule 3: AS64512-AS65534).
PRIVATE_ASN_MIN = 64512
PRIVATE_ASN_MAX = 65534

#: Number of distinct IP literals :func:`config.ip_for_index` can emit before its
#: private-block index wraps around (three documentation /24s plus
#: ``config.IP_PRIVATE_BLOCKS`` private /24s of ``config.IP_DOC_BLOCK_HOSTS``).
IP_POOL_CAPACITY = (
    len(config.IP_DOCUMENTATION_BLOCKS) * config.IP_DOC_BLOCK_HOSTS
    + config.IP_PRIVATE_BLOCKS * config.IP_DOC_BLOCK_HOSTS
)


class EntityError(ValueError):
    """Raised when an entity pool cannot be built from the given configuration."""


# ---------------------------------------------------------------------------
# Entity identifiers (generator bookkeeping; never a dataset field)
# ---------------------------------------------------------------------------


def entity_id(kind: str, pool_index: int) -> str:
    """Return the generator-side identifier of a pool entry.

    ``"W000007"`` for wallets, ``"IP000007"`` for IP endpoints.  The identifier
    is stable for a ``(kind, pool index)`` pair and independent of pool size.
    ``docs/17`` Section 5 identifies a wallet by its address literal, an IP by its
    IPv4 literal and an observation by ``source_record_id``; this ID is internal
    bookkeeping for merging, ground truth and evidence lookup only.
    """
    prefix = KIND_PREFIXES.get(kind)
    if prefix is None:
        raise EntityError("unknown entity kind: {0!r}".format(kind))
    _check_pool_index(pool_index, "entity identifier")
    return "{0}{1:0{2}d}".format(prefix, pool_index, ENTITY_ID_DIGITS)


def parse_entity_id(text: str) -> Tuple[str, int]:
    """Inverse of :func:`entity_id`; returns ``(kind, pool_index)``."""
    value = str(text).strip()
    for kind in sorted(KIND_PREFIXES):
        prefix = KIND_PREFIXES[kind]
        digits = value[len(prefix):] if value.startswith(prefix) else ""
        if len(digits) == ENTITY_ID_DIGITS and digits.isdigit():
            return kind, int(digits)
    raise EntityError("not a synthetic entity identifier: {0!r}".format(text))


def _check_pool_index(pool_index: int, label: str) -> None:
    """Bound a pool index to the identifier width (also guards pool lookups)."""
    if isinstance(pool_index, bool) or not isinstance(pool_index, int):
        raise EntityError("{0} index must be an int, got {1!r}".format(label, pool_index))
    if pool_index < 0 or pool_index > MAX_POOL_INDEX:
        raise EntityError(
            "{0} index {1} is outside 0..{2}".format(label, pool_index, MAX_POOL_INDEX)
        )

# ---------------------------------------------------------------------------
# Wallet addresses (docs/17 Section 13 WA-01 / WA-02, Section 17 step 2)
# ---------------------------------------------------------------------------


def normalise_denylist(denylist: Optional[Iterable[str]] = None) -> Tuple[str, ...]:
    """Return the WA-02 denylist as an ordered, de-duplicated tuple.

    ``None`` selects :data:`config.PUBLISHED_EXAMPLE_DENYLIST` (the published
    example addresses of ``docs/17`` Sections 2 and 4).  A caller may pass the
    ``address_denylist`` list from ``generator_config.json`` instead, which is how
    the frontend mock-data placeholders are appended without changing code
    (Section 13 WA-02).
    """
    values = config.PUBLISHED_EXAMPLE_DENYLIST if denylist is None else denylist
    cleaned: List[str] = []
    for value in values:
        address = str(value).strip()
        if not address:
            raise EntityError("denylist entries must be non-empty addresses")
        if address not in cleaned:  # small list; keeps the order deterministic
            cleaned.append(address)
    return tuple(cleaned)


def wallet_address(
    master_seed: int = config.MASTER_SEED,
    pool_index: int = 0,
    denylist: Optional[Iterable[str]] = None,
) -> str:
    """Return the deterministic synthetic address at ``pool_index``.

    The literal is ``config.ADDRESS_PREFIX`` followed by
    ``config.ADDRESS_DATA_LEN`` characters of :data:`config.BECH32_CHARSET`
    (WA-01 shape, 42 characters, lowercase, no script-type hypothesis readable
    from the shape) and depends only on the master seed and its own pool index.
    """
    address, _attempt = wallet_address_with_attempt(master_seed, pool_index, denylist)
    return address


def wallet_address_with_attempt(
    master_seed: int = config.MASTER_SEED,
    pool_index: int = 0,
    denylist: Optional[Iterable[str]] = None,
) -> Tuple[str, int]:
    """Like :func:`wallet_address`, but also returns the accepted attempt number.

    Attempt ``0`` means no denylist collision occurred.  A higher number records
    the deterministic redraw required by WA-02; it is stored on the wallet entity
    so a regenerated dataset can prove it redrew identically.
    """
    _check_pool_index(pool_index, "wallet")
    banned = normalise_denylist(denylist)
    blocked = frozenset(banned)
    for attempt in range(ADDRESS_DRAW_ATTEMPTS):
        candidate = _address_candidate(master_seed, pool_index, attempt)
        if candidate not in blocked:
            return candidate, attempt
    raise EntityError(
        "no non-denylisted address for wallet pool index {0} within {1} attempts".format(
            pool_index, ADDRESS_DRAW_ATTEMPTS
        )
    )


def _address_candidate(master_seed: int, pool_index: int, attempt: int) -> str:
    """One deterministic candidate address (WA-01 shape), drawing ``attempt``."""
    rng = config.make_rng(
        master_seed, STAGE_ADDRESSES, "{0}#{1}".format(pool_index, attempt)
    )
    data = "".join(
        rng.choice(config.BECH32_CHARSET) for _ in range(config.ADDRESS_DATA_LEN)
    )
    return config.ADDRESS_PREFIX + data

# ---------------------------------------------------------------------------
# Shared pool-construction helpers
# ---------------------------------------------------------------------------


def _check_count(value: int, label: str, maximum: Optional[int] = None) -> int:
    """Validate a pool size or count and return it (entity-layer guard only)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EntityError("{0} must be an int, got {1!r}".format(label, value))
    if value < 0:
        raise EntityError("{0} must be >= 0, got {1}".format(label, value))
    if maximum is not None and value > maximum:
        raise EntityError(
            "{0} {1} exceeds the maximum {2}".format(label, value, maximum)
        )
    return value


def _resolve_count(override: Optional[int], default: int, label: str) -> int:
    """Take an explicit count when given, otherwise the configured default."""
    return _check_count(
        default if override is None else override, label + " wallet count"
    )


# ---------------------------------------------------------------------------
# Wallet pool (docs/17 Section 5 "Wallet / Address", Section 17 step 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Wallet:
    """One synthetic wallet.

    ``docs/17`` Section 5: a wallet's identity in the dataset is the address
    literal.  ``entity_id`` is generator bookkeeping and ``draw_attempt`` records
    a WA-02 redraw.  ``is_service`` / ``is_hub_spend`` mark the pool indices that
    Section 17 step 2 reserves for background traffic ("the service-like wallets
    used by background traffic"); they are entity-layer flags only and carry no
    record-level behaviour.
    """

    entity_id: str
    address: str
    pool_index: int
    draw_attempt: int = 0
    is_service: bool = False
    is_hub_spend: bool = False

    @property
    def is_background_reserved(self) -> bool:
        """True for the indices the background stage is expected to use."""
        return self.is_service or self.is_hub_spend


class WalletPool:
    """Deterministic pool of synthetic wallet addresses.

    Addresses are produced on demand per pool index and memoised, so any of the
    Section 8 scales can be requested (12,000 wallets at demo scale, about 90,000
    at stress scale) without materialising the pool up front.

    The first :attr:`background_reserved_count` indices
    (:attr:`service_wallet_count` then :attr:`hub_spend_wallet_count`, both taken
    from ``config.BACKGROUND_DEFAULTS["reuse"]`` unless overridden) are reserved
    for background traffic, so a scenario routine drawing its own wallets never
    has to share an index with family A.  If a pool is smaller than that
    configured budget the budget is scaled down proportionally, so a small
    dev/test pool stays constructible; an explicitly supplied count that does not
    fit is an error instead of being reinterpreted.

    Values depend only on the master seed and the wallet's own pool index
    (Section 12.1), so growing the pool, or asking for index 900 before index 3,
    cannot change an address.  Addresses are not compared against each other:
    with 32 ** 38 possible literals a cross-index collision is not a practical
    concern, and duplicate detection over records is the Section 13 validator's
    job, not the entity layer's.
    """

    def __init__(
        self,
        master_seed: int = config.MASTER_SEED,
        size: int = DEFAULT_WALLET_POOL_SIZE,
        denylist: Optional[Iterable[str]] = None,
        service_wallet_count: Optional[int] = None,
        hub_spend_wallet_count: Optional[int] = None,
    ) -> None:
        _check_count(size, "wallet pool size", maximum=MAX_POOL_INDEX + 1)
        reuse = config.BACKGROUND_DEFAULTS["reuse"]
        service = _resolve_count(service_wallet_count, reuse["service_wallets"], "service")
        hub = _resolve_count(
            hub_spend_wallet_count, reuse["hub_spend_wallets"], "hub-spend"
        )
        if service + hub > size:
            if service_wallet_count is not None or hub_spend_wallet_count is not None:
                raise EntityError(
                    "reserved background wallets ({0} service + {1} hub-spend) exceed "
                    "pool size {2}".format(service, hub, size)
                )
            # The configured background budget is a budget, not a contract: a pool
            # smaller than it (only reachable below the documented scales, e.g. a
            # unit-test pool) scales the budget down proportionally instead of
            # failing.  Both documented scales (12,000 and about 90,000 wallets)
            # are far above it and unaffected.
            service, hub = config.largest_remainder(
                size, [float(service), float(hub)]
            )
        self._master_seed = int(master_seed)
        self._size = size
        self._denylist = normalise_denylist(denylist)
        self._service_count = service
        self._hub_spend_count = hub
        self._cache: Dict[int, Wallet] = {}

    # -- introspection ------------------------------------------------------

    @property
    def master_seed(self) -> int:
        """Master seed every address in this pool is derived from."""
        return self._master_seed

    @property
    def size(self) -> int:
        """Number of wallets in the pool."""
        return self._size

    @property
    def denylist(self) -> Tuple[str, ...]:
        """The WA-02 denylist in force for this pool."""
        return self._denylist

    @property
    def service_wallet_count(self) -> int:
        """Leading indices flagged as service-like wallets (family A)."""
        return self._service_count

    @property
    def hub_spend_wallet_count(self) -> int:
        """Indices flagged as hub-spend wallets (family A)."""
        return self._hub_spend_count

    @property
    def background_reserved_count(self) -> int:
        """Length of the leading block reserved for background traffic."""
        return self._service_count + self._hub_spend_count

    def __len__(self) -> int:
        return self._size

    # -- access -------------------------------------------------------------

    def wallet(self, index: int) -> Wallet:
        """Return the wallet at ``index`` (generated once, then memoised)."""
        self._check_index(index)
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        address, attempt = wallet_address_with_attempt(
            self._master_seed, index, self._denylist
        )
        wallet = Wallet(
            entity_id=entity_id(KIND_WALLET, index),
            address=address,
            pool_index=index,
            draw_attempt=attempt,
            is_service=index < self._service_count,
            is_hub_spend=(
                self._service_count <= index < self.background_reserved_count
            ),
        )
        self._cache[index] = wallet
        return wallet

    def address(self, index: int) -> str:
        """Return only the address literal at ``index``."""
        return self.wallet(index).address

    def wallets(self) -> List[Wallet]:
        """All wallets in ascending pool-index order (the only defined order)."""
        return [self.wallet(index) for index in range(self._size)]

    def addresses(self) -> List[str]:
        """All address literals, ascending pool-index order."""
        return [wallet.address for wallet in self.wallets()]

    def service_wallets(self) -> List[Wallet]:
        """The service-like wallets of the leading reserved block."""
        return [self.wallet(index) for index in range(self._service_count)]

    def hub_spend_wallets(self) -> List[Wallet]:
        """The hub-spend wallets, immediately after the service block."""
        return [
            self.wallet(index)
            for index in range(self._service_count, self.background_reserved_count)
        ]

    def __iter__(self) -> Iterator[Wallet]:
        return iter(self.wallets())

    def __repr__(self) -> str:
        return "WalletPool(master_seed={0}, size={1})".format(
            self._master_seed, self._size
        )

    # -- internals ----------------------------------------------------------

    def _check_index(self, index: int) -> None:
        _check_pool_index(index, "wallet")
        if index >= self._size:
            raise EntityError(
                "wallet pool index {0} is outside this pool of {1}".format(
                    index, self._size
                )
            )

# ---------------------------------------------------------------------------
# IP -> (geo_country, asn, organisation) mapping
# (docs/17 Section 15 rule 3, Section 17 step 2, conflict C3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeoEntry:
    """The synthetic geo attribution of one IP endpoint.

    ``geo_country`` is an ISO 3166-1 alpha-2 code, ``asn`` a private-use ASN
    (AS64512-AS65534) and ``asn_org`` a deliberately fictional organisation name
    (Section 15 rule 3).  None of these values describe a real allocation.
    """

    geo_country: str
    asn: int
    asn_org: str

    def as_dict(self) -> Dict[str, object]:
        """Row form for ``metadata/ip_geo_mapping.csv`` (conflict C3)."""
        return {
            "geo_country": self.geo_country,
            "asn": self.asn,
            "asn_org": self.asn_org,
        }


def ipv4_sort_key(ip: str) -> Tuple[int, int, int, int]:
    """Numeric sort key for an IPv4 dotted quad (Section 12.2 stable ordering)."""
    parts = str(ip).strip().split(".")
    if len(parts) != 4:
        raise EntityError("not an IPv4 dotted quad: {0!r}".format(ip))
    octets: List[int] = []
    for part in parts:
        if not part.isdigit() or len(part) > 3 or (len(part) > 1 and part[0] == "0"):
            raise EntityError("not an IPv4 dotted quad: {0!r}".format(ip))
        octet = int(part)
        if octet > 255:
            raise EntityError("not an IPv4 dotted quad: {0!r}".format(ip))
        octets.append(octet)
    return (octets[0], octets[1], octets[2], octets[3])

def normalise_geo_table(table: Optional[Iterable[Iterable[object]]] = None) -> Tuple[Tuple[str, int, str], ...]:
    """Return the ``(country, asn, organisation)`` table as validated tuples.

    ``None`` selects :data:`config.COUNTRY_ASN_TABLE`.  The table is checked
    against the generator's own privacy rules (Section 15 rule 3) - two-letter
    country codes, ASNs inside the private range and non-empty fictional
    organisation names - so a bad configuration fails here rather than producing
    a dataset that contradicts Section 15.
    """
    rows = config.COUNTRY_ASN_TABLE if table is None else table
    entries: List[Tuple[str, int, str]] = []
    for row in rows:
        values = tuple(row)
        if len(values) != 3:
            raise EntityError(
                "geo table rows must be (country, asn, organisation): {0!r}".format(row)
            )
        country, asn, organisation = values
        country_text = str(country).strip().upper()
        if len(country_text) != 2 or not country_text.isalpha():
            raise EntityError(
                "country code must be ISO 3166-1 alpha-2: {0!r}".format(country)
            )
        if isinstance(asn, bool) or not isinstance(asn, int):
            raise EntityError("ASN must be an int: {0!r}".format(asn))
        if asn < PRIVATE_ASN_MIN or asn > PRIVATE_ASN_MAX:
            raise EntityError(
                "ASN {0} is outside the private range {1}-{2}".format(
                    asn, PRIVATE_ASN_MIN, PRIVATE_ASN_MAX
                )
            )
        organisation_text = str(organisation).strip()
        if not organisation_text:
            raise EntityError("organisation name must not be empty (AS{0})".format(asn))
        entries.append((country_text, asn, organisation_text))
    if not entries:
        raise EntityError("geo table must not be empty")
    return tuple(entries)


class IpGeoMap:
    """Deterministic IP -> :class:`GeoEntry` mapping.

    The mapping is produced per IP literal rather than per prefix: that is the
    granularity of the ``metadata/ip_geo_mapping.csv`` artifact named in
    ``docs/17`` conflict C3, and the IP-level country count is a documented
    network feature (Section 7 family G), so two IPs in one /24 must be able to
    differ.

    Selection is uniform over the configured table unless ``concentration_alpha``
    is given, in which case :func:`config.zipf_weights` concentrates the draw -
    the helper the address-reuse realism of Section 14 uses; the caller may pass
    ``config.BACKGROUND_DEFAULTS["reuse"]["zipf_alpha_ips"]``.  Either way a
    mapping depends only on the master seed and the IP literal, so it never
    changes with pool size or query order (Section 12.1).
    """

    def __init__(
        self,
        master_seed: int = config.MASTER_SEED,
        table: Optional[Iterable[Iterable[object]]] = None,
        concentration_alpha: Optional[float] = None,
    ) -> None:
        self._entries = normalise_geo_table(table)
        self._master_seed = int(master_seed)
        if concentration_alpha is not None and float(concentration_alpha) < 0:
            raise EntityError("concentration_alpha must be >= 0")
        self._alpha: Optional[float] = (
            None if concentration_alpha is None else float(concentration_alpha)
        )
        self._cache: Dict[str, GeoEntry] = {}

    @property
    def master_seed(self) -> int:
        """Master seed this mapping is derived from."""
        return self._master_seed

    @property
    def table(self) -> Tuple[Tuple[str, int, str], ...]:
        """The ``(country, asn, organisation)`` rows in use."""
        return self._entries

    @property
    def concentration_alpha(self) -> Optional[float]:
        """Zipf exponent used for the draw, or ``None`` for a uniform draw."""
        return self._alpha

    @property
    def countries(self) -> List[str]:
        """Configured countries, ascending (a determinism-safe key order)."""
        return sorted({entry[0] for entry in self._entries})

    @property
    def asns(self) -> List[int]:
        """Configured private ASNs, ascending (a determinism-safe key order)."""
        return sorted({entry[1] for entry in self._entries})
    # -- access -------------------------------------------------------------

    def for_ip(self, ip: str) -> GeoEntry:
        """Return (and memoise) the geo attribution of one IP literal."""
        literal = str(ip).strip()
        cached = self._cache.get(literal)
        if cached is not None:
            return cached
        rng = config.make_rng(self._master_seed, STAGE_GEO, literal)
        if self._alpha is None:
            weights: List[float] = [1.0] * len(self._entries)
        else:
            weights = config.zipf_weights(len(self._entries), self._alpha)
        country, asn, organisation = self._entries[config.weighted_choice(rng, weights)]
        entry = GeoEntry(geo_country=country, asn=asn, asn_org=organisation)
        self._cache[literal] = entry
        return entry

    def resolved_ips(self) -> List[str]:
        """The IP literals resolved so far, ascending by numeric value."""
        return sorted(self._cache, key=ipv4_sort_key)

    def rows(self, ips: Optional[Iterable[str]] = None) -> List[Dict[str, object]]:
        """CSV-ready rows for ``metadata/ip_geo_mapping.csv`` (conflict C3).

        Each row is ``{"ip", "geo_country", "asn", "asn_org"}``, de-duplicated and
        sorted by numeric IP rather than by insertion order (Section 12.2).  With
        ``ips`` omitted the rows cover the literals already resolved through
        :meth:`for_ip`; pass an explicit iterable (for example the whole IP pool)
        to emit a complete table.
        """
        candidates = self.resolved_ips() if ips is None else list(ips)
        seen = set()
        literals: List[str] = []
        for candidate in candidates:
            literal = str(candidate).strip()
            if literal not in seen:
                seen.add(literal)
                literals.append(literal)
        literals.sort(key=ipv4_sort_key)
        rows: List[Dict[str, object]] = []
        for literal in literals:
            row: Dict[str, object] = {"ip": literal}
            row.update(self.for_ip(literal).as_dict())
            rows.append(row)
        return rows

    def __repr__(self) -> str:
        return "IpGeoMap(master_seed={0}, rows={1}, concentration_alpha={2})".format(
            self._master_seed, len(self._entries), self._alpha
        )


# ---------------------------------------------------------------------------
# IP endpoint pool (docs/17 Section 13 IP-01/IP-02, Section 15 rule 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IpEndpoint:
    """One synthetic observing IP endpoint.

    ``docs/17`` Section 5: identity is the IPv4 literal; ``geo_country``, ``asn``
    and ``asn_org`` are the attributes the dataset carries per observation
    (conflict C3 keeps them supplied *and* re-derivable by offline enrichment).
    The literal is always an observing endpoint and never an address field
    (IP-04).
    """

    entity_id: str
    ip: str
    pool_index: int
    geo_country: str
    asn: int
    asn_org: str

    def as_dict(self) -> Dict[str, object]:
        """Row form for the IP side of ``metadata/ip_geo_mapping.csv``."""
        row: Dict[str, object] = {"entity_id": self.entity_id, "ip": self.ip}
        row.update({"geo_country": self.geo_country, "asn": self.asn, "asn_org": self.asn_org})
        return row


class IpPool:
    """Deterministic pool of observing IP endpoints.

    Literals come from :func:`config.ip_for_index`, which enumerates only the
    approved blocks of Section 15 rule 2: the three documentation /24s
    (``192.0.2.0/24``, ``198.51.100.0/24``, ``203.0.113.0/24``) first, then the
    private ``10.20.k.0/24``, ``172.16.k.0/24`` and ``192.168.k.0/24`` blocks, with
    host octets ``1..254``.  ``src_ip`` and ``dst_ip`` for a record are both drawn
    from this pool by the record-producing stages; this module owns the pool, not
    the pairs, so IP-03 (``src_ip != dst_ip``) is enforced there.

    The pool is capped at :data:`IP_POOL_CAPACITY` distinct literals, because that
    is where :func:`config.ip_for_index` starts reusing literals; a larger request
    is refused rather than silently producing duplicates.

    Endpoints are generated lazily per index and memoised, so the demo scale
    (3,800 IPs) and the stress scale (20,000 IPs) cost nothing until they are
    used.
    """

    def __init__(
        self,
        master_seed: int = config.MASTER_SEED,
        size: int = DEFAULT_IP_POOL_SIZE,
        geo_table: Optional[Iterable[Iterable[object]]] = None,
        concentration_alpha: Optional[float] = None,
    ) -> None:
        if isinstance(size, bool) or not isinstance(size, int):
            raise EntityError("IP pool size must be an int, got {0!r}".format(size))
        if size < 0:
            raise EntityError("IP pool size must be >= 0, got {0}".format(size))
        if size > IP_POOL_CAPACITY:
            raise EntityError(
                "IP pool size {0} exceeds the {1} distinct reserved-range literals "
                "config.ip_for_index can produce before it wraps".format(
                    size, IP_POOL_CAPACITY
                )
            )
        self._master_seed = int(master_seed)
        self._size = size
        self._geo = IpGeoMap(master_seed, geo_table, concentration_alpha)
        self._cache: Dict[int, IpEndpoint] = {}

    # -- introspection ------------------------------------------------------

    @property
    def master_seed(self) -> int:
        """Master seed this pool is derived from."""
        return self._master_seed

    @property
    def size(self) -> int:
        """Number of IP endpoints in the pool."""
        return self._size

    @property
    def geo(self) -> IpGeoMap:
        """The IP -> ``(geo_country, asn, organisation)`` mapping in use."""
        return self._geo

    def __len__(self) -> int:
        return self._size
    # -- access -------------------------------------------------------------

    def ip(self, index: int) -> str:
        """Return the reserved-range IPv4 literal at ``index``.

        The literal comes straight from :func:`config.ip_for_index`, so the
        approved-range guarantee of Section 15 rule 2 is structural rather than
        re-checked here.
        """
        self._check_index(index)
        return config.ip_for_index(index)

    def endpoint(self, index: int) -> IpEndpoint:
        """Return the endpoint at ``index`` (literal plus geo attribution)."""
        self._check_index(index)
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        literal = config.ip_for_index(index)
        entry = self._geo.for_ip(literal)
        endpoint = IpEndpoint(
            entity_id=entity_id(KIND_IP, index),
            ip=literal,
            pool_index=index,
            geo_country=entry.geo_country,
            asn=entry.asn,
            asn_org=entry.asn_org,
        )
        self._cache[index] = endpoint
        return endpoint

    def endpoints(self) -> List[IpEndpoint]:
        """All endpoints in ascending pool-index order (the only defined order)."""
        return [self.endpoint(index) for index in range(self._size)]

    def ips(self) -> List[str]:
        """All IPv4 literals, ascending pool-index order."""
        return [endpoint.ip for endpoint in self.endpoints()]

    def geo_mapping_rows(self) -> List[Dict[str, object]]:
        """``metadata/ip_geo_mapping.csv`` rows for this pool (conflict C3).

        Rows are emitted per IP literal in numeric IP order, not in pool-index
        order, so the artifact is stable however the record stages happened to
        touch the pool (Section 12.2).
        """
        return self._geo.rows(self.ips())

    def __iter__(self) -> Iterator[IpEndpoint]:
        return iter(self.endpoints())

    def __repr__(self) -> str:
        return "IpPool(master_seed={0}, size={1})".format(
            self._master_seed, self._size
        )

    # -- internals ----------------------------------------------------------

    def _check_index(self, index: int) -> None:
        _check_pool_index(index, "IP endpoint")
        if index >= self._size:
            raise EntityError(
                "IP pool index {0} is outside this pool of {1}".format(
                    index, self._size
                )
            )


# ---------------------------------------------------------------------------
# Entity layer of one generator run (docs/17 Section 17 step 2)
# ---------------------------------------------------------------------------


class EntityPools:
    """The complete entity layer for one generator run.

    ``docs/17`` Section 17 step 2 requires the pools to exist before any record
    is created ("No record may be created before its entities exist"), so
    constructing this object is the first thing a run does after reading the
    master seed.  It owns the wallet pool (:attr:`wallet_pool`), the IP endpoint
    pool (:attr:`ip_pool`) and their shared geo mapping, and nothing else: no
    record, no scenario instance, no ground-truth group (Sections 7, 10 and 17
    steps 4-6 own those).
    """

    def __init__(
        self,
        master_seed: int = config.MASTER_SEED,
        wallet_count: int = DEFAULT_WALLET_POOL_SIZE,
        ip_count: int = DEFAULT_IP_POOL_SIZE,
        denylist: Optional[Iterable[str]] = None,
        geo_table: Optional[Iterable[Iterable[object]]] = None,
        service_wallet_count: Optional[int] = None,
        hub_spend_wallet_count: Optional[int] = None,
        concentration_alpha: Optional[float] = None,
    ) -> None:
        self._master_seed = int(master_seed)
        self.wallet_pool = WalletPool(
            master_seed=self._master_seed,
            size=wallet_count,
            denylist=denylist,
            service_wallet_count=service_wallet_count,
            hub_spend_wallet_count=hub_spend_wallet_count,
        )
        self.ip_pool = IpPool(
            master_seed=self._master_seed,
            size=ip_count,
            geo_table=geo_table,
            concentration_alpha=concentration_alpha,
        )

    @property
    def master_seed(self) -> int:
        """Master seed shared by both pools (Sections 12.1, 17 step 1)."""
        return self._master_seed

    @property
    def geo(self) -> IpGeoMap:
        """The IP -> ``(geo_country, asn, organisation)`` mapping in use."""
        return self.ip_pool.geo

    #: Convenience accessors.  The pools themselves are :attr:`wallet_pool` and
    #: :attr:`ip_pool`; these methods are the shortest path for a record stage that
    #: already holds an index.
    def wallet(self, index: int) -> Wallet:
        """Wallet at a wallet-pool index (``wallet_pool.wallet``)."""
        return self.wallet_pool.wallet(index)

    def ip(self, index: int) -> str:
        """IPv4 literal at an IP-pool index (``ip_pool.ip``)."""
        return self.ip_pool.ip(index)

    def endpoint(self, index: int) -> IpEndpoint:
        """IP endpoint (literal plus geo attribution) at an IP-pool index."""
        return self.ip_pool.endpoint(index)

    def counts(self) -> Dict[str, int]:
        """Entity counts for ``metadata/dataset_manifest.json`` (Section 12).

        ``countries`` and ``asns`` are the configured table's totals - the run's
        diversity budget.  The countries and ASNs actually reached by the record
        stream are counted by the manifest step, which already walks the records;
        counting them here would force the whole IP pool to materialise.
        """
        return {
            "wallets": self.wallet_pool.size,
            "ips": self.ip_pool.size,
            "countries": len(self.geo.countries),
            "asns": len(self.geo.asns),
            "service_wallets": self.wallet_pool.service_wallet_count,
            "hub_spend_wallets": self.wallet_pool.hub_spend_wallet_count,
        }

    def __repr__(self) -> str:
        return "EntityPools(master_seed={0}, wallets={1}, ips={2})".format(
            self._master_seed, self.wallet_pool.size, self.ip_pool.size
        )

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ADDRESS_DRAW_ATTEMPTS",
    "DEFAULT_IP_POOL_SIZE",
    "DEFAULT_WALLET_POOL_SIZE",
    "ENTITY_ID_DIGITS",
    "IP_ID_PREFIX",
    "IP_POOL_CAPACITY",
    "KIND_IP",
    "KIND_PREFIXES",
    "KIND_WALLET",
    "MAX_POOL_INDEX",
    "PRIVATE_ASN_MAX",
    "PRIVATE_ASN_MIN",
    "STAGE_ADDRESSES",
    "STAGE_GEO",
    "STAGE_IPS",
    "WALLET_ID_PREFIX",
    "EntityError",
    "EntityPools",
    "GeoEntry",
    "IpEndpoint",
    "IpGeoMap",
    "IpPool",
    "Wallet",
    "WalletPool",
    "entity_id",
    "ipv4_sort_key",
    "normalise_denylist",
    "normalise_geo_table",
    "parse_entity_id",
    "wallet_address",
    "wallet_address_with_attempt",
]
