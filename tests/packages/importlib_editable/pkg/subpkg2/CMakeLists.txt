python_add_library(subpkg2 MODULE subpkg2.c WITH_SOABI)

install(TARGETS subpkg2 DESTINATION pkg/subpkg2)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/subpkg2)

add_subdirectory(subsubpkg1)
add_subdirectory(subsubpkg2)
