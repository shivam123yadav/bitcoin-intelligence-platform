from fastapi import APIRouter, HTTPException

from app.services.analysis import AnalysisError, analysis_service

router = APIRouter(prefix="/api/v1/analysis")


@router.get("/stages")
def stages():
    return analysis_service.status()["stages"]


@router.get("/result")
def result():
    try:
        return analysis_service.result()
    except AnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run")
def run():
    try:
        state = analysis_service.run(force=True)
        return state.stages
    except AnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
def status():
    return analysis_service.status()