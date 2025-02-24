python_add_library(emod_e MODULE emod_e.c WITH_SOABI)

install(TARGETS emod_e DESTINATION pkg/sub_b/sub_d/)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile"
        DESTINATION pkg/sub_b/sub_d/)
