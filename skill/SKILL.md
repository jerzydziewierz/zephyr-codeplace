---
name: codeplace
description: Measure and improve code placement on a microcontroller that executes code from cached external flash (XIP), e.g. RP2040, i.MX RT, ESP32, STM32 with OCTOSPI. Use when a firmware path (network, USB, crypto) is slower than its CPU clock suggests, or when deciding which code to put in SRAM/ITCM.
---

# Code placement for cached-flash MCUs

Goal: find out whether a firmware hot path is limited by instruction fetch from external flash, and if so, put the right code in fast memory (SRAM, ITCM) or lay it out so that it fits the cache. Every step gives a number with an error bar; decide from numbers, not from expectations.

Tools: the `codeplace` Python package in this repository (`python -m codeplace profile|pick|colour|check`), samplers in `samplers/`. Zephyr is the reference integration; the method is not Zephyr-specific.

## 0. Rules

- Measure on the real board with the real flash chip. ⛔ Do not profile on another board with the same SoC but a different flash device or flash interface setup: the fetch cost is the thing under study.
- One workload driver, repeatable, that represents the use case (e.g. UDP echo at fixed rates, ping, a protocol load generator). A layout made from one workload helps mainly that workload.
- Two metrics: a cost per event (latency, cycles or cache misses per event) and a throughput (rate sweep: linear grid, ≥ 3 independent passes, each after a fresh flash; report the peak and the curve with ± SD).
- Repeat each image ≥ 3 times. Latency on USB devices can be bimodal between boots: prefer throughput sweeps for decisions, report latency as median of runs with the spread.
- Ask the owner of the hardware before flashing; a non-booting image may need a manual bootloader entry.
- Change one thing per image. Keep every image's build directory until the result is written down.

## 1. Is it the memory system? (no profiler needed)

Build these A/B images and measure both metrics:

1. Stock.
2. Whole libraries of the hot path in fast memory (Zephyr: `zephyr_code_relocate(LIBRARY <target> LOCATION RAM_TEXT|ITCM_TEXT NOKEEP)`; as `samples/net/zperf` does). Large gain = fetch-bound.
3. Instruction cache off (and, separately, data cache off). Shows the cost of misses and how much the cache already hides.
4. If the clock can change: cost ∝ 1/f says "clock-driven" but cannot separate CPU from flash when the flash clock follows the CPU clock.
5. If the cache has hit/miss counters (RP2040 XIP_CTRL), count misses per event; with a flush before one event, count the distinct lines one event touches (footprint). Footprint > cache capacity ⇒ layout alone cannot fix it; fast memory is needed.

## 2. Where is the time? (PC sampling)

- With SWD/JTAG: `samplers/openocd/dwt_pcsr.sh` reads DWT_PCSR while the target runs (non-intrusive, ~1–5 k samples/s).
- Without a probe: an on-target sampler (`samplers/zephyr-imxrt-pit/`): a timer interrupt above the kernel's interrupt lock level records the stacked PC into a buffer; its code in tightly coupled/fast memory and its buffer in non-cached fast data memory, so that it does not disturb the caches or the flash. Vary the interval (LFSR) against aliasing.
- `python -m codeplace --windows <code ranges> profile <map> <pcs> --idle .text.arch_cpu_idle --line <cache line>` → busy share per memory window, per library, per function; executed lines.
- Exclude idle and busy-wait functions (many samples, few misses).
- Read the per-window line: if the share of busy time in flash is small after a placement, more placement will not help; the path is now compute- or data-bound.

## 3. Placement, most portable first

1. **Name list** of the densest functions (samples or line weight per byte) into fast memory: `codeplace pick <map> <out> <map>:<pcs> --budget <bytes> --format relocate --location RAM|ITCM` (Zephyr CMake) or `--format ramfunc` (linker snippet; works with LTO if `.ramfunc` comes before `.text` in the linker script). Make a size curve (e.g. 4–32 KB). Names survive most code changes.
2. **Cache colouring** of the remaining hot code: `codeplace colour ... --sets --ways --line --start --origin`, then `codeplace check`. Build-specific: regenerate per build.
3. **Whole files/libraries** when fast memory is plentiful (i.MX RT ITCM 128 KB+): simplest, robust.
4. Then compiler and configuration (only after placement, because a fetch-bound image hides them): `-O2` for the hot code, fewer thread hand-offs, fewer locks.

## 4. Footguns (each one cost a day once)

- Code that runs before the copy to RAM must stay in flash: reset, early init (`SystemInit`, clock setup), `memcpy`/`memset` used by the copy itself, BSS/data init. Moving them = image does not boot.
- `*(.text.foo)` patterns also match same-named static functions in other files: use `*libx.a:obj.o(.text.foo)` (codeplace does).
- LTO renames objects per link (`.ltrans`): use plain section names; Zephyr code relocation does not work with LTO.
- Zephyr `zephyr_code_relocate` silently skips files that are not in the build: verify addresses with `nm` after each build.
- C++ code with exceptions cannot move to TCM on Cortex-M7 if `.ARM.exidx` stays in flash with out-of-range offsets.
- Instrumented images (`-finstrument-functions`, gcov) need larger stacks; Zephyr coverage builds force `-O0`.
- Editing a shell script while a background run executes it can break that run (bash reads scripts incrementally).
- A non-allocating/bypass cache alias for code does not help (RP2040: ⛔ measured).
- PGO at `-Os` and global `-O2` did not help while fetch-bound (RP2040); after placement, `-O2` on code in fast memory can help (i.MX RT).

## 5. Report

Per image: build flags, fast-memory bytes, cost per event (median, spread), throughput peak ± SD, profile file. One plot of throughput vs offered rate with all images; one bar chart of cost per event. State what was not measured.
