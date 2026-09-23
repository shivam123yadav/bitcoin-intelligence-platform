from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from ipaddress import ip_address
import json
import re
from typing import Any

import pandas as pd


CANONICAL_FIELDS = (
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
)

SCRIPT_TYPES = {
    "P2PKH",
    "P2SH",
    "P2WPKH",
    "P2WSH",
    "P2TR",
    "MultiSig",
    "OP_RETURN",
}

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TXID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SOURCE_RECORD_ID_PATTERN = re.compile(r"^R\d{8}$")
PORT_PATTERN = re.compile(r"^\d+$")
ADDRESS_PATTERN = re.compile(r"^bc1q[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{38}$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


@dataclass
class RecordValidationResult:
    record: dict[str, Any] | None
    errors: list[dict[str, Any]]
    missing_fields: set[str]


class RecordValidator:
    def __init__(
        self, time_start: str | None = None, time_end: str | None = None
    ) -> None:
        self.time_start = self._parse_timestamp(time_start) if time_start else None
        self.time_end = self._parse_timestamp(time_end) if time_end else None
        self._seen_source_record_ids: set[str] = set()
        self._seen_observation_keys: set[tuple[Any, ...]] = set()
        self._transaction_fields: dict[str, tuple[Any, ...]] = {}

    def validate(self, row_number: int, values: pd.Series) -> RecordValidationResult:
        errors: list[dict[str, Any]] = []
        missing_fields: set[str] = set()

        source_record_id = self._string_value(
            row_number, values, "source_record_id", errors, missing_fields
        )
        timestamp_value = self._string_value(
            row_number, values, "timestamp", errors, missing_fields
        )
        src_ip = self._string_value(
            row_number, values, "src_ip", errors, missing_fields
        )
        dst_ip = self._string_value(
            row_number, values, "dst_ip", errors, missing_fields
        )
        txid = self._string_value(row_number, values, "txid", errors, missing_fields)
        script_type = self._string_value(
            row_number, values, "script_type", errors, missing_fields
        )
        geo_country = self._string_value(
            row_number, values, "geo_country", errors, missing_fields
        )
        asn = self._string_value(row_number, values, "asn", errors, missing_fields)
        src_port = self._port_value(
            row_number, values, "src_port", errors, missing_fields
        )
        dst_port = self._port_value(
            row_number, values, "dst_port", errors, missing_fields
        )
        fee = self._decimal_value(row_number, values, "fee", errors, missing_fields)
        input_addresses = self._address_array(
            row_number, values, "input_addresses", errors, missing_fields
        )
        output_addresses = self._address_array(
            row_number, values, "output_addresses", errors, missing_fields
        )
        input_amounts = self._amount_array(
            row_number, values, "input_amounts", errors, missing_fields
        )
        output_amounts = self._amount_array(
            row_number, values, "output_amounts", errors, missing_fields
        )

        timestamp: str | None = None
        if timestamp_value is not None:
            timestamp = self._timestamp_value(row_number, timestamp_value, errors)
        if src_ip is not None:
            self._ipv4_value(row_number, src_ip, "src_ip", errors)
        if dst_ip is not None:
            self._ipv4_value(row_number, dst_ip, "dst_ip", errors)
        if src_ip is not None and dst_ip is not None and src_ip == dst_ip:
            self._error(
                row_number,
                source_record_id,
                errors,
                "src_ip,dst_ip",
                "IP-03",
                "Source and destination IPs must differ",
            )
        if txid is not None and not TXID_PATTERN.fullmatch(txid):
            self._error(
                row_number, source_record_id, errors, "txid", "TX-01", "Invalid TXID"
            )
        if script_type is not None and script_type not in SCRIPT_TYPES:
            self._error(
                row_number,
                source_record_id,
                errors,
                "script_type",
                "MV-03",
                "Unsupported script type",
            )
        if geo_country is not None and not COUNTRY_PATTERN.fullmatch(geo_country):
            self._error(
                row_number,
                source_record_id,
                errors,
                "geo_country",
                "MV-01",
                "Invalid country code",
            )
        if source_record_id is not None and not SOURCE_RECORD_ID_PATTERN.fullmatch(
            source_record_id
        ):
            self._error(
                row_number,
                source_record_id,
                errors,
                "source_record_id",
                "DU-03",
                "Invalid source record ID",
            )
        if timestamp is not None and (self.time_start or self.time_end):
            parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if self.time_start and parsed_timestamp < self.time_start:
                self._error(
                    row_number,
                    source_record_id,
                    errors,
                    "timestamp",
                    "TS-02",
                    "Timestamp precedes the dataset window",
                )
            if self.time_end and parsed_timestamp > self.time_end:
                self._error(
                    row_number,
                    source_record_id,
                    errors,
                    "timestamp",
                    "TS-02",
                    "Timestamp follows the dataset window",
                )

        if (
            input_addresses
            and input_amounts
            and len(input_addresses) != len(input_amounts)
        ):
            self._error(
                row_number,
                source_record_id,
                errors,
                "input_addresses,input_amounts",
                "AR-01",
                "Input address and amount lengths differ",
            )
        if (
            output_addresses
            and output_amounts
            and len(output_addresses) != len(output_amounts)
        ):
            self._error(
                row_number,
                source_record_id,
                errors,
                "output_addresses,output_amounts",
                "AR-02",
                "Output address and amount lengths differ",
            )
        if not input_addresses:
            self._error(
                row_number,
                source_record_id,
                errors,
                "input_addresses",
                "AR-03",
                "Input address array is empty or malformed",
            )
        if not output_addresses:
            self._error(
                row_number,
                source_record_id,
                errors,
                "output_addresses",
                "AR-03",
                "Output address array is empty or malformed",
            )
        if fee is not None and fee < 0:
            self._error(
                row_number,
                source_record_id,
                errors,
                "fee",
                "AM-01",
                "Fee must be non-negative",
            )
        if input_amounts and any(amount < 0 for amount in input_amounts):
            self._error(
                row_number,
                source_record_id,
                errors,
                "input_amounts",
                "AM-01",
                "Input amounts must be non-negative",
            )
        if output_amounts and any(amount < 0 for amount in output_amounts):
            self._error(
                row_number,
                source_record_id,
                errors,
                "output_amounts",
                "AM-01",
                "Output amounts must be non-negative",
            )
        if (
            fee is not None
            and input_amounts
            and output_amounts
            and input_addresses is not None
            and output_addresses is not None
            and len(input_amounts) == len(input_addresses)
            and len(output_amounts) == len(output_addresses)
        ):
            expected_fee = sum(input_amounts) - sum(output_amounts)
            if abs(fee - expected_fee) > Decimal("0.00000001"):
                self._error(
                    row_number,
                    source_record_id,
                    errors,
                    "fee",
                    "AM-05",
                    "Fee does not match input minus output amounts",
                )

        if errors:
            return RecordValidationResult(None, errors, missing_fields)

        assert source_record_id is not None
        assert timestamp is not None
        assert src_ip is not None
        assert dst_ip is not None
        assert src_port is not None
        assert dst_port is not None
        assert txid is not None
        assert input_addresses is not None
        assert output_addresses is not None
        assert input_amounts is not None
        assert output_amounts is not None
        assert fee is not None
        assert script_type is not None
        assert geo_country is not None
        assert asn is not None

        observation_key = self._observation_key(
            timestamp,
            src_ip,
            dst_ip,
            src_port,
            dst_port,
            txid,
            input_addresses,
            output_addresses,
            input_amounts,
            output_amounts,
            fee,
            script_type,
            geo_country,
            asn,
        )
        blockchain_key = self._blockchain_key(
            input_addresses,
            output_addresses,
            input_amounts,
            output_amounts,
            fee,
            script_type,
        )
        if source_record_id in self._seen_source_record_ids:
            self._error(
                row_number,
                source_record_id,
                errors,
                "source_record_id",
                "DU-03",
                "Duplicate source record ID",
            )
        if observation_key in self._seen_observation_keys:
            self._error(
                row_number,
                source_record_id,
                errors,
                "source_record_id",
                "DU-01",
                "Duplicate observation",
            )
        previous_blockchain_key = self._transaction_fields.get(txid)
        if (
            previous_blockchain_key is not None
            and previous_blockchain_key != blockchain_key
        ):
            self._error(
                row_number,
                source_record_id,
                errors,
                "txid",
                "TX-02",
                "Conflicting fields for the same TXID",
            )
        if errors:
            return RecordValidationResult(None, errors, missing_fields)

        self._seen_source_record_ids.add(source_record_id)
        self._seen_observation_keys.add(observation_key)
        self._transaction_fields[txid] = blockchain_key
        return RecordValidationResult(
            {
                "timestamp": timestamp,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "txid": txid,
                "input_addresses": input_addresses,
                "output_addresses": output_addresses,
                "input_amounts": [float(amount) for amount in input_amounts],
                "output_amounts": [float(amount) for amount in output_amounts],
                "fee": float(fee),
                "script_type": script_type,
                "geo_country": geo_country,
                "asn": asn,
                "source_record_id": source_record_id,
            },
            errors,
            missing_fields,
        )

    @staticmethod
    def _observation_key(
        timestamp: str,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        txid: str,
        input_addresses: list[str],
        output_addresses: list[str],
        input_amounts: list[Decimal],
        output_amounts: list[Decimal],
        fee: Decimal,
        script_type: str,
        geo_country: str,
        asn: str,
    ) -> tuple[Any, ...]:
        return (
            timestamp,
            src_ip,
            dst_ip,
            src_port,
            dst_port,
            txid,
            tuple(input_addresses),
            tuple(output_addresses),
            tuple(str(amount) for amount in input_amounts),
            tuple(str(amount) for amount in output_amounts),
            str(fee),
            script_type,
            geo_country,
            asn,
        )

    @staticmethod
    def _blockchain_key(
        input_addresses: list[str],
        output_addresses: list[str],
        input_amounts: list[Decimal],
        output_amounts: list[Decimal],
        fee: Decimal,
        script_type: str,
    ) -> tuple[Any, ...]:
        return (
            tuple(input_addresses),
            tuple(output_addresses),
            tuple(str(amount) for amount in input_amounts),
            tuple(str(amount) for amount in output_amounts),
            str(fee),
            script_type,
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp has no timezone")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _string_value(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> str | None:
        try:
            value = str(values[field]).strip()
        except Exception:
            value = ""
        if not value:
            RecordValidator._error(
                row_number, None, errors, field, "MV-01", "Required field is empty"
            )
            missing_fields.add(field)
            return None
        return value

    @staticmethod
    def _port_value(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> int | None:
        value = RecordValidator._string_value(
            row_number, values, field, errors, missing_fields
        )
        if value is None:
            return None
        if not PORT_PATTERN.fullmatch(value):
            RecordValidator._error(
                row_number, None, errors, field, "PT-01", "Port is not an integer"
            )
            return None
        port = int(value)
        if not 1024 <= port <= 65535:
            RecordValidator._error(
                row_number,
                None,
                errors,
                field,
                "PT-01",
                "Port is outside the valid range",
            )
            return None
        return port

    @staticmethod
    def _decimal_value(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> Decimal | None:
        value = RecordValidator._string_value(
            row_number, values, field, errors, missing_fields
        )
        if value is None:
            return None
        try:
            decimal_value = Decimal(value)
        except InvalidOperation:
            RecordValidator._error(
                row_number, None, errors, field, "AM-01", "Value is not numeric"
            )
            return None
        if not decimal_value.is_finite() or decimal_value < 0:
            RecordValidator._error(
                row_number,
                None,
                errors,
                field,
                "AM-01",
                "Value is not a valid non-negative number",
            )
            return None
        return decimal_value

    @staticmethod
    def _timestamp_value(
        row_number: int,
        value: str,
        errors: list[dict[str, Any]],
    ) -> str | None:
        if not TIMESTAMP_PATTERN.fullmatch(value):
            RecordValidator._error(
                row_number,
                None,
                errors,
                "timestamp",
                "TS-01",
                "Timestamp is not UTC ISO 8601",
            )
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            RecordValidator._error(
                row_number,
                None,
                errors,
                "timestamp",
                "TS-01",
                "Timestamp is not parseable",
            )
            return None
        if parsed.tzinfo is None:
            RecordValidator._error(
                row_number,
                None,
                errors,
                "timestamp",
                "TS-01",
                "Timestamp has no timezone",
            )
            return None
        return (
            parsed.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _ipv4_value(
        row_number: int,
        value: str,
        field: str,
        errors: list[dict[str, Any]],
    ) -> None:
        try:
            parsed = ip_address(value)
        except ValueError:
            RecordValidator._error(
                row_number, None, errors, field, "IP-01", "IP address is invalid"
            )
            return
        if parsed.version != 4:
            RecordValidator._error(
                row_number, None, errors, field, "IP-01", "IPv4 address is required"
            )

    @staticmethod
    def _address_array(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> list[str] | None:
        parsed = RecordValidator._json_array(
            row_number, values, field, errors, missing_fields
        )
        if parsed is None:
            return None
        result: list[str] = []
        for index, item in enumerate(parsed):
            if not isinstance(item, str) or not ADDRESS_PATTERN.fullmatch(item):
                RecordValidator._error(
                    row_number,
                    None,
                    errors,
                    field,
                    "WA-01",
                    f"Invalid address at position {index}",
                )
                continue
            result.append(item)
        return result

    @staticmethod
    def _amount_array(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> list[Decimal] | None:
        parsed = RecordValidator._json_array(
            row_number, values, field, errors, missing_fields
        )
        if parsed is None:
            return None
        result: list[Decimal] = []
        for index, item in enumerate(parsed):
            if isinstance(item, bool) or not isinstance(item, (str, int, float)):
                RecordValidator._error(
                    row_number,
                    None,
                    errors,
                    field,
                    "AM-01",
                    f"Invalid amount at position {index}",
                )
                continue
            try:
                amount = Decimal(str(item))
            except InvalidOperation:
                RecordValidator._error(
                    row_number,
                    None,
                    errors,
                    field,
                    "AM-01",
                    f"Invalid amount at position {index}",
                )
                continue
            if not amount.is_finite() or amount < 0:
                RecordValidator._error(
                    row_number,
                    None,
                    errors,
                    field,
                    "AM-01",
                    f"Invalid amount at position {index}",
                )
                continue
            if "e" in str(item).lower():
                RecordValidator._error(
                    row_number,
                    None,
                    errors,
                    field,
                    "AM-01",
                    f"Amount uses exponent notation at position {index}",
                )
                continue
            result.append(amount)
        return result

    @staticmethod
    def _json_array(
        row_number: int,
        values: pd.Series,
        field: str,
        errors: list[dict[str, Any]],
        missing_fields: set[str],
    ) -> list[Any] | None:
        value = RecordValidator._string_value(
            row_number, values, field, errors, missing_fields
        )
        if value is None:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            RecordValidator._error(
                row_number,
                None,
                errors,
                field,
                "AR-05",
                "Array field is not valid JSON",
            )
            return None
        if not isinstance(parsed, list):
            RecordValidator._error(
                row_number,
                None,
                errors,
                field,
                "AR-05",
                "Array field is not a JSON array",
            )
            return None
        return parsed

    @staticmethod
    def _error(
        row_number: int,
        source_record_id: str | None,
        errors: list[dict[str, Any]],
        field: str,
        code: str,
        message: str,
    ) -> None:
        errors.append(
            {
                "row_number": row_number,
                "source_record_id": source_record_id,
                "field": field,
                "code": code,
                "message": message,
            }
        )
