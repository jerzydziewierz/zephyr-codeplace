# codeplace

Code placement for microcontrollers that execute code from cached external flash (XIP): find the hot code from PC samples, put the densest functions into fast memory by name, and lay out the rest so that it fits the instruction cache.

Status: prototype (0.1). Used on a Raspberry Pi Pico (RP2040) and a Teensy 4.1 (i.MX RT1062) with Zephyr.

## Why

On MCUs without on-chip flash, the CPU fetches code through a small cache from QSPI/octal flash. When the working set of a hot path (network stack, USB stack, crypto) is larger than the cache, each event reloads most of it from flash, and a fast core spends most of its time waiting. Measured examples:

| Board | Workload | Stock | After placement | Fast memory used |
|---|---|---|---|---|
| Raspberry Pi Pico (RP2040, 125 MHz, 16 KB XIP cache) | UDP echo over USB CDC-ECM, peak rate | 322/s | 2,248/s (hot functions + colouring + LTO) | 17 KB SRAM |
| Teensy 4.1 (i.MX RT1062, 600 MHz, 32 KB I-cache) | UDP echo over USB CDC-ECM, peak rate | 2,257/s | ≈ 15,900/s (network, USB, kernel code in ITCM) | 64 KB ITCM |

## Contents

- `codeplace/` — Python package, standard library only:
  - `mapfile` — GNU ld map parser (input sections, archive members, LTO objects, exact ld patterns).
  - `profile` — PC samples → time per memory window, library and function; executed cache lines; profile merge across differently linked images.
  - `place` — densest-function picker; emitters for Zephyr `zephyr_code_relocate(... FILTER ...)` and `.ramfunc` linker snippets; cache colouring for any (sets, ways, line) geometry; placement check.
- `samplers/openocd/dwt_pcsr.sh` — non-intrusive PC sampling over SWD (DWT_PCSR).
- `samplers/zephyr-imxrt-pit/` — on-target PC sampler for i.MX RT10xx boards without a debug probe (PIT interrupt at zero-latency priority, handler in ITCM, buffer in DTCM) and its host script.
- `skill/SKILL.md` — the procedure as a checklist for an engineer or an AI coding agent: decision points, measurement rules, footguns.
- `tests/` — unit tests with a small map fixture.

## Quick start

```sh
pixi run test
# profile: busy share per window, library, function
pixi run codeplace --windows 0x60000000-0x70000000,0x0-0x20000 profile build/zephyr/zephyr.map pcs.txt \
    --idle .text.arch_cpu_idle --line 32
# 16 KB of the densest functions into ITCM (Zephyr CMake, include from the app CMakeLists.txt)
pixi run codeplace --windows 0x60000000-0x70000000 pick build/zephyr/zephyr.map hot.cmake \
    build/zephyr/zephyr.map:pcs.txt --budget 16384 --location ITCM
# colour the rest for a 16 KB, 2-way, 8-byte-line cache (RP2040), check after the rebuild
pixi run codeplace --windows 0x10000000-0x11000000 colour build/zephyr/zephyr.map colour.ld \
    build/zephyr/zephyr.map:pcs.txt --sets 1024 --ways 2 --line 8 --start 0x100001a8 --origin 0x10000100
pixi run codeplace --windows 0x10000000-0x11000000 check build2/zephyr/zephyr.map colour.ld.plan.tsv
```

Zephyr integration of a colouring snippet: `zephyr_linker_sources(ROM_START SORT_KEY 0x2hot colour.ld)`; of a name list: `include(hot.cmake)` with `CONFIG_CODE_DATA_RELOCATION=y`.

## Method

Read `skill/SKILL.md` before changing a layout: first decide with A/B images (stock, whole libraries in fast memory, cache off) whether the path is fetch-bound at all; then sample, pick, verify on the board with throughput sweeps and error bars.

## License

Apache-2.0 (see `LICENSE`).
