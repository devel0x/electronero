set(evm_sources
  evm.cpp
)

set(evm_headers
  evm.h
)

monero_add_library(evm
  ${evm_sources}
  ${evm_headers}
)

target_link_libraries(evm
  PUBLIC
    common
    wallet      # <-- Required for tools::wallet2
    cryptonote_core
    cryptonote_basic
    crypto
    epee
    blockchain_db
    ringct
    ringct_basic
    mnemonics
    serialization
    device
    version
)
