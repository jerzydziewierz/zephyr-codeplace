# On-target PC sampler for i.MX RT10xx (Zephyr)

For boards without a debug probe (Teensy 4.0/4.1). PIT channel 0 interrupts at a zero-latency priority, so `irq_lock()` does not defer samples; the naked handler passes the stacked exception frame to a C function that stores the interrupted PC. Handler code is in ITCM (`__itcm_section`) and the buffer in DTCM (`__dtcm_bss_section`): the sampler does not use the I-cache, the D-cache or the flash. The interval varies by ±25 % (LFSR) against aliasing with periodic work. Cost: about 64 KB DTCM for 16384 samples, one interrupt per sample (~10 kHz default).

Integration:

1. Copy `pc_sampler.c` into the application, add `target_sources_ifdef(CONFIG_CODEPLACE_PC_SAMPLER app PRIVATE src/pc_sampler.c)`.
2. Add the `Kconfig` entries to the application Kconfig; build with `CONFIG_CODEPLACE_PC_SAMPLER=y` (needs the Zephyr shell on a console).
3. Run the workload and `python pcs_host.py <console> pcs.txt --mode udp --dst <ip>:<port> --rate 1000`; or use the shell directly: `pcs start 10000`, `pcs status`, `pcs dump`.
4. `python -m codeplace --windows 0x60000000-0x70000000,0x0-0x20000 profile build/zephyr/zephyr.map pcs.txt --idle .text.arch_cpu_idle --line 32`.

Verified on a Teensy 4.1 (Zephyr 4.4 development tree, 600 MHz): the image with the sampler idle had the same USB echo turnaround as without it (0.043 vs 0.042 ms); 10.2 k samples/s.
