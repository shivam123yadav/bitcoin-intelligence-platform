"""Validate that the latest completed analysis can be restored after restart.

This script is intentionally read-only. It does not regenerate the dataset or
run the ML pipeline. It simply imports the AnalysisService singleton and prints
its restored status.
"""
from app.services.analysis import analysis_service

status = analysis_service.status()
print(status)
if status.get("status") != "completed":
    raise SystemExit("No completed analysis run could be restored.")
print("Latest analysis restored successfully without running the pipeline.")
