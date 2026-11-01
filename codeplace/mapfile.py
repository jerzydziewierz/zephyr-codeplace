"""GNU ld map file: code input sections (one function each with -ffunction-sections)."""

import re
from pathlib import Path
from typing import NamedTuple

_SEC = re.compile(r"^ (\.\S+)\s*$|^ (\.\S+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)")
_CONT = re.compile(r"^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)")
_CODE = (".text", ".rodata.", ".init", ".fini", ".vector", ".exc", ".boot", ".rom", ".itcm", ".ramfunc")


class Section(NamedTuple):
    addr: int
    size: int
    name: str  # input section name, e.g. ".text.net_ipv4_input"
    path: str  # object, e.g. "zephyr/subsys/net/ip/libsubsys__net__ip.a(ipv4.c.obj)"


def parse_windows(text):
    """"lo-hi,lo-hi" (hex) -> [(lo, hi), ...]."""
    return [tuple(int(x, 16) for x in w.split("-")) for w in text.split(",") if w]


def sections(map_path, windows):
    """Sorted, de-duplicated code input sections whose address is in one of the windows."""
    out, pend = [], None
    with open(map_path, errors="replace") as f:
        text = f.read().splitlines()
    for line in text:
        if pend:
            m = _CONT.match(line)
            if m:
                out.append(Section(int(m[1], 16), int(m[2], 16), pend, m[3]))
            pend = None
            continue
        m = _SEC.match(line)
        if m and m[1]:
            pend = m[1]
        elif m and m[2]:
            out.append(Section(int(m[3], 16), int(m[4], 16), m[2], m[5]))
    return sorted({s for s in out if s.size and s.name.startswith(_CODE) and any(lo <= s.addr < hi for lo, hi in windows)})


def lib_of(path):
    """Archive name without ".a" ("libkernel"), else the object file name."""
    m = re.search(r"([^/]+)\.a\(", path)
    return m[1] if m else Path(path).name


def member_of(path):
    """Archive member ("sched.c.obj") or object file name."""
    m = re.search(r"\.a\(([^)]+)\)$", path)
    return m[1] if m else Path(path).name


def ld_pattern(sec):
    """ld input-section pattern for exactly this section (same-named static functions exist)."""
    if ".ltrans" in sec.path:  # LTO: temporary object names change per link
        return f"*({sec.name})"
    if sec.path.endswith(")") and ".a(" in sec.path:
        arch, mem = sec.path[:-1].split(".a(", 1)
        return f"*{Path(arch).name}.a:{mem}({sec.name})"
    return f"*{Path(sec.path).name}({sec.name})"
