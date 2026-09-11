"""Union occupied/unavailable time before adding it to a section's CP model.

Two source restrictions may overlap each other; the union blocks work without
incorrectly requiring the restrictions themselves to be mutually exclusive.
"""
from collections import defaultdict


def fixed_intervals(snapshot, lo, hi):
    by_section = defaultdict(list)
    for movement in snapshot.movements:
        margin = movement.get('margin', 0)
        for o in movement['occupancies']:
            by_section[o['section']].append((o['start']-margin, o['end']+margin))
    for r in snapshot.protected_intervals:
        by_section[r['section']].append((r['start'], r['end']))
    for section, intervals in by_section.items():
        merged = []
        for a,b in sorted(intervals):
            a,b = max(lo,a),min(hi,b)
            if a>=b:
                continue
            if merged and a<=merged[-1][1]:
                merged[-1][1]=max(merged[-1][1],b)
            else:
                merged.append([a,b])
        for a,b in merged:
            yield section,a,b
