#!/usr/bin/env python
"""Task 34: equilibrium estimate (win% by opponent band with Wilson intervals), field census,
cutoff trend, and the basins-vs-convergence check."""
import collections, csv, glob, json, math, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BANDS = [(0,1500),(1500,1800),(1800,2100),(2100,2400),(2400,2700),(2700,10**9)]
def band(s):
    if s is None: return None
    for lo,hi in BANDS:
        if lo<=s<hi: return f"{lo}-{hi if hi<10**9 else '+'}"
    return None
def wilson(w,n,z=1.96):
    if n==0: return (0,0)
    p=w/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0,c-h),min(1,c+h))
def rows(ref):
    out=[]
    for ep in json.loads(Path(f'data/episodes-{ref}-raw.json').read_text()):
        ag=ep.get('agents') or []
        mine=[a for a in ag if str(a.get('submissionId'))==str(ref)]
        if len(ag)!=2 or not mine or any(a.get('reward') is None for a in ag): continue
        me=mine[0]; opp=[a for a in ag if a is not me][0]
        out.append({'m':float(me['reward'])-float(opp['reward']),'tid':int(opp.get('teamId') or 0),
                    'team':opp.get('teamName'),'sub':str(opp.get('submissionId')),'end':str(ep.get('endTime'))})
    return sorted(out,key=lambda r:r['end'])
def main():
    lb_raw=json.loads(Path('data/leaderboard.json').read_text())
    lb={int(r['teamId']):float(r['score']) for r in lb_raw if r.get('score')}
    ours=next((float(r['score']) for r in lb_raw if r['teamName']=='nickyl'),None)
    n_teams=len(lb_raw)
    print(f"our displayed score {ours} | teams {n_teams}")
    print("\n=== (1) PER-BAND WIN RATE + WILSON 95% CI, our recent refs ===")
    allgames=[]
    for ref in (56565204,56533839,56523821,56496301,56496292):
        p=Path(f'data/episodes-{ref}-raw.json')
        if not p.exists(): continue
        rs=rows(ref)
        if not rs: print(f"  ref {ref}: no games"); continue
        allgames+=rs
        by=collections.defaultdict(list)
        for r in rs: by[band(lb.get(r['tid']))].append(r)
        w=sum(1 for r in rs if r['m']>0)
        print(f"\n  ref {ref}: {len(rs)} games, win {100*w/len(rs):.1f}%  (opp mean {st.mean([lb.get(r['tid']) for r in rs if lb.get(r['tid'])])or 0:.0f})")
        cross=None
        for b in [f"{lo}-{hi if hi<10**9 else '+'}" for lo,hi in BANDS]+['unknown']:
            g=by.get(b)
            if not g: continue
            ww=sum(1 for r in g if r['m']>0); n=len(g)
            lo_,hi_=wilson(ww,n)
            print(f"    {b:>10} n={n:3} win {100*ww/n:5.1f}%  CI [{100*lo_:4.1f},{100*hi_:4.1f}]  median margin {st.median([r['m'] for r in g]):+7,.0f}")
            if cross is None and ww/n < 0.5: cross=b
        print(f"    -> first band below 50%: {cross}")
    print("\n=== (1b) repeat beaters (>=2 games, negative total margin vs us) ===")
    h2h=collections.defaultdict(lambda:[0,0.0])
    for r in allgames:
        h2h[(r['team'],lb.get(r['tid']))][0]+=1; h2h[(r['team'],lb.get(r['tid']))][1]+=r['m']
    worst=[(k,v) for k,v in h2h.items() if v[0]>=2 and v[1]<0]
    for (t,s),(n,m) in sorted(worst,key=lambda kv:kv[1][1])[:8]:
        print(f"    {str(t)[:26]:26} score {s if s else 0:6.0f}  n={n:2}  total margin {m:+9,.0f}  mean {m/n:+8,.0f}")
    print("\n=== (2) FIELD CENSUS over all our pulled refs ===")
    seen=set(); teams=collections.Counter(); subs=set()
    for f in glob.glob('data/episodes-*-raw.json'):
        ref=Path(f).name.split('-')[1]
        try: eps=json.loads(Path(f).read_text())
        except Exception: continue
        for ep in eps:
            ag=ep.get('agents') or []
            for a in ag:
                if str(a.get('submissionId'))==str(ref): continue
                teams[int(a.get('teamId') or 0)]+=1; subs.add(str(a.get('submissionId')))
    sc=[lb.get(t) for t in teams if lb.get(t)]
    sc.sort()
    print(f"  distinct opponents {len(teams)}, distinct opponent submissions {len(subs)}, with a leaderboard score {len(sc)}")
    if sc:
        q=lambda p: sc[min(len(sc)-1,int(p*len(sc)))]
        print(f"  opponent score: p10 {q(.10):.0f} p25 {q(.25):.0f} median {q(.50):.0f} p75 {q(.75):.0f} p90 {q(.90):.0f} max {sc[-1]:.0f}")
        print(f"  opponents above our score {sum(1 for s in sc if ours and s>ours)} ({100*sum(1 for s in sc if ours and s>ours)/len(sc):.0f}%)")
    print("\n=== (2b) cutoff trend (cmp-track.csv, per-day last sample) ===")
    rowsx=list(csv.DictReader(open('data/cmp-track.csv')))
    days=collections.defaultdict(list)
    for r in rowsx: days[r['utc'][:10]].append(r)
    prev=None
    for d in sorted(days):
        last=days[d][-1]
        t1,t5,t10=float(last['top1']),float(last['top5']),float(last['top10'])
        dd=f" (d1 {t1-prev[0]:+.0f} d5 {t5-prev[1]:+.0f} d10 {t10-prev[2]:+.0f})" if prev else ""
        print(f"  {d}: teams {last['total']:>5} ours {float(last['ours_score']):7.1f} rank {last['rank']:>5} top1 {t1:.0f} top5 {t5:.0f} top10 {t10:.0f}{dd}")
        prev=(t1,t5,t10)
    print("\n=== (4) basins vs convergence: same-payload instances ===")
    tr=json.loads(Path('data/submission_track.json').read_text())
    for ref,v in sorted(tr.items()):
        s=v.get('samples') or []
        if len(s)<2: continue
        wr=[x['win_rate'] for x in s]; om=[x.get('opp_mean_score') for x in s if x.get('opp_mean_score')]
        print(f"  ref {ref} ({v.get('label','')[:14]:14}) samples {len(s)} win {100*s[0]['win_rate']:.0f}%->{100*wr[-1]:.0f}% "
              f"opp mean {om[0] if om else 0:.0f}->{om[-1] if om else 0:.0f}")
if __name__=='__main__': main()
