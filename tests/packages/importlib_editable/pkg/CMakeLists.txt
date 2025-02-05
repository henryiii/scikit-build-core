python_add_library(emod_a MODULE emod_a.c WITH_SOABI)

install(TARGETS emod_a DESTINATION pkg/)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/testfile" "This is the file")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/testfile" DESTINATION pkg/)

add_subdirectory(sub_a)
add_subdirectory(sub_b)
