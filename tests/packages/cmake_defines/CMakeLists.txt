cmake_minimum_required(VERSION 3.15)
project(cmake_defines LANGUAGES NONE)

set(ONE_LEVEL_LIST
    ""
    CACHE STRING "")
set(NESTED_LIST
    ""
    CACHE STRING "")
set(PRESET_ONLY_VAR
    ""
    CACHE STRING "")
set(OVERWRITTEN_VAR
    ""
    CACHE STRING "")

set(out_file "${CMAKE_CURRENT_BINARY_DIR}/log.txt")
file(WRITE "${out_file}" "")

file(APPEND "${out_file}" "PRESET_ONLY_VAR=${PRESET_ONLY_VAR}\n")
file(APPEND "${out_file}" "OVERWRITTEN_VAR=${OVERWRITTEN_VAR}\n")

foreach(list IN ITEMS ONE_LEVEL_LIST NESTED_LIST)
  list(LENGTH ${list} length)
  file(APPEND "${out_file}" "${list}.LENGTH = ${length}\n")
  foreach(item IN LISTS ${list})
    file(APPEND "${out_file}" "${item}\n")
  endforeach()
endforeach()
