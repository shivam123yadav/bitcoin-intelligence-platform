# 16 --- Development Rules

## Rule 1 --- Read before changing

Before modifying code, inspect: - PROJECT.md - relevant documentation -
existing implementation - tests

## Rule 2 --- No architecture drift

Do not replace: - FastAPI with another backend framework -
DuckDB/Parquet with a server database without approval - local/offline
ML with cloud AI - existing frontend architecture without approval

## Rule 3 --- No fake backend

Once backend integration begins, do not return hardcoded values merely
to make the frontend look complete.

Mock data may remain in isolated frontend tests/examples but must not be
confused with production analysis output.

## Rule 4 --- Type safety

Use explicit Pydantic and TypeScript types. Avoid blanket `any`.

## Rule 5 --- Explainability

Every investigation lead must be traceable to: - source observations -
derived features - model/pattern findings

## Rule 6 --- Offline operation

Do not require: - OpenAI/Gemini APIs - live blockchain APIs - cloud
databases - cloud GeoIP services

for the core analysis path.

## Rule 7 --- Preserve provenance

Never discard the source-record relationship needed to explain a result.

## Rule 8 --- Validate after changes

At minimum, run relevant: - unit tests - typecheck - build - API tests

## Rule 9 --- Small commits

Prefer one logical change per commit.

## Rule 10 --- Report assumptions

If the data does not support an implementation assumption, stop and
report the uncertainty instead of inventing a format or behavior.

## Rule 11 --- Security

Validate uploaded files and inputs. Do not execute dataset contents.

## Rule 12 --- Investigation terminology

Use neutral analytical language: - anomalous - unusual - candidate -
potential - observed - flagged for review

Avoid unsupported criminal conclusions.
