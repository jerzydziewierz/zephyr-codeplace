"""PC samples -> time per function, per library and per memory window; executed cache lines."""

import bisect
from collections import Counter, defaultdict


def load_pcs(path):
    """One hex PC per line."""
    with open(path) as f:
        return [int(x, 16) for x in f if x.strip()]


def attribute(secs, pcs, line):
    """(samples per section index, set of executed lines per index, samples outside all sections)."""
    starts = [s.addr for s in secs]
    per, lines, outside = Counter(), defaultdict(set), 0
    for pc in pcs:
        i = bisect.bisect_right(starts, pc) - 1
        if i >= 0 and pc < secs[i].addr + secs[i].size:
            per[i] += 1
            lines[i].add(pc // line)
        else:
            outside += 1
    return per, lines, outside


def line_weights(secs, profiles, line, cap=None):
    """{index in secs: {line offset from the section start: weight}} merged over profiles.

    profiles: [(image secs, pcs)]; the images may be linked differently (sections are matched by
    name and object). Weight = samples per 100k samples, maximum over profiles, optionally capped."""
    key = {(s.name, s.path): i for i, s in enumerate(secs)}
    out = defaultdict(lambda: defaultdict(float))
    for isecs, pcs in profiles:
        starts = [s.addr for s in isecs]
        cnt = Counter()
        for pc in pcs:
            i = bisect.bisect_right(starts, pc) - 1
            if i >= 0 and pc < isecs[i].addr + isecs[i].size and isecs[i].name.startswith(".text"):
                cnt[(i, pc // line - isecs[i].addr // line)] += 1
        for (i, r), c in cnt.items():
            j = key.get((isecs[i].name, isecs[i].path))
            if j is not None:
                w = c * 1e5 / len(pcs)
                out[j][r] = max(out[j][r], min(w, cap) if cap else w)
    return out


def report(secs, pcs, line, windows, lib_of, idle_names=(), top=40):
    """Text report: shares per window, per library and per section, of all and of busy samples."""
    per, lines, outside = attribute(secs, pcs, line)
    n = len(pcs)
    idle = sum(c for i, c in per.items() if secs[i].name in idle_names)
    busy = max(n - idle, 1)
    out = [f"{n} samples, {outside} outside the code windows, idle {100 * idle / n:.1f} % ({', '.join(idle_names) or 'none'})"]
    out.append("busy share per window:")
    for lo, hi in windows:
        c = sum(c for i, c in per.items() if lo <= secs[i].addr < hi and secs[i].name not in idle_names)
        out.append(f"  {100 * c / busy:5.1f} %  0x{lo:08x}-0x{hi:08x}")
    bylib = Counter()
    for i, c in per.items():
        if secs[i].name not in idle_names:
            bylib[lib_of(secs[i].path)] += c
    out.append("busy share per library:")
    out += [f"  {100 * c / busy:5.1f} %  {lib}" for lib, c in bylib.most_common(20)]
    out.append("top sections: busy %, size B, executed lines, address, name, library")
    for i, c in per.most_common(top + len(idle_names)):
        s = secs[i]
        if s.name in idle_names:
            continue
        out.append(f"  {100 * c / busy:5.1f}  {s.size:5d}  {len(lines[i]):4d}  0x{s.addr:08x}  {s.name[:48]:48s} {lib_of(s.path)}")
    for k in (1, 3, 10):
        hot = [i for i, c in per.items() if c >= k and secs[i].name not in idle_names]
        out.append(f"sections with >= {k:2d} samples: {len(hot)}, {sum(secs[i].size for i in hot)} B, "
                   f"executed lines {sum(len(lines[i]) for i in hot)} ({line * sum(len(lines[i]) for i in hot)} B)")
    return "\n".join(out), per
