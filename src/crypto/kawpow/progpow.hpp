#ifndef BITCOIN_CRYPTO_PROGPOW_HPP
#define BITCOIN_CRYPTO_PROGPOW_HPP

#include <array>
#include <cstdint>

namespace progpow {

// Output hash: 256-bit (32-byte)
struct hash256 {
    std::array<uint8_t, 32> bytes;
};

// Computes the KAWPOW (ProgPoW-based) hash
void progpow_hash(uint32_t epoch,
                  const std::array<uint8_t, 32>& header_hash,
                  uint64_t nonce,
                  hash256& result,
                  hash256& mix_hash);

} // namespace progpow

#endif // BITCOIN_CRYPTO_PROGPOW_HPP
