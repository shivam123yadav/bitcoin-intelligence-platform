from dataclasses import dataclass
from pathlib import Path
import re

import duckdb
import pandas as pd


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StorageResult:
    duckdb_path: Path
    parquet_path: Path
    record_count: int


class NormalizedDatasetStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, records: pd.DataFrame, dataset_version: str) -> StorageResult:
        safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", dataset_version).strip("._")
        if not safe_version:
            raise StorageError("Dataset version cannot be used in a storage filename")

        self.root.mkdir(parents=True, exist_ok=True)
        duckdb_path = self.root / f"observations_v{safe_version}.duckdb"
        parquet_path = self.root / f"observations_v{safe_version}.parquet"
        duckdb_temp = self.root / f".observations_v{safe_version}.duckdb.tmp"
        parquet_temp = self.root / f".observations_v{safe_version}.parquet.tmp"

        for temporary_path in (duckdb_temp, parquet_temp):
            temporary_path.unlink(missing_ok=True)

        connection = duckdb.connect(str(duckdb_temp))
        try:
            connection.register("normalized_records", records)
            connection.execute(
                """
                CREATE OR REPLACE TABLE observations AS
                SELECT
                    CAST(timestamp AS VARCHAR) AS timestamp,
                    CAST(src_ip AS VARCHAR) AS src_ip,
                    CAST(dst_ip AS VARCHAR) AS dst_ip,
                    CAST(src_port AS BIGINT) AS src_port,
                    CAST(dst_port AS BIGINT) AS dst_port,
                    CAST(txid AS VARCHAR) AS txid,
                    CAST(input_addresses AS VARCHAR[]) AS input_addresses,
                    CAST(output_addresses AS VARCHAR[]) AS output_addresses,
                    CAST(input_amounts AS DOUBLE[]) AS input_amounts,
                    CAST(output_amounts AS DOUBLE[]) AS output_amounts,
                    CAST(fee AS DOUBLE) AS fee,
                    CAST(script_type AS VARCHAR) AS script_type,
                    CAST(geo_country AS VARCHAR) AS geo_country,
                    CAST(asn AS VARCHAR) AS asn,
                    CAST(source_record_id AS VARCHAR) AS source_record_id
                FROM normalized_records
                """
            )
            count_row = connection.execute(
                "SELECT COUNT(*) FROM observations"
            ).fetchone()
            if count_row is None:
                raise StorageError("Normalized storage count query returned no row")
            stored_count = int(count_row[0])
            escaped_parquet_path = str(parquet_temp).replace("'", "''")
            connection.execute(
                f"COPY observations TO '{escaped_parquet_path}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        except Exception as exc:
            raise StorageError("Failed to write normalized analytical storage") from exc
        finally:
            connection.close()

        if stored_count != len(records):
            raise StorageError(
                f"Normalized storage count mismatch: expected {len(records)}, got {stored_count}"
            )

        duckdb_temp.replace(duckdb_path)
        parquet_temp.replace(parquet_path)
        return StorageResult(
            duckdb_path=duckdb_path,
            parquet_path=parquet_path,
            record_count=stored_count,
        )
