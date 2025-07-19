#include "kawpow.h"
#include "progpow.hpp"
#include "keccak.hpp"
#include "uint256.h"
#include "arith_uint256.h"
#include <primitives/block.h>  // for CBlock
#include <cstring>             // for std::memcpy

// Epoch length — same as Ravencoin (7500 blocks)
static constexpr uint32_t EPOCH_LENGTH = 7500;

namespace kawpow {

bool verify(const uint256& headerHash,
            const uint256& mixHash,
            uint64_t nonce,
            int height,
            const uint256& seedHash)
{
    // Convert hash to bytes
    std::array<uint8_t, 32> header;
    std::copy(headerHash.begin(), headerHash.end(), header.begin());

    // Determine epoch number
    const uint32_t epoch = height / EPOCH_LENGTH;

    // Light cache context (no full DAG needed)
    progpow::hash256 result;
    progpow::hash256 mix_out;

    progpow::progpow_hash(epoch, header, nonce, result, mix_out);

    // Validate mix hash
    if (memcmp(mix_out.bytes.data(), mixHash.begin(), 32) != 0) {
        return false;
    }

    // Convert result to arith form for comparison
    uint256 final_hash;
    std::copy(std::begin(result.bytes), std::end(result.bytes), final_hash.begin());
    arith_uint256 bnResult = UintToArith256(final_hash);

    // You’ll do final PoW check (hash < target) elsewhere in pow.cpp
    // This just validates the hash computation and mix correctness
    return true;
}

} // namespace kawpow

uint256 GetKAWPOWHash(const CBlock& block, int height)
{
    std::array<unsigned char, 32> headerHash;
    std::memcpy(headerHash.data(), ((CBlockHeader)block).GetHash().begin(), 32);

    progpow::hash256 mix, result;
    progpow::progpow_hash(height / 7500, headerHash, block.nNonce64, mix, result);

    return uint256(std::vector<unsigned char>(result.bytes.begin(), result.bytes.end()));
}