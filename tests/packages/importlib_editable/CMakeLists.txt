cmake_minimum_required(VERSION 3.15...3.26)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(
  Python
  COMPONENTS Interpreter Development.Module
  REQUIRED)

python_add_library(emod MODULE emod.c WITH_SOABI)
install(TARGETS emod DESTINATION .)
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/pmod.py" DESTINATION .)

add_subdirectory(pkg)
