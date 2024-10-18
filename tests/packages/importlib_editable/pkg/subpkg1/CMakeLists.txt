python_add_library(emod_b MODULE emod_b.c WITH_SOABI)

install(TARGETS emod_b DESTINATION pkg/subpkg1)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/subpkg1)
