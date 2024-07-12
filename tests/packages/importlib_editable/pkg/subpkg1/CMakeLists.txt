python_add_library(subpkg1 MODULE subpkg1.c WITH_SOABI)

install(TARGETS subpkg1 DESTINATION pkg/subpkg1)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/subpkg1)
