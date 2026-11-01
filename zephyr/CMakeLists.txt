# SPDX-License-Identifier: Apache-2.0
if(CONFIG_CODEPLACE_PC_SAMPLER)
  zephyr_library()
  zephyr_library_sources(src/pc_sampler_imxrt.c)
endif()
