cmake_minimum_required(VERSION 3.15...4.4)

project(
  ${SKBUILD_PROJECT_NAME}
  LANGUAGES C
  VERSION ${SKBUILD_PROJECT_VERSION})

find_package(
  Python
  COMPONENTS Interpreter Development.Module ${SKBUILD_SABI_COMPONENT}
  REQUIRED)

if(NOT "${SKBUILD_SABI_VERSION}" STREQUAL "")
  python_add_library(abi3_example MODULE abi3_example.c WITH_SOABI USE_SABI
                     ${SKBUILD_SABI_VERSION})

  if(NOT SKBUILD_SABI_VERSION STREQUAL "3.10")
    message(
      FATAL_ERROR
        "TEST FAILED: SKBUILD_SABI_VERSION (${SKBUILD_SABI_VERSION}) is not 3.10"
    )
  endif()
else()
  python_add_library(abi3_example MODULE abi3_example.c WITH_SOABI)
endif()

install(TARGETS abi3_example DESTINATION .)
