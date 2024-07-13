cmake_minimum_required(VERSION 3.15...3.26)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(
  Python
  COMPONENTS Interpreter Development.Module
  REQUIRED)

python_add_library(example MODULE example/example.c WITH_SOABI)

install(TARGETS example DESTINATION example/)
file(WRITE "${CMAKE_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_BINARY_DIR}/testfile" DESTINATION example/)
