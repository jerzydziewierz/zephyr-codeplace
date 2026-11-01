"""UDP echo rate sweep (standard library only): offered rate vs replies, for samples/usb_udp_echo.

    python3 tools/udp_echo_sweep.py out.jsonl [--dst 192.0.2.1:4242] [--rates 500:30000:500]
                                    [--step-seconds 2] [--gap-seconds 1] [--payload 32]

Per step: send datagrams at the offered rate for step-seconds (in 1 ms batches), wait gap-seconds,
count the replies that carry this step's tag. One JSON line per step (rate, sent, blocked, echoed,
goodput, rtt_p50_us), then a summary line with the peak goodput. Sends that would block (host
queue full, the device is not taking packets) are counted as "blocked", not retried. Writes
<out>.part and renames it at the end; Ctrl-C stops after the current step.
"""

import argparse
import json
import os
import select
import signal
import socket
import struct
import time

HDR = struct.Struct("!IId")  # step, sequence, send time


def run_step(sock, dst, step, rate, seconds, gap, payload):
    pad = bytes(max(0, payload - HDR.size))
    sent = blocked = echoed = 0
    rtts = []
    t0 = time.monotonic()
    end = t0 + seconds
    while True:
        now = time.monotonic()
        if now >= end:
            break
        due = int((now - t0) * rate)
        while sent + blocked < due:
            try:
                sock.sendto(HDR.pack(step, sent + blocked, time.monotonic()) + pad, dst)
                sent += 1
            except BlockingIOError:
                blocked += 1
        echoed += drain(sock, step, rtts)
        select.select([sock], [], [], 0.001)
    deadline = time.monotonic() + gap
    while time.monotonic() < deadline:
        select.select([sock], [], [], 0.01)
        echoed += drain(sock, step, rtts)
    rtts.sort()
    return {"rate": rate, "seconds": seconds, "sent": sent, "blocked": blocked, "echoed": echoed,
            "goodput": round(echoed / seconds, 1),
            "rtt_p50_us": round(rtts[len(rtts) // 2] * 1e6, 1) if rtts else None}


def drain(sock, step, rtts):
    n = 0
    while True:
        try:
            data = sock.recv(2048)
        except BlockingIOError:
            return n
        if len(data) >= HDR.size:
            s, _, t = HDR.unpack_from(data)
            if s == step:
                n += 1
                rtts.append(time.monotonic() - t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--dst", default="192.0.2.1:4242")
    ap.add_argument("--rates", default="500:30000:500", help="first:last:step")
    ap.add_argument("--step-seconds", type=float, default=2.0)
    ap.add_argument("--gap-seconds", type=float, default=1.0)
    ap.add_argument("--payload", type=int, default=32)
    args = ap.parse_args()
    host, port = args.dst.rsplit(":", 1)
    dst = (host, int(port))
    a, b, c = (int(x) for x in args.rates.split(":"))
    stop = []
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 22)
    peak = 0.0
    with open(args.out + ".part", "w") as f:
        for i, rate in enumerate(range(a, b + 1, c)):
            if stop:
                break
            r = run_step(sock, dst, i + 1, rate, args.step_seconds, args.gap_seconds, args.payload)
            peak = max(peak, r["goodput"])
            f.write(json.dumps({"kind": "step", "payload": args.payload, **r}) + "\n")
            f.flush()
        f.write(json.dumps({"kind": "end", "peak_goodput": peak, "interrupted": bool(stop)}) + "\n")
    os.replace(args.out + ".part", args.out)
    print(f"peak goodput {peak:.0f}/s -> {args.out}")


if __name__ == "__main__":
    main()
