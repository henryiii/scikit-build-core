python_add_library(subsubpkg2 MODULE subsubpkg2.c WITH_SOABI)

install(TARGETS subsubpkg2 DESTINATION pkg/subpkg2/subsubpkg2/)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile"
        DESTINATION pkg/subpkg2/subsubpkg2/)
