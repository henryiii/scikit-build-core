# LANGUAGES NONE: this is a header + CMake-config package, so no compiler (and
# no compiled extension) is involved -- only configure-time generation +
# install.
cmake_minimum_required(VERSION 3.15...3.30)
project(
  sdist_cmake_install_auto
  LANGUAGES NONE
  VERSION ${SKBUILD_PROJECT_VERSION})

# Configure-time generated file: the version is substituted here, so it only
# exists after CMake runs. Capturing it in the sdist is the point of the test.
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/example-config.cmake.in"
               "${CMAKE_CURRENT_BINARY_DIR}/example-config.cmake" @ONLY)

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/include/example.h"
        DESTINATION sdist_cmake_install_auto/include)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/example-config.cmake"
        DESTINATION sdist_cmake_install_auto/cmake)

# Also install into the headers wheel tree, outside the install prefix, to
# exercise restaging trees beyond platlib/purelib (SKBUILD_HEADERS_DIR et al.).
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/include/example.h"
        DESTINATION "${SKBUILD_HEADERS_DIR}")
