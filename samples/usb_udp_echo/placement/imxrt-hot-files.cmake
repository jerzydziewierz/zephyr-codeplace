# SPDX-License-Identifier: Apache-2.0
# i.MX RT: kernel, arch, timer, MPU, MCUX USB controller driver and app files in ITCM, in addition to
# the network and USB libraries. Found with the on-target PC sampler under UDP echo load (Teensy 4.1).
# Never list code that runs before the relocation copy: SystemInit (soc_reset_hook), memcpy/memset
# (fsl_memcpy.S, used by the copy), reset, z_prep_c, z_bss_zero, z_data_copy.
set(zb ${ZEPHYR_BASE})
set(hal ${ZEPHYR_HAL_NXP_MODULE_DIR}/mcux/mcux-sdk-ng)
zephyr_code_relocate(FILES
  ${zb}/kernel/work.c ${zb}/kernel/sched.c ${zb}/kernel/poll.c ${zb}/kernel/thread.c ${zb}/kernel/timeout.c
  ${zb}/kernel/queue.c ${zb}/kernel/mutex.c ${zb}/kernel/sem.c ${zb}/kernel/mem_slab.c ${zb}/kernel/timeslicing.c
  ${zb}/kernel/sleep.c ${zb}/kernel/timer.c ${zb}/kernel/kheap.c
  ${zb}/arch/arm/core/cortex_m/swap_helper.S ${zb}/arch/arm/core/cortex_m/isr_wrapper.c
  ${zb}/arch/arm/core/cortex_m/irq_manage.c ${zb}/arch/arm/core/cortex_m/thread.c
  ${zb}/arch/arm/core/cortex_m/exc_exit.c ${zb}/arch/arm/core/cortex_m/cache.c ${zb}/arch/arm/core/cortex_m/cpu_idle.c
  ${zb}/drivers/timer/cortex_m_systick.c ${zb}/lib/heap/heap.c
  ${hal}/middleware/usb/device/usb_device_ehci.c ${hal}/components/osa/fsl_os_abstraction_zephyr.c
  ${hal}/drivers/cache/armv7-m7/fsl_cache.c
  ${CMAKE_CURRENT_SOURCE_DIR}/src/main.c ${CMAKE_CURRENT_SOURCE_DIR}/src/usb.c
  ${zb}/arch/arm/core/mpu/arm_core_mpu.c ${zb}/arch/arm/core/mpu/arm_mpu.c
  ${zb}/kernel/events.c ${zb}/kernel/msg_q.c
  ${zb}/lib/os/zvfs/zvfs_poll.c ${zb}/lib/os/zvfs/zvfs_fdtable.c
  LOCATION ITCM_TEXT NOKEEP)
