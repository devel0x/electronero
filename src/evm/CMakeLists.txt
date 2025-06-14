set(evm_sources
  evm.cpp
  )

set(evm_headers
  evm.h
  )

monero_add_library(evm
  ${evm_sources}
  ${evm_headers})

target_link_libraries(evm
  PUBLIC
    common)
