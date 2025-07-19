#ifndef BITCOIN_CRYPTO_PROGPOW_HPP
#define BITCOIN_CRYPTO_PROGPOW_HPP

#include <array>
#include <cstdint>
#include "arith_uint256.h"

namespace progpow {

// Output hash: 256-bit (32-byte)
struct hash256 {
    std::array<uint8_t, 32> bytes;
};

// Initializes the DAG light cache for the given epoch
void initialize_cache(uint32_t epoch);

// Clears allocated DAG cache memory
void finalize_context();

// Core KAWPOW hashing (used by consensus verification)
void progpow_hash(uint32_t epoch,
                  const std::array<uint8_t, 32>& header_hash,
                  uint64_t nonce,
                  hash256& result,
                  hash256& mix);

// Mining search function: returns true if a nonce under the target is found
bool search(uint32_t epoch,
            const std::array<uint8_t, 32>& header_hash,
            uint64_t start_nonce,
            uint64_t* found_nonce,
            hash256& mix,
            hash256& result,
            const arith_uint256& target);

} // namespace progpow

#endif // BITCOIN_CRYPTO_PROGPOW_HPP
