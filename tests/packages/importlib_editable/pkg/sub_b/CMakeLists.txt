python_add_library(emod_c MODULE emod_c.c WITH_SOABI)

install(TARGETS emod_c DESTINATION pkg/sub_b)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/sub_b)

add_subdirectory(sub_c)
add_subdirectory(sub_d)
