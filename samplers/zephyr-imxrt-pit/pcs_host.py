"""Host side of the on-target PC sampler (pc_sampler.c): start, load, dump.

    python pcs_host.py <console> <out.txt> [--mode udp|ping|idle] [--dst 192.0.2.1:4242]
                       [--rate 1000] [--hz 10000] [--runs 4] [--lr]

<console> is the Zephyr shell serial port of the board. Per run: "pcs start <hz>", load (UDP
datagrams to --dst at <rate>/s, ping at 1/rate s, or none) until the sample buffer is full,
"pcs dump". Writes one hex PC per line (all runs). Needs pyserial.
"""

import argparse
import os
import re
import socket
import subprocess
import threading
import time

import serial

def command(con, cmd, until, timeout=10.0):
    con.reset_input_buffer()
    con.write(cmd.encode() + b"\r")
    buf, t0 = b"", time.monotonic()
    while time.monotonic() - t0 < timeout:
        buf += con.read(4096)
        if re.search(until, buf):
            return buf.decode(errors="replace")
    raise TimeoutError(f"{cmd!r}: no {until!r} in {buf[-200:]!r}")


def udp_load(dst, rate, stop, counts):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setblocking(False)
    t, dt = time.monotonic(), 1.0 / rate
    while not stop.is_set():
        s.sendto(bytes(64), dst)
        counts[0] += 1
        t += dt
        try:
            while s.recv(2048):
                counts[1] += 1
        except OSError:
            pass
        time.sleep(max(0.0, t - time.monotonic()))


def one_run(con, args):
    print(command(con, f"pcs start {args.hz}{' lr' if args.lr else ''}", rb"PCS start[^\r\n]*\r?\n").strip().splitlines()[-1])
    stop, counts, load = threading.Event(), [0, 0], None
    if args.mode == "udp":
        load = threading.Thread(target=udp_load, args=(args.dst, args.rate, stop, counts))
        load.start()
    elif args.mode == "ping":
        load = subprocess.Popen(["ping", "-q", "-i", f"{1.0 / args.rate:.4f}", args.dst[0]],
                                stdout=subprocess.DEVNULL, start_new_session=True)
    try:
        while True:
            time.sleep(0.3)
            st = command(con, "pcs status", rb"PCS n \d+ of \d+, \d+ ms")
            m = re.search(r"PCS n (\d+) of (\d+), (\d+) ms", st)
            if int(m[1]) >= int(m[2]):
                break
    finally:
        stop.set()
        if isinstance(load, threading.Thread):
            load.join()
        elif load:
            load.terminate()
            load.wait()
    print(f"run: {m[1]} samples in ~{m[3]} ms, udp sent {counts[0]} replies {counts[1]}")
    out = command(con, "pcs dump", rb"PCS end \d+", timeout=120)
    pcs = []
    for line in out.splitlines():
        if re.match(r"\s*PCS( [0-9a-f]{8}){8}\s*$", line):
            pcs += line.split()[1:]
    n = int(re.search(r"PCS end (\d+)", out)[1])
    assert len(pcs) >= n, (len(pcs), n)
    return pcs[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("console")
    ap.add_argument("out")
    ap.add_argument("--dst", default="192.0.2.1:4242")
    ap.add_argument("--mode", choices=["udp", "ping", "idle"], default="udp")
    ap.add_argument("--rate", type=float, default=1000.0)
    ap.add_argument("--hz", type=int, default=10000)
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--lr", action="store_true", help="store (PC, LR) pairs: the file alternates PC and LR lines (codeplace callers)")
    args = ap.parse_args()
    host, port = args.dst.rsplit(":", 1)
    args.dst = (host, int(port))
    pcs = []
    with serial.Serial(args.console, 115200, timeout=0.1, exclusive=True) as con:
        for _ in range(args.runs):
            pcs += one_run(con, args)
    with open(args.out + ".part", "w") as f:
        f.write("\n".join(pcs) + "\n")
    os.replace(args.out + ".part", args.out)
    print(f"{len(pcs)} samples -> {args.out}")


if __name__ == "__main__":
    main()
