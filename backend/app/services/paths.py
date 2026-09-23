from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_ROOT = PROJECT_ROOT / "datasets"
DEFAULT_DATASET_PATH = DATASET_ROOT / "generated" / "synthetic_traffic_v1.0.0.csv"
DATASET_MANIFEST_PATH = DATASET_ROOT / "metadata" / "dataset_manifest.json"
DATASET_VALIDATION_PATH = DATASET_ROOT / "validation" / "validation_report.json"
NORMALIZED_STORAGE_ROOT = PROJECT_ROOT / "backend" / "data" / "normalized"
GRAPH_STORAGE_ROOT = PROJECT_ROOT / "backend" / "data" / "graph"

RUNTIME_STORAGE_ROOT = PROJECT_ROOT / "backend" / "data" / "runtime"
