"""Plot udp_echo_sweep.py results: replies vs offered rate, and peak per variant (needs matplotlib).

    python3 tools/plot_sweeps.py <dir> <out-prefix> [label=name ...]

<dir> holds <variant>-r<pass>.jsonl files (other payloads as <variant>-p<bytes>-r<pass>.jsonl). Writes
<out-prefix>-goodput.png (mean ± SD over passes per offered rate) and <out-prefix>-peaks.png (peak
per pass, mean ± SD), 3840 x 2160 px. Optional variant=name pairs select the variants, their legend text and their order.
"""

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(d):
    runs = defaultdict(list)
    for p in sorted(Path(d).glob("*-r*.jsonl")):
        m = re.match(r"(.+)-r\d+\.jsonl$", p.name)
        runs[m[1]].append([s for s in map(json.loads, open(p)) if s.get("kind") == "step"])
    return runs


def main():
    d, prefix = sys.argv[1], sys.argv[2]
    names = dict(a.split("=", 1) for a in sys.argv[3:])
    runs = load(d)
    order = [k for k in names if k in runs] if names else sorted(runs)
    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=200)
    top = 0
    for k, lab in enumerate(order):
        by = defaultdict(list)
        for r in runs[lab]:
            for s in r:
                by[s["rate"]].append(s["goodput"])
        x = sorted(by)
        y = [statistics.mean(by[v]) for v in x]
        e = [statistics.stdev(by[v]) if len(by[v]) > 1 else 0 for v in x]
        top = max(top, max(x))
        ax.errorbar(x, y, yerr=e, color=cmap(k % 10), lw=2, capsize=2, label=f"{names.get(lab, lab)} ({len(runs[lab])} passes)")
    ax.plot([0, top], [0, top], color="0.7", lw=1, ls="--", label="all echoed")
    ax.set_xlabel("offered UDP echo requests per second")
    ax.set_ylabel("echo replies per second (mean ± SD over passes)")
    ax.set_xlim(0, top)
    ax.set_ylim(0, None)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=12)
    fig.tight_layout()
    fig.savefig(f"{prefix}-goodput.png")

    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=200)
    peaks = [[max(s["goodput"] for s in r) for r in runs[lab]] for lab in order]
    mean = [statistics.mean(p) for p in peaks]
    sd = [statistics.stdev(p) if len(p) > 1 else 0 for p in peaks]
    ax.barh([names.get(lab, lab) for lab in order], mean, xerr=sd, color="#3b6ea5", capsize=4)
    for i, (m, p) in enumerate(zip(mean, peaks)):
        ax.text(m + max(mean) * 0.01, i, f"{m:,.0f}/s (n={len(p)})", va="center", fontsize=14)
    ax.set_xlabel("peak UDP echo replies per second (mean ± SD over passes)")
    ax.set_xlim(0, max(mean) * 1.2)
    ax.invert_yaxis()
    ax.tick_params(labelsize=14)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{prefix}-peaks.png")
    print(f"wrote {prefix}-goodput.png {prefix}-peaks.png")


if __name__ == "__main__":
    main()
