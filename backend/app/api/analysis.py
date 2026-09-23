from fastapi import APIRouter, HTTPException
from app.services.analysis import AnalysisError, analysis_service

router=APIRouter(prefix='/api/v1/analysis')

@router.get('/stages')
def stages(): return analysis_service.status()['stages']

@router.get('/result')
def result():
    try: return analysis_service.get_state().summary | {'stages':analysis_service.get_state().stages}
    except AnalysisError as e: raise HTTPException(500,str(e)) from e

@router.post('/run')
def run():
    try:
        s=analysis_service.run(force=True)
        return s.stages
    except AnalysisError as e: raise HTTPException(500,str(e)) from e

@router.get('/status')
def status(): return analysis_service.status()
