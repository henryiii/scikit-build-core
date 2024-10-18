python_add_library(emod_d MODULE emod_d.c WITH_SOABI)

install(TARGETS emod_d DESTINATION pkg/sub_b/sub_c)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile"
        DESTINATION pkg/sub_b/sub_c/)
