cmake_minimum_required(VERSION 3.15...4.4)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(
  Python
  COMPONENTS Interpreter Development.SABIModule
  REQUIRED)

python_add_library(_core MODULE src/${SKBUILD_PROJECT_NAME}/_core.c WITH_SOABI
                   USE_SABI 3.10)

install(TARGETS _core DESTINATION ${SKBUILD_PROJECT_NAME})
