#!/usr/bin/env python
"""Task 32(A): field-change test vs Elo-regression, from the refs' own game lists."""
import collections, csv, glob, json, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def load(ref, path=None):
    d = json.loads(Path(path or f'data/episodes-{ref}-raw.json').read_text())
    rows = []
    for ep in d:
        ag = ep.get('agents') or []
        mine = [a for a in ag if str(a.get('submissionId')) == str(ref)]
        if len(ag) != 2 or not mine or any(a.get('reward') is None for a in ag):
            continue
        me = mine[0]; opp = [a for a in ag if a is not me][0]
        rows.append({'end': str(ep.get('endTime')), 'margin': float(me['reward']) - float(opp['reward']),
                     'team': opp.get('teamName'), 'tid': opp.get('teamId'), 'sub': str(opp.get('submissionId')),
                     'idx': int(me.get('index', 0))})
    return sorted(rows, key=lambda r: r['end'])

def seen_before():
    """Opponent submissionIds seen in every OTHER episode snapshot we hold (old builds)."""
    s = set()
    for f in glob.glob('data/episodes-*-raw*.json'):
        if any(x in f for x in ('56523821', '56496301', '56496292')):
            continue
        try:
            for ep in json.loads(Path(f).read_text()):
                for a in (ep.get('agents') or []):
                    s.add(str(a.get('submissionId')))
        except Exception:
            pass
    return s

def main():
    lb = {int(r['teamId']): float(r['score']) for r in json.loads(Path('data/leaderboard.json').read_text()) if r.get('score')}
    ours = next((float(r['score']) for r in json.loads(Path('data/leaderboard.json').read_text()) if r['teamName'] == 'nickyl'), None)
    old = seen_before()
    print(f"our displayed score: {ours}\npreviously-seen opponent submissions: {len(old)}")
    for ref in (56523821, 56496301, 56496292):
        rows = load(ref)
        if not rows:
            continue
        def win(r): return sum(1 for x in r if x['margin'] > 0)
        def stats(r, name):
            sc = [lb.get(int(x['tid'] or 0)) for x in r]
            sc = [s for s in sc if s]
            new = sum(1 for x in r if x['sub'] not in old)
            losses = [x for x in r if x['margin'] < 0]
            above = sum(1 for x in losses if (lb.get(int(x['tid'] or 0)) or 0) > (ours or 0))
            print(f"  {name:12} n={len(r):3} win {100*win(r)/len(r):5.1f}%  margin med {st.median([x['margin'] for x in r]):+7,.0f} "
                  f"mean opp {st.mean(sc) if sc else 0:6.0f} (p10 {sorted(sc)[len(sc)//10] if sc else 0:.0f} p90 {sorted(sc)[-max(1,len(sc)//10)] if sc else 0:.0f}) "
                  f"| new-sub share {100*new/len(r):4.1f}% | losses to >ours {above}/{len(losses)}")
        print(f"\nref {ref}: {len(rows)} games, first {rows[0]['end'][:16]}, last {rows[-1]['end'][:16]}")
        stats(rows, 'ALL')
        stats(rows[-20:], 'last 20')
        stats(rows[-40:], 'last 40')
        stats(rows[:-40], 'earlier')
    print("\n=== cutoff history (data/cmp-track.csv) ===")
    rows = list(csv.DictReader(open('data/cmp-track.csv')))
    for r in rows:
        pass
    days = collections.defaultdict(list)
    for r in rows:
        days[r['utc'][:10]].append(r)
    for d in sorted(days):
        last = days[d][-1]
        print(f"  {d}: teams {last['total']:>5} ours {float(last['ours_score']):7.1f} rank {last['rank']:>5} "
              f"| top1 {last['top1']:>6} top5 {last['top5']:>6} top10 {last['top10']:>6}")
    if len(rows) >= 2:
        print(f"  delta over the history: top1 {float(rows[-1]['top1'])-float(rows[0]['top1']):+.0f}, "
              f"top5 {float(rows[-1]['top5'])-float(rows[0]['top5']):+.0f}, "
              f"top10 {float(rows[-1]['top10'])-float(rows[0]['top10']):+.0f}, "
              f"teams {int(rows[-1]['total'])-int(rows[0]['total']):+d}")

if __name__ == '__main__':
    main()
