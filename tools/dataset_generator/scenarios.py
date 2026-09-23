"""Scenario families B-H for the SIH 26146 synthetic corpus.

The routines return records plus generator-side bookkeeping. They never write
files and never expose scenario labels in canonical records.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple
import math

try:
    from . import config
except ImportError:
    import config  # type: ignore

@dataclass
class ScenarioContext:
    entities: object
    make_record: Callable
    master_seed: int
    start_epoch: int
    days: int

def _wallet(ctx, idx): return ctx.entities.wallet_pool.wallet(idx).address
def _ip_count(ctx): return ctx.entities.ip_pool.size
def _safe_ip(ctx, idx): return idx % ctx.entities.ip_pool.size

def _instance_day(ctx, family, number):
    # Spread families through the window and intentionally overlap days.
    seed = config.sub_seed(ctx.master_seed, "scenario-day", f"{family}-{number}")
    return seed % max(1, ctx.days)

def _instance_truth(family, iid, role, strength, signals, pattern, note, wallets, ips):
    return {
        "family": family, "instance_id": iid, "role": role,
        "label_strength": strength, "expected_signals": signals,
        "expected_pattern_kind": pattern, "contamination_note": note,
        "wallet_indices": sorted(set(wallets)), "ip_indices": sorted(set(ips)),
    }

def _wallet_range(ctx, start):
    size=ctx.entities.wallet_pool.size
    return range(min(start,max(0,size-1)), size)

def _pick_unique(rng, pool, n):
    if n >= len(pool): return list(pool)
    return rng.sample(list(pool), n)

def _ordinary_amounts(rng, n, lo=0.01, hi=3.0):
    return [max(1, int(rng.uniform(lo, hi) * config.SAT_PER_BTC)) for _ in range(n)]

def _add_record(ctx, records, truth, *, family, iid, role, strength, signals, pattern, note,
                ts, src, dst, ins, outs, in_sats, out_sats, rng, script="P2WPKH"):
    ts=min(ts, ctx.start_epoch + ctx.days*86400 - 1)
    rec = ctx.make_record(
        timestamp=ts, src_ip_idx=src, dst_ip_idx=dst,
        input_wallet_indices=ins, output_wallet_indices=outs,
        input_sats=in_sats, output_sats=out_sats, rng=rng,
        script_type=script, tx_namespace=f"{family}:{iid}:{len(records)}",
    )
    records.append(rec)
    truth.append(_instance_truth(family, iid, role, strength, signals, pattern, note, ins+outs, [src,dst]))
    return rec

def _fill_simple(ctx, records, truth, target, family, iid, wallets, ip_choices, rng, base_ts,
                 signals="", pattern="none", strength="weak", note=""):
    """Fill the current instance until its absolute target record count is reached."""
    j = 0
    while len(records) < target:
        a = rng.choice(wallets); b = rng.choice(wallets)
        if a == b:
            b = wallets[(wallets.index(a)+1) % len(wallets)]
        val = max(10000, int(rng.uniform(0.02, 2.5)*config.SAT_PER_BTC))
        fee = max(1, int(rng.uniform(5, 20) * (11+68+31)))
        out = max(1, val-fee)
        src = rng.choice(ip_choices); dst = rng.choice(ip_choices)
        if src == dst: dst = (dst+1) % ctx.entities.ip_pool.size
        _add_record(ctx, records, truth, family=family, iid=iid, role="scenario_support",
                    strength=strength, signals=signals, pattern=pattern, note=note,
                    ts=base_ts+j*173+rng.randrange(90), src=src, dst=dst,
                    ins=[a], outs=[b], in_sats=[val], out_sats=[out], rng=rng)
        j += 1

def generate_velocity(ctx, count, instances=14):
    rng=config.make_rng(ctx.master_seed,"scenario-family","B")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"B-{k+1:02d}"; instance_start=len(records); day=_instance_day(ctx,"B",k)
        base=ctx.start_epoch+day*86400
        core=_pick_unique(rng, range(0, min(ctx.entities.wallet_pool.size,12000)), rng.randint(1,3))
        counterpart=_pick_unique(rng, range(100, min(ctx.entities.wallet_pool.size,12000)), rng.randint(20, min(40, max(20,ctx.entities.wallet_pool.size-100))))
        wallets=core+counterpart
        ips=_pick_unique(rng, range(ctx.entities.ip_pool.size), rng.randint(1,2))
        n_bursts=rng.randint(2,6)
        made=0
        for b in range(n_bursts):
            burst_start=base+rng.randint(8*3600,20*3600)
            burst_n=min(target-made,rng.randint(20,80))
            for q in range(burst_n):
                if made>=target: break
                a=rng.choice(core); outs=[rng.choice(counterpart)]
                val=max(1,int(rng.uniform(.01,3)*config.SAT_PER_BTC))
                fee=max(1,int(rng.uniform(5,20)*(11+68+31))); out=max(1,val-fee)
                src=rng.choice(ips); dst=rng.choice(ips)
                if src==dst: dst=(dst+1)%ctx.entities.ip_pool.size
                _add_record(ctx,records,truth,family="B",iid=iid,role="scenario_core",
                    strength="strong",signals="temporal",pattern="none",note="",
                    ts=burst_start+q*rng.randint(10,120),src=src,dst=dst,ins=[a],outs=outs,
                    in_sats=[val],out_sats=[out],rng=rng)
                made+=1
            if made>=target: break
        _fill_simple(ctx,records,truth,instance_start+target,"B",iid,wallets,ips,rng,base,"temporal","strong")
    return records,truth

def generate_multihop(ctx,count,instances=12):
    rng=config.make_rng(ctx.master_seed,"scenario-family","C")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"C-{k+1:02d}"; instance_start=len(records); day=_instance_day(ctx,"C",k); base=ctx.start_epoch+day*86400
        chains=max(1,min(7,target//6)); made=0
        for c in range(chains):
            hops=rng.randint(5,9)
            ws=_pick_unique(rng,_wallet_range(ctx,200),hops+1)
            ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(2,5))
            value=max(1,int(rng.uniform(.5,12)*config.SAT_PER_BTC))
            t=base+rng.randint(0,20*3600)
            for h in range(hops):
                if made>=target: break
                inp=ws[h]; out=ws[h+1]
                fee=max(1,int(rng.uniform(5,18)*(11+68+31)))
                keep=max(1,int(value*(1-rng.uniform(.001,.02))))
                total=max(value,keep+fee)
                src=ips[h%len(ips)]; dst=ips[(h+1)%len(ips)]
                _add_record(ctx,records,truth,family="C",iid=iid,role="scenario_core",
                    strength="strong",signals="flow,temporal",pattern="multi_hop",
                    note="shares_ip_with_G" if k%4==0 else "",
                    ts=t,src=src,dst=dst,ins=[inp],outs=[out],
                    in_sats=[total],out_sats=[keep],rng=rng)
                value=keep;t+=rng.randint(30,600);made+=1
            if made>=target: break
        wallets=list(set([x for x in range(max(0,0))]))  # bookkeeping comes from truth
        _fill_simple(ctx,records,truth,instance_start+target,"C",iid,
                     _pick_unique(rng,_wallet_range(ctx,200),min(30,ctx.entities.wallet_pool.size-200)),
                     list(range(ctx.entities.ip_pool.size)),rng,base,"flow,temporal","strong")
    return records,truth

def generate_peeling(ctx,count,instances=15):
    rng=config.make_rng(ctx.master_seed,"scenario-family","D")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"D-{k+1:02d}"; instance_start=len(records); day=_instance_day(ctx,"D",k); base=ctx.start_epoch+day*86400
        hops=min(max(5,target),rng.randint(5,12))
        ws=_pick_unique(rng,_wallet_range(ctx,500),2*hops+1)
        ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(1,3))
        value=max(1,int(rng.uniform(1,20)*config.SAT_PER_BTC)); t=base+rng.randint(0,12*3600)
        made=0
        for h in range(hops):
            if made>=target: break
            spine_in=ws[2*h]; forward=ws[2*h+1]; change=ws[2*h+2]
            reduction=rng.uniform(.03,.15)
            forwarded=max(int(value*(1-reduction)),100000)
            fee=max(1,int(rng.uniform(5,20)*(11+68+62)))
            total=max(value,forwarded+fee+100000)
            change_val=max(1,total-forwarded-fee)
            src=ips[h%len(ips)];dst=ips[(h+1)%len(ips)]
            _add_record(ctx,records,truth,family="D",iid=iid,role="scenario_core",
                strength="strong" if k<12 else "weak",signals="flow,transaction,temporal",
                pattern="peeling",note="near_threshold" if k<3 else "",
                ts=t,src=src,dst=dst,ins=[spine_in],outs=[forward,change],
                in_sats=[total],out_sats=[forwarded,change_val],rng=rng)
            value=forwarded;t+=rng.randint(120,600) if k%5!=0 else rng.randint(3600,14400);made+=1
        _fill_simple(ctx,records,truth,instance_start+target,"D",iid,
                     _pick_unique(rng,_wallet_range(ctx,500),min(50,ctx.entities.wallet_pool.size-500)),
                     ips,rng,base,"flow,transaction,temporal","strong")
    return records,truth

def generate_mixing(ctx,count,instances=8):
    rng=config.make_rng(ctx.master_seed,"scenario-family","E")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"E-{k+1:02d}"; instance_start=len(records); day=_instance_day(ctx,"E",k); base=ctx.start_epoch+day*86400
        ins_count=rng.randint(5,12); out_count=rng.randint(6,15)
        ins=_pick_unique(rng,_wallet_range(ctx,1000),ins_count)
        outs=_pick_unique(rng,_wallet_range(ctx,1500),out_count)
        ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(3,10))
        made=0; t=base+rng.randint(8*3600,18*3600)
        # consolidation
        total=max(1,int(rng.uniform(4,20)*config.SAT_PER_BTC))
        vals=_ordinary_amounts(rng,len(ins),lo=.1,hi=3)
        total=sum(vals)
        fee=max(1,int(rng.uniform(8,25)*(11+68*ins_count+31)))
        main=max(1,total-fee)
        _add_record(ctx,records,truth,family="E",iid=iid,role="scenario_core",
            strength="weak" if k in (0,1) else "strong",signals="graph,flow",
            pattern="fan_in",note="benign_batch_payout" if k in (0,1) else "",
            ts=t,src=ips[0],dst=ips[1],ins=ins,outs=[outs[0]],
            in_sats=vals,out_sats=[main],rng=rng);made+=1;t+=rng.randint(300,1800)
        base_chunk=max(100000,int(main/out_count))
        # distribution groups
        while made<target:
            group_outs=_pick_unique(rng,outs,min(out_count,len(outs)))
            if not group_outs: break
            chunk=max(10000,base_chunk)
            outvals=[]
            for _ in group_outs:
                outvals.append(max(1,int(chunk*rng.uniform(.9,1.1))))
            inp=sum(outvals)+max(1,int(rng.uniform(5,20)*(11+68+31)))
            fee=inp-sum(outvals)
            if fee<=0: fee=1; inp=sum(outvals)+fee
            a=rng.choice(ins)
            src=rng.choice(ips);dst=rng.choice(ips)
            if src==dst: dst=(dst+1)%ctx.entities.ip_pool.size
            _add_record(ctx,records,truth,family="E",iid=iid,role="scenario_core",
                strength="weak" if k in (0,1) else "strong",signals="structure,graph,flow",
                pattern="mixing_like",note="benign_batch_payout" if k in (0,1) else "",
                ts=t,src=src,dst=dst,ins=[a],outs=group_outs,in_sats=[inp],out_sats=outvals,rng=rng)
            t+=rng.randint(180,1800);made+=1
        _fill_simple(ctx,records,truth,instance_start+target,"E",iid,ins+outs,ips,rng,base,
                     "structure,graph,flow","mixing_like","weak" if k in (0,1) else "strong",
                     "benign_batch_payout" if k in (0,1) else "")
    return records,truth

def generate_common_input(ctx,count,instances=20):
    rng=config.make_rng(ctx.master_seed,"scenario-family","F")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"F-{k+1:02d}"; instance_start=len(records); day=_instance_day(ctx,"F",k); base=ctx.start_epoch+day*86400
        group=_pick_unique(rng,_wallet_range(ctx,min(2000,max(200,ctx.entities.wallet_pool.size//2))),rng.randint(3,9))
        ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(1,3) if k%4 else 3)
        made=0
        for j in range(min(target, rng.randint(6,15))):
            n=rng.randint(3,len(group)); ins=rng.sample(group,n)
            out=rng.choice([x for x in _wallet_range(ctx,min(2000,max(200,ctx.entities.wallet_pool.size//2))) if x not in ins])
            vals=_ordinary_amounts(rng,n,.05,5); total=sum(vals)
            fee=max(1,int(rng.uniform(5,20)*(11+68*n+31))); ov=max(1,total-fee)
            src=ips[j%len(ips)];dst=ips[(j+1)%len(ips)]
            _add_record(ctx,records,truth,family="F",iid=iid,role="scenario_core",
                strength="weak" if k<3 else "strong",signals="graph",
                pattern="fan_in" if n>=5 else "none",
                note="benign_multi_address_user" if k==0 else "",
                ts=min(ctx.start_epoch+ctx.days*86400-1, base+j*rng.randint(3*86400,10*86400)),src=src,dst=dst,
                ins=ins,outs=[out],in_sats=vals,out_sats=[ov],rng=rng)
            made+=1
            if made>=target: break
        _fill_simple(ctx,records,truth,instance_start+target,"F",iid,group+[_ for _ in range(min(2000, max(0, ctx.entities.wallet_pool.size-1)), min(2030, ctx.entities.wallet_pool.size))],
                     ips,rng,base,"graph","weak" if k<3 else "strong",
                     "benign_multi_address_user" if k==0 else "")
    return records,truth

def generate_network(ctx,count,instances=10):
    rng=config.make_rng(ctx.master_seed,"scenario-family","G")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"G-{k+1:02d}"; day=_instance_day(ctx,"G",k); base=ctx.start_epoch+day*86400
        wallet=rng.choice(list(_wallet_range(ctx,min(3000,max(0,ctx.entities.wallet_pool.size//3)))))
        wallet_pool=[wallet]+_pick_unique(rng,_wallet_range(ctx,3000),rng.randint(2,8))
        if k%4==0:
            ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(10,20))
        elif k%4==1:
            ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(4,7))
        elif k%4==2:
            ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(6,12))
        else:
            ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(2,4))
        made=0
        for j in range(target):
            a=wallet if j%3 else rng.choice(wallet_pool)
            b=rng.randrange(ctx.entities.wallet_pool.size)
            if a==b:b=(b+1)%ctx.entities.wallet_pool.size
            val=max(1,int(rng.uniform(.01,5)*config.SAT_PER_BTC))
            fee=max(1,int(rng.uniform(5,20)*(11+68+31)));out=max(1,val-fee)
            src=ips[j%len(ips)];dst=rng.randrange(ctx.entities.ip_pool.size)
            if dst==src:dst=(dst+1)%ctx.entities.ip_pool.size
            script="P2WPKH"
            _add_record(ctx,records,truth,family="G",iid=iid,role="scenario_core",
                strength="strong" if k<2 else "weak",signals="network",
                pattern="none",note="shares_ip_with_C" if k==0 else "",
                ts=base+rng.randint(0,6*3600)+j*30,src=src,dst=dst,
                ins=[a],outs=[b],in_sats=[val],out_sats=[out],rng=rng,script=script)
            made+=1
        # No filler needed because loop is exact.
    return records,truth

def generate_dense(ctx,count,instances=6):
    rng=config.make_rng(ctx.master_seed,"scenario-family","H")
    records=[]; truth=[]
    per=[count//instances]*instances
    for i in range(count%instances): per[i]+=1
    for k,target in enumerate(per):
        iid=f"H-{k+1:02d}"; day=_instance_day(ctx,"H",k); base=ctx.start_epoch+day*86400
        members=_pick_unique(rng,_wallet_range(ctx,min(4000,max(0,ctx.entities.wallet_pool.size//3))),rng.randint(40, min(120, max(40, ctx.entities.wallet_pool.size // 4))))
        ips=_pick_unique(rng,range(ctx.entities.ip_pool.size),rng.randint(2,4))
        made=0
        while made<target:
            a,b=rng.sample(members,2)
            n_in=rng.choices([1,2,3,4],[.45,.30,.18,.07])[0]
            ins=_pick_unique(rng,members,n_in)
            outs=[b] if n_in==1 else _pick_unique(rng,members,rng.randint(1,4))
            val=max(1,int(rng.uniform(.01,50)*config.SAT_PER_BTC))
            fee=max(1,int(rng.uniform(5,25)*(11+68*n_in+31*len(outs))))
            out_total=max(1,val-fee)
            # Split output value.
            vals=[max(1,int(out_total/len(outs))) for _ in outs]
            vals[-1]+=out_total-sum(vals)
            src=rng.choice(ips);dst=rng.choice(ips)
            if src==dst:dst=(dst+1)%ctx.entities.ip_pool.size
            in_weights=[max(0.1,rng.random()) for _ in ins]
            in_vals=[max(1,int(val*w/sum(in_weights))) for w in in_weights]
            in_vals[-1]+=val-sum(in_vals)
            _add_record(ctx,records,truth,family="H",iid=iid,role="scenario_core",
                strength="weak",signals="graph",pattern="none",
                note="contains_embedded_C" if k==0 else "",
                ts=base+rng.randint(0,max(1,ctx.days*86400-1)),src=src,dst=dst,
                ins=ins,outs=outs,in_sats=in_vals,out_sats=vals,rng=rng)
            made+=1
    return records,truth

FAMILY_GENERATORS = {
    "B": generate_velocity,
    "C": generate_multihop,
    "D": generate_peeling,
    "E": generate_mixing,
    "F": generate_common_input,
    "G": generate_network,
    "H": generate_dense,
}
