# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(usb_udp_echo)

target_sources(app PRIVATE src/main.c src/usb.c)
target_sources_ifdef(CONFIG_BOARD_TEENSY41 app PRIVATE src/teensy_bootloader.c)

# Placement (README.md). Whole libraries and files by Kconfig; or a list of hot functions by name
# (-DCODEPLACE_LIST=<file.cmake>, made by "python -m codeplace pick"; needs CONFIG_CODE_DATA_RELOCATION=y).
if(CONFIG_SAMPLE_HOT_PATH_LIBS)
  foreach(lib subsys__net__ip subsys__net subsys__net__l2__ethernet lib__net_buf
          subsys__usb__device_next drivers__usb__udc)
    zephyr_code_relocate(LIBRARY ${lib} LOCATION ${CONFIG_SAMPLE_HOT_PATH_REGION}_TEXT NOKEEP)
  endforeach()
endif()
if(CONFIG_SAMPLE_HOT_PATH_FILES)
  include(${CMAKE_CURRENT_SOURCE_DIR}/placement/imxrt-hot-files.cmake)
endif()
if(DEFINED CODEPLACE_LIST)
  include(${CODEPLACE_LIST})
endif()
