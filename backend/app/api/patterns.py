from fastapi import APIRouter, HTTPException
from app.services.analysis import analysis_service
router=APIRouter(prefix='/api/v1/patterns')
@router.get('')
def patterns(): return analysis_service.get_state().patterns
@router.get('/{pattern_id}')
def pattern(pattern_id:str):
    for x in analysis_service.get_state().patterns:
        if x['id']==pattern_id:return x
    raise HTTPException(404,'Pattern not found')
