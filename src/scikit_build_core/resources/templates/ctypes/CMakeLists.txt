cmake_minimum_required(VERSION 3.15...4.4)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

# A plain library loaded with ctypes; it does not use Python at all.
add_library(_core MODULE src/${SKBUILD_PROJECT_NAME}/_core.c)
set_target_properties(_core PROPERTIES PREFIX "")

install(TARGETS _core DESTINATION ${SKBUILD_PROJECT_NAME})
