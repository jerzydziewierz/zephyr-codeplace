/*
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>

/* PJRC "bkpt #251": the Teensy 4.1 ROM enters the HalfKay bootloader. */
static int cmd_bootloader(const struct shell *sh, size_t argc, char **argv)
{
	shell_print(sh, "Entering HalfKay");
	k_msleep(100);
	__asm__ volatile("bkpt #251" ::: "memory");

	return 0;
}

SHELL_CMD_ARG_REGISTER(bootloader, NULL, "Enter Teensy HalfKay bootloader", cmd_bootloader, 1, 0);
