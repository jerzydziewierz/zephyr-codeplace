# zephyr-codeplace

Code placement for Zephyr on microcontrollers that execute code from cached external flash (XIP): measure whether a hot path waits for instruction fetch, find the hot code with PC sampling (also on boards without a debug probe), and put the right code into fast memory (SRAM, ITCM) by name, or lay it out so that it fits the cache.

Status: prototype release (0.1), Apache-2.0. 

Verified on a Raspberry Pi Pico (RP2040) and a Teensy 4.1 (i.MX RT1062) with Zephyr main of October 2026.

## Why

On MCUs without on-chip flash the CPU fetches code through a small cache from QSPI flash. When the working set of a hot path is larger than the cache, each event reloads much of it from flash, and a fast core spends most of its time waiting. The Zephyr USB network path is such a case:

| Board | Workload | Stock | After placement | Fast memory used | uplift |
|---|---|---|---|---|---|
| **Raspberry Pi Pico** <br/>RP2040, 125 MHz<br/> 16 KB XIP cache) | UDP echo over USB CDC-ECM, <br/> peak rate | 322/s | 2,248/s () | 17 KB SRAM | **~7x** |
| **Teensy 4.1** <br/>i.MX RT1062, 600 MHz<br/> 32 KB I-cache) | UDP echo over USB, <br/>peak rate | 2,257/s | (a) 15,921/s;<br/> (b) 22,359/s | (a)34KB ITCM<br/>(b)78 KB ITCM | **~10x** |

RP2040 methods used: hot functions in SRAM; cache colouring; Link-time optimisation;

Teensy 4.1 methods used: 
* (a) 32 KB hot-function list in ITCM;
* (b) network, USB, kernel in ITCM, `-O2`, CDC-NCM, tuning;

Write-ups: [Pico](https://www.rey.wiki/george/blog/2026-11-01-pico-flash-layout/), [Teensy](https://www.rey.wiki/george/blog/2026-11-01-teensy-usb-itcm/).

## Contents

| Path | What |
|---|---|
| `codeplace/` | Python package, standard library only: GNU ld map parser; PC samples → time per memory window, library, function; executed cache lines; densest-function picker with emitters for `zephyr_code_relocate(... FILTER ...)` and `.ramfunc` snippets; cache colouring for any (sets, ways, line) geometry; placement check; caller attribution from (PC, LR) pairs. |
| `zephyr/` | Zephyr module. `CONFIG_CODEPLACE_PC_SAMPLER`: on-target PC sampler for i.MX RT10xx (PIT interrupt at zero-latency priority, handler in ITCM, buffer in DTCM, shell command `pcs`). |
| `samples/usb_udp_echo/` | Benchmark workload: UDP echo over USB CDC-NCM/ECM, with the placement chosen at build time (whole libraries, kernel/driver files, or a function list) and the tuning that pays after placement. |
| `tools/` | `udp_echo_sweep.py` (rate sweep, standard library), `plot_sweeps.py` (figures, matplotlib), `pcs_host.py` (drive the on-target sampler), `dwt_pcsr.sh` (PC sampling over SWD with openocd). |
| `skill/SKILL.md` | The procedure as a checklist for an engineer or an AI coding agent: decision points, measurement rules, footguns. |
| `tests/` | Unit tests (`python -m unittest discover -s tests`). |

## Use the module

Add the repository as a Zephyr module, e.g. `west build ... -- -DEXTRA_ZEPHYR_MODULES=/path/to/zephyr-codeplace`, or an entry in your `west.yml`.

PC sampling on an i.MX RT board without a probe (the board needs a Zephyr shell on a console):

```sh
# build with CONFIG_CODEPLACE_PC_SAMPLER=y; then, with the workload running:
python3 tools/pcs_host.py /dev/serial/by-id/<console> pcs.txt --mode udp --dst 192.0.2.1:4242 --rate 5000
python3 -m codeplace --windows 0x60000000-0x70000000,0x0-0x20000 profile build/zephyr/zephyr.map pcs.txt \
    --idle .text.arch_cpu_idle --line 32
```

Shell commands: `pcs start [hz] [lr]` (`lr` stores PC and LR pairs for `codeplace callers`), `pcs status`, `pcs dump`, `pcs stop`, `pcs mutex` (cycles of an uncontended `k_mutex` lock + unlock). The sampler, built in but idle, did not change the measured echo time on the Teensy. ⚠️ Do not combine it with `zephyr,sram = &dtcm`: Zephyr then places `__dtcm_bss_section` data over the normal RAM contents without a link error.

With a probe (any Cortex-M with DWT): `tools/dwt_pcsr.sh pcs.txt 20000 <openocd args>`.

## Pick and place

```sh
# 32 KB of the densest functions into ITCM, as a CMake include (zephyr_code_relocate ... FILTER)
python3 -m codeplace --windows 0x60000000-0x70000000 pick build/zephyr/zephyr.map hot.cmake \
    build/zephyr/zephyr.map:pcs.txt --budget 32768 --location ITCM
# who takes the time in a function (samples taken with "pcs start 10000 lr")
python3 -m codeplace --windows 0x60000000-0x70000000,0x0-0x20000 callers build/zephyr/zephyr.map pairs.txt \
    --functions z_impl_k_mutex_lock,z_impl_k_mutex_unlock
# colour the rest for the RP2040 XIP cache (16 KB, 2-way, 8-byte lines); check after the rebuild
python3 -m codeplace --windows 0x10000000-0x11000000 colour build/zephyr/zephyr.map colour.ld \
    build/zephyr/zephyr.map:pcs.txt --sets 1024 --ways 2 --line 8 --start 0x100001a8 --origin 0x10000100
python3 -m codeplace --windows 0x10000000-0x11000000 check build2/zephyr/zephyr.map colour.ld.plan.tsv
```

A name list goes into the application `CMakeLists.txt` with `include(hot.cmake)` and `CONFIG_CODE_DATA_RELOCATION=y`; a colouring snippet with `zephyr_linker_sources(ROM_START SORT_KEY 0x2hot colour.ld)`. Code that runs before Zephyr copies code to RAM/ITCM must stay in flash (SoC reset hooks such as `SystemInit`, the `memcpy`/`memset` used by the copy); `pick` excludes `memcpy`, `memset` and `arch_cpu_idle` by default.

## Benchmark sample

See [`samples/usb_udp_echo/README.md`](samples/usb_udp_echo/README.md): build variants, flashing, the host sweep, and the numbers measured with this sample.

## Method

Read [`skill/SKILL.md`](skill/SKILL.md) before changing a layout. In short: first decide with A/B images (stock, whole libraries in fast memory, cache off) whether the path is fetch-bound at all; then sample, pick, and verify on the real board (not a board with another flash chip) with throughput sweeps and error bars; tune the configuration only after placement.

## License

Apache-2.0 (`LICENSE`), as Zephyr.
