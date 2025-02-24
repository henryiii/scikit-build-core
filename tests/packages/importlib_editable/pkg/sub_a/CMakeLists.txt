python_add_library(emod_b MODULE emod_b.c WITH_SOABI)

install(TARGETS emod_b DESTINATION pkg/sub_a)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/sub_a)
