from fastapi import APIRouter, HTTPException
from app.services.analysis import analysis_service
from app.services.graph import GraphService, EntityNotFoundError, GraphDataError
from app.services.investigation_workspace import investigation_workspace

router=APIRouter(prefix="/api/v1/transactions")
graph_service=GraphService()

def _tx(txid: str):
    data=graph_service.transaction_summary(txid,limit=100)
    amount=float(sum(data.get("output_amounts",[])))
    return {"id":txid,"txid":txid,"timestamp":data.get("first_seen"),"amount":amount,"fee":float(data.get("fee") or 0),"scriptType":data.get("script_type") or "P2WPKH","inputAddresses":data.get("input_wallets",[]),"outputAddresses":data.get("output_wallets",[]),"srcIp":(data.get("src_ips") or [""])[0],"dstIp":(data.get("dst_ips") or [""])[0],"srcPort":(data.get("src_ports") or [0])[0],"dstPort":(data.get("dst_ports") or [0])[0],"anomalyScore":0,"relatedWallets":sorted(set(data.get("input_wallets",[]))|set(data.get("output_wallets",[])))}

@router.get("/flow-patterns")
def flow_patterns(): return investigation_workspace.flow_patterns()

@router.get("")
def get_transactions(limit:int=500):
    g=graph_service.get_graph(); out=[]
    for _,a in g.nodes(data=True):
        if a.get("type")!="transaction":continue
        try:out.append(_tx(str(a.get("txid") or a.get("entity_id"))))
        except Exception:continue
        if len(out)>=min(max(limit,1),500):break
    return out

@router.get("/{txid}")
def get_transaction(txid:str):
    try:return _tx(txid)
    except EntityNotFoundError as exc: raise HTTPException(404,str(exc)) from exc
    except GraphDataError as exc: raise HTTPException(500,"Transaction lookup is unavailable") from exc
