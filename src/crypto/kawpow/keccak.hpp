#ifndef BITCOIN_CRYPTO_KECCAK_HPP
#define BITCOIN_CRYPTO_KECCAK_HPP

#include <cstdint>

// Keccak-f[800] permutation (used in ProgPoW mix and final hashing)
void keccak_f800(const uint8_t* input, uint8_t* output);

#endif // BITCOIN_CRYPTO_KECCAK_HPP
