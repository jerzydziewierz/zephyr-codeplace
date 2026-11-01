"""codeplace command line.

    codeplace profile <map> <pcs> [--windows lo-hi,...] [--line N] [--idle name,...]
    codeplace pick    <map> <out> <image-map>:<pcs> ... --budget BYTES [--format relocate|ramfunc|names]
                      [--location RAM|ITCM] [--exclude name,...]
    codeplace colour  <map> <out.ld> <image-map>:<pcs> ... --sets S --ways W --line L --start ADDR --origin ADDR
    codeplace check   <map> <out.ld.plan.tsv>

<map> is the linker map of the image to be changed; profiles may come from other builds of the same
objects (<image-map> is the map of the sampled image). PCs: one hex value per line.
"""

import argparse
import sys

from . import mapfile, place, profile

DEFAULT_WINDOWS = "0x00000000-0xffffffff"


def _profiles(args, line):
    out = []
    for arg in args.profiles:
        m, f = arg.rsplit(":", 1)
        out.append((mapfile.sections(m, args.win), profile.load_pcs(f)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeplace", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--windows", default=DEFAULT_WINDOWS, help="code address ranges, hex lo-hi,lo-hi")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile")
    p.add_argument("map")
    p.add_argument("pcs")
    p.add_argument("--line", type=int, default=32, help="cache line size in bytes")
    p.add_argument("--idle", default="", help="section names of idle/busy-wait code, comma separated")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--tsv", help="write section, samples, size, address, library (most samples first)")
    k = sub.add_parser("pick")
    k.add_argument("map")
    k.add_argument("out")
    k.add_argument("profiles", nargs="+")
    k.add_argument("--budget", type=int, required=True)
    k.add_argument("--line", type=int, default=32)
    k.add_argument("--format", choices=["relocate", "ramfunc", "names"], default="relocate")
    k.add_argument("--location", default="RAM", help="Zephyr memory region for --format relocate (RAM, ITCM, ...)")
    k.add_argument("--exclude", default=".text.arch_cpu_idle,.text.memcpy,.text.memset")
    c = sub.add_parser("colour")
    c.add_argument("map")
    c.add_argument("out")
    c.add_argument("profiles", nargs="+")
    c.add_argument("--sets", type=int, required=True)
    c.add_argument("--ways", type=int, required=True)
    c.add_argument("--line", type=int, required=True)
    c.add_argument("--start", type=lambda x: int(x, 0), required=True, help="first free address after the fixed head of flash")
    c.add_argument("--origin", type=lambda x: int(x, 0), required=True, help="start of the output section of the snippet")
    c.add_argument("--exclude", default="", help="section names left out (e.g. moved to RAM by pick)")
    h = sub.add_parser("check")
    h.add_argument("map")
    h.add_argument("plan")
    args = ap.parse_args(argv)
    args.win = mapfile.parse_windows(args.windows)
    secs = mapfile.sections(args.map, args.win)

    if args.cmd == "profile":
        pcs = profile.load_pcs(args.pcs)
        text, per = profile.report(secs, pcs, args.line, args.win, mapfile.lib_of,
                                   tuple(x for x in args.idle.split(",") if x), args.top)
        print(text)
        if args.tsv:
            with open(args.tsv, "w") as f:
                for i, n in per.most_common():
                    s = secs[i]
                    f.write(f"{s.name}\t{n}\t{s.size}\t{s.addr:#x}\t{mapfile.lib_of(s.path)}\n")
        return 0
    if args.cmd == "pick":
        w = profile.line_weights(secs, _profiles(args, args.line), args.line)
        picked, used = place.pick(secs, w, args.budget, set(args.exclude.split(",")), libs_only=args.format == "relocate")
        text = {"relocate": lambda: place.zephyr_relocate_cmake(secs, picked, args.location),
                "ramfunc": lambda: place.ramfunc_ld(secs, picked),
                "names": lambda: "".join(f"{secs[i].name}\t{mapfile.lib_of(secs[i].path)}\t{secs[i].size}\n" for i in picked)}[args.format]()
        with open(args.out, "w") as f:
            f.write(text)
        print(f"{len(picked)} functions, {used} B -> {args.out}")
        return 0
    if args.cmd == "colour":
        cache = place.Cache(args.sets, args.ways, args.line)
        w = profile.line_weights(secs, _profiles(args, args.line), args.line, cap=None)
        for i in [i for i in w if secs[i].name in set(args.exclude.split(","))]:
            del w[i]
        plan, load = place.colour(secs, w, cache)
        placed = place.place(secs, plan, cache, args.start)
        with open(args.out, "w") as f:
            f.write(place.colour_ld(secs, placed, args.origin))
        with open(args.out + ".plan.tsv", "w") as f:
            f.writelines(f"{secs[i].name}\t{secs[i].path}\t0x{a:x}\n" for i, a in placed)
        n = [len(s) for s in load]
        print(f"{len(placed)} sections -> {args.out}; sets by executed-line count: "
              + ", ".join(f"{k}: {n.count(k)}" for k in range(max(n, default=0) + 1)))
        return 0
    if args.cmd == "check":
        rows = [(n, p, int(a, 16)) for n, p, a in (line.rstrip("\n").split("\t") for line in open(args.plan))]
        bad = place.check(secs, rows)
        for n, p, a, got in bad[:5]:
            print(f"{n} {p}: planned {a:#x}, linked {got or 0:#x}")
        print(f"{len(bad)} sections not at the planned address")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
