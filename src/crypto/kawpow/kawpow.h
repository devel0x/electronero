#ifndef BITCOIN_CRYPTO_KAWPOW_H
#define BITCOIN_CRYPTO_KAWPOW_H

#include <stdint.h>
#include "uint256.h"

namespace kawpow {

// Verify the PoW hash for a given block header hash
bool verify(const uint256& headerHash,
            const uint256& mixHash,
            uint64_t nonce,
            int height,
            const uint256& seedHash);

} // namespace kawpow

#endif // BITCOIN_CRYPTO_KAWPOW_H
