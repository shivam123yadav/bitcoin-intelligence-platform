from __future__ import annotations
from typing import Any
import json
import pandas as pd
from app.services.analysis import analysis_service
from app.services.graph import GraphService
from app.services.paths import DEFAULT_DATASET_PATH, DATASET_MANIFEST_PATH, DATASET_VALIDATION_PATH, NORMALIZED_STORAGE_ROOT
from app.services.ingestion import DatasetIngestionService
from app.services.storage import NormalizedDatasetStorage
from app.services.dataset_registry import dataset_registry

graph_service = GraphService()

def _active_catalog_item():
    active = dataset_registry.active_id()
    return dataset_registry.get(active)

def dataset_meta():
    item = _active_catalog_item()
    if item and item.get("source") == "upload":
        return {
            'filename': item.get('filename',''), 'format': item.get('format','csv'),
            'fileSizeBytes': int(item.get('fileSizeBytes',0)), 'records': int(item.get('records',0)),
            'timeRangeStart': item.get('timeRangeStart',''), 'timeRangeEnd': item.get('timeRangeEnd',''),
            'validationStatus': 'valid', 'uploadedAt': item.get('uploadedAt','')
        }
    manifest=json.loads(DATASET_MANIFEST_PATH.read_text(encoding='utf-8'))
    return {
      'filename': DEFAULT_DATASET_PATH.name,'format':'csv','fileSizeBytes':DEFAULT_DATASET_PATH.stat().st_size,
      'records':int(manifest.get('record_count',0)),'timeRangeStart':manifest.get('time_start',''),'timeRangeEnd':manifest.get('time_end',''),
      'validationStatus':'valid' if manifest.get('validation_status')=='PASS' else 'warning','uploadedAt':manifest.get('generated_at',manifest.get('time_start',''))
    }

def dataset_stats():
    item = _active_catalog_item()
    if item and item.get("source") == "upload":
        return {'transactions':int(item.get('uniqueTxids',0)),'wallets':int(item.get('wallets',0)),'ips':int(item.get('ips',0)),'countries':int(item.get('countries',0)),'asns':int(item.get('asns',0)),'validRecords':int(item.get('validRecords',0)),'invalidRecords':int(item.get('invalidRecords',0)),'duplicates':0}
    manifest=json.loads(DATASET_MANIFEST_PATH.read_text(encoding='utf-8')); v=json.loads(DATASET_VALIDATION_PATH.read_text(encoding='utf-8'))
    return {'transactions':int(manifest.get('unique_txids',0)),'wallets':int(manifest.get('wallet_pool_count',0)),'ips':int(manifest.get('ip_pool_count',0)),'countries':int(manifest.get('observed_country_count',0)),'asns':int(manifest.get('observed_asn_count',0)),'validRecords':int(v.get('valid_records',manifest.get('record_count',0))),'invalidRecords':int(v.get('error_count',0)),'duplicates':int(v.get('duplicate_count',0))}

def field_quality():
    data=json.loads((DATASET_VALIDATION_PATH.parent/'field_quality.json').read_text(encoding='utf-8'))
    fields=data.get('fields',data if isinstance(data,(list,dict)) else [])
    total=int(json.loads(DATASET_MANIFEST_PATH.read_text(encoding='utf-8')).get('record_count',0)) or 0
    out=[]
    if isinstance(fields,dict):
      for name, item in fields.items():
        present=int(item.get('present',0)); coverage=round(present/total*100,2) if total else 0; invalid=max(0,total-present); out.append({'field':name,'coverage':coverage,'invalid':invalid,'status':'good' if invalid==0 else 'warning'})
    elif isinstance(fields,list): out=fields
    return out

def preview(page=1,page_size=10):
    import duckdb
    path=NORMALIZED_STORAGE_ROOT/'observations_v1.0.0.duckdb'
    con=duckdb.connect(str(path),read_only=True)
    try:
      offset=max(0,page-1)*page_size
      rows=con.execute(f'''SELECT source_record_id,timestamp,src_ip,dst_ip,src_port,dst_port,txid,input_addresses,output_addresses,input_amounts,output_amounts,fee,script_type FROM observations ORDER BY timestamp,source_record_id LIMIT {page_size} OFFSET {offset}''').df().to_dict('records')
      total=int(con.execute('SELECT COUNT(*) FROM observations').fetchone()[0])
    finally: con.close()
    out=[]
    for r in rows:
      r['id']=int(str(r['source_record_id']).lstrip('R') or 0); r.pop('source_record_id',None)
      for k in ('input_addresses','output_addresses','input_amounts','output_amounts'): r[k]=list(r[k])
      out.append(r)
    return {'rows':out,'total':total,'page':page,'pageSize':page_size}

def wallet_to_frontend(wid):
    s=analysis_service.get_state(); row=s.wallet_features[s.wallet_features.entity_id==wid]
    if row.empty: return None
    r=row.iloc[0]; score=float(r.anomaly_score); p='high' if score>=.7 else 'medium' if score>=.45 else 'low'
    return {'id':wid,'address':wid,'type':'wallet','priority':p,'priorityScore':int(score*100),'investigationStatus':'requires_review' if p!='low' else 'cleared','transactions':int(r.transaction_count),'connectedWallets':0,'observedIps':int(r.unique_ip_count),'countries':int(r.country_count),'clusterId':r.cluster_id,'totalVolumeBtc':float(r.total_volume),'anomalyScore':score,'mlAnomalyLabel':str(r.anomaly_level),'lastActivity':r.last_activity,'firstSeen':r.first_seen,'signals':[], 'countriesList':list(r.countries)}

def ip_to_frontend(iid):
    s=analysis_service.get_state(); row=s.ip_features[s.ip_features.entity_id==iid]
    if row.empty:return None
    r=row.iloc[0]; score='high' if int(r.observation_count)>=100 else 'medium' if int(r.observation_count)>=30 else 'low'
    return {'id':iid,'ip':iid,'asn':r.asns[0] if r.asns else '','country':r.countries[0] if r.countries else '','countryCode':r.countries[0] if r.countries else '','city':'','observations':int(r.observation_count),'relatedWallets':int(r.wallet_count),'relatedTransactions':int(r.transaction_count),'firstSeen':r.first_seen,'lastSeen':r.last_activity,'riskLevel':score}
