python_add_library(pkg MODULE pkg.c WITH_SOABI)

install(TARGETS pkg DESTINATION pkg/)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/)

add_subdirectory(subpkg1)
add_subdirectory(subpkg2)
