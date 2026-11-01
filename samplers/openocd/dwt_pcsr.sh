#!/bin/bash
# Non-intrusive PC sampling over SWD: reads DWT_PCSR (0xE000101C, ARMv7-M and ARMv6-M with DWT) <n>
# times with openocd while the target runs. Rate is limited by the probe (CMSIS-DAP: about 1-5 k/s).
#   dwt_pcsr.sh <out.txt> <n> <openocd args ...>
#   example (RP2040, Raspberry Pi Debug Probe):
#     dwt_pcsr.sh pcs.txt 20000 -c "adapter serial E66..." -f interface/cmsis-dap.cfg -f target/rp2040.cfg \
#                 -c "adapter speed 10000" -c init -c "targets rp2040.core0"
# Output: one hex PC per line. Start the workload before, stop it after. A sampled PC of 0xffffffff
# means the core was halted or sleeping on some cores; filter it out.
set -eu
out=$1 n=$2
shift 2
timeout 3600 openocd "$@" \
	-c "set f [open $out.part w]; for {set i 0} {\$i < $n} {incr i} { puts \$f [format %08x [read_memory 0xE000101C 32 1]] }; close \$f" \
	-c shutdown
mv "$out.part" "$out"
echo "$(wc -l < "$out") samples -> $out"
