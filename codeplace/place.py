"""Placement: hot functions to fast memory by name, and cache colouring of the rest."""

from collections import defaultdict
from typing import NamedTuple

from .mapfile import ld_pattern, lib_of


class Cache(NamedTuple):
    sets: int
    ways: int
    line: int


def total(ws):
    return sum(ws.values())


def pick(secs, weights, budget, exclude=(), libs_only=False):
    """Functions with the highest executed-line weight per byte, up to budget bytes.

    exclude: section names never moved (busy-waits: many samples, few misses; early-boot code that
    runs before the copy to RAM, e.g. memcpy). libs_only: only Zephyr library targets ("lib*.a",
    not arch, libc, libgcc), for zephyr_code_relocate(LIBRARY ...)."""
    def ok(i):
        s = secs[i]
        if not s.name.startswith(".text.") or s.name in exclude:
            return False
        lib = lib_of(s.path)
        return not libs_only or (lib.startswith("lib") and not lib.startswith(("libarch", "libc", "libgcc", "libapp")))
    cand = sorted((i for i in weights if ok(i)), key=lambda i: -total(weights[i]) / secs[i].size)
    out, used = [], 0
    for i in cand:
        if used + secs[i].size <= budget:
            out.append(i)
            used += secs[i].size
    return out, used


def zephyr_relocate_cmake(secs, picked, location="RAM"):
    """zephyr_code_relocate(LIBRARY <target> LOCATION <location>_TEXT NOKEEP FILTER ...) per library.
    Not with LTO (Zephyr: code relocation and LTO do not combine; use ramfunc_ld)."""
    by = defaultdict(list)
    for i in picked:
        by[lib_of(secs[i].path)[3:]].append(secs[i].name[len(".text."):].replace(".", "[.]"))
    return "".join(f'zephyr_code_relocate(LIBRARY {lib} LOCATION {location}_TEXT NOKEEP FILTER "^[.]text[.]({"|".join(n)})$")\n'
                   for lib, n in sorted(by.items()))


def ramfunc_ld(secs, picked):
    """Input-section patterns for a RAMFUNC_SECTION linker snippet. Needs a linker script in which
    .ramfunc comes before .text, else .text claims the sections first."""
    return "".join(ld_pattern(secs[i]) + "\n" for i in picked)


def _set_cost(ws, ways):
    """Relative misses of one set (LRU): each run of a line beyond the `ways` most used lines misses
    and evicts another line; a small term spreads lines over empty sets first."""
    s = sorted(ws, reverse=True)
    return 2 * sum(s[ways:]) + 0.001 * sum(s[1:ways])


def colour(secs, weights, cache, cap=64.0):
    """Start set per function, heaviest first, so that few sets hold more than `ways` often executed
    lines. Returns ({index: start set}, per-set weight lists)."""
    load = [[] for _ in range(cache.sets)]
    order = sorted(weights, key=lambda i: -sum(min(c, cap) for c in weights[i].values()))
    plan, nxt = {}, 0
    for i in order:
        ls = [(r, min(c, cap)) for r, c in weights[i].items()]
        span = (secs[i].size + secs[i].addr % cache.line + cache.line - 1) // cache.line
        best = None
        for k in range(cache.sets):
            c = (nxt + k) % cache.sets
            cost = sum(_set_cost(load[(c + r) % cache.sets] + [w], cache.ways) - _set_cost(load[(c + r) % cache.sets], cache.ways) for r, w in ls)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, c)
                if cost == 0:
                    break
        for r, w in ls:
            load[(best[1] + r) % cache.sets].append(w)
        plan[i] = best[1]
        nxt = (best[1] + span) % cache.sets
    return plan, load


def place(secs, plan, cache, start):
    """Addresses from `start` on, with padding, so that each function begins in its planned set and
    keeps its address mod line size (its line split stays as profiled)."""
    way = cache.sets * cache.line
    left, p, out = dict(plan), start, []
    while left:
        def gap(i):
            return (left[i] * cache.line + secs[i].addr % cache.line - p % way) % way
        i = min(left, key=gap)
        a = p + gap(i)
        out.append((i, a))
        p = a + secs[i].size
        del left[i]
    return out


def colour_ld(secs, placed, origin):
    """Linker snippet (placed in the output section that starts at `origin`, e.g. Zephyr ROM_START)."""
    return "".join(f". = 0x{a - origin:x};\n{ld_pattern(secs[i])}\n" for i, a in placed)


def check(secs, plan_rows):
    """Rows (name, path, planned address) not linked at their planned address."""
    key = lambda name, path: (name, "ltrans" if ".ltrans" in path else path)
    at = {key(s.name, s.path): s.addr for s in secs}
    return [(n, p, a, at.get(key(n, p))) for n, p, a in plan_rows if at.get(key(n, p)) != a]
