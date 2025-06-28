add_executable(staking_example
    ${CMAKE_CURRENT_SOURCE_DIR}/staking_example.cpp
)

target_include_directories(staking_example PRIVATE
    ${CMAKE_SOURCE_DIR}/src
)
