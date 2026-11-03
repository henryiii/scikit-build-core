cmake_minimum_required(VERSION 3.15...4.4)
project(${SKBUILD_PROJECT_NAME} LANGUAGES CXX)

find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)

find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_core NB_STATIC src/${SKBUILD_PROJECT_NAME}/_core.cpp)

install(TARGETS _core LIBRARY DESTINATION ${SKBUILD_PROJECT_NAME})
