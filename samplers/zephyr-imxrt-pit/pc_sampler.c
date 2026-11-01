/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * On-target PC sampler for NXP i.MX RT10xx (Cortex-M7) boards without a debug probe (e.g. Teensy 4.x).
 * PIT channel 0 interrupts at a zero-latency priority (irq_lock does not mask it); the handler
 * reads the PC from the stacked exception frame of the interrupted context. Handler code is in
 * ITCM and the sample buffer in DTCM, so the sampler does not use the I-cache, the D-cache or
 * the flash. The interval varies by +-25 % (LFSR) so that periodic work does not alias.
 * Shell: "pcs start <hz>", "pcs status", "pcs dump" (lines "PCS <hex> ..."), "pcs stop".
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/shell/shell.h>
#include <zephyr/linker/section_tags.h>
#include <fsl_clock.h>

#define PCS_N CONFIG_CODEPLACE_PC_SAMPLER_N

static __dtcm_bss_section uint32_t pcs_buf[PCS_N];
static __dtcm_bss_section volatile uint32_t pcs_n;
static __dtcm_bss_section uint32_t pcs_lfsr;
static __dtcm_bss_section uint32_t pcs_base;
static uint32_t pcs_t0, pcs_t1;

/* Called from pcs_isr with the exception frame; returns through EXC_RETURN in lr. */
__itcm_section void codeplace_pcs_record(uint32_t *frame)
{
	uint32_t n = pcs_n;

	PIT->CHANNEL[0].TFLG = PIT_TFLG_TIF_MASK;
	if (n < PCS_N) {
		pcs_buf[n] = frame[6];
		pcs_n = n + 1U;
	} else {
		PIT->CHANNEL[0].TCTRL = 0U;
	}
	pcs_lfsr = (pcs_lfsr >> 1) ^ (-(pcs_lfsr & 1U) & 0xB400U);
	PIT->CHANNEL[0].LDVAL = pcs_base - pcs_base / 4U + (pcs_base / 2U) * (pcs_lfsr & 0xFFU) / 256U;
	__DSB();
}

__itcm_section __attribute__((naked)) void codeplace_pcs_isr(void)
{
	__asm__ volatile("tst lr, #4\n\t"
			 "ite eq\n\t"
			 "mrseq r0, msp\n\t"
			 "mrsne r0, psp\n\t"
			 "b codeplace_pcs_record\n\t");
}

static int cmd_start(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t hz = argc > 1 ? strtoul(argv[1], NULL, 0) : 10000U;
	uint32_t f;

	CLOCK_EnableClock(kCLOCK_Pit);
	PIT->MCR = 0U;
	f = CLOCK_GetPerClkFreq();
	PIT->CHANNEL[0].TCTRL = 0U;
	pcs_base = f / hz;
	pcs_lfsr = 0xACE1U;
	pcs_n = 0U;
	PIT->CHANNEL[0].TFLG = PIT_TFLG_TIF_MASK;
	PIT->CHANNEL[0].LDVAL = pcs_base;
	pcs_t0 = k_uptime_get_32();
	PIT->CHANNEL[0].TCTRL = PIT_TCTRL_TIE_MASK | PIT_TCTRL_TEN_MASK;
	irq_enable(PIT_IRQn);
	shell_print(sh, "PCS start perclk %u Hz, base %u, %u samples", f, pcs_base, PCS_N);
	return 0;
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t n = pcs_n;

	if (n < PCS_N) {
		pcs_t1 = k_uptime_get_32();
	}
	shell_print(sh, "PCS n %u of %u, %u ms", n, PCS_N, pcs_t1 - pcs_t0);
	return 0;
}

static int cmd_stop(const struct shell *sh, size_t argc, char **argv)
{
	PIT->CHANNEL[0].TCTRL = 0U;
	irq_disable(PIT_IRQn);
	shell_print(sh, "PCS stopped at %u", pcs_n);
	return 0;
}

static int cmd_dump(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t n = MIN(pcs_n, PCS_N);

	for (uint32_t i = 0; i < n; i += 8U) {
		uint32_t *p = &pcs_buf[i];

		shell_print(sh, "PCS %08x %08x %08x %08x %08x %08x %08x %08x", p[0], p[1], p[2], p[3],
			    p[4], p[5], p[6], p[7]);
	}
	shell_print(sh, "PCS end %u", n);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(pcs_cmds,
	SHELL_CMD_ARG(start, NULL, "start sampling [hz]", cmd_start, 1, 1),
	SHELL_CMD(status, NULL, "samples taken", cmd_status),
	SHELL_CMD(stop, NULL, "stop sampling", cmd_stop),
	SHELL_CMD(dump, NULL, "print the samples", cmd_dump),
	SHELL_SUBCMD_SET_END);
SHELL_CMD_REGISTER(pcs, &pcs_cmds, "PC sampler (codeplace)", NULL);

static int pcs_init(void)
{
	IRQ_DIRECT_CONNECT(PIT_IRQn, 0, codeplace_pcs_isr, IRQ_ZERO_LATENCY);
	return 0;
}

SYS_INIT(pcs_init, APPLICATION, 0);
