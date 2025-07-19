#include "pow/kawpow.h"
#include "hash.h"

uint256 KawpowHash(const CBlockHeader& block, int height)
{
    // Placeholder implementation: use double SHA256 like legacy PoW.
    // Replace with real KAWPOW algorithm as needed.
    return block.GetHash();
}

bool CheckKawpow(const CBlockHeader& block, const arith_uint256& bnTarget, int height)
{
    uint256 hash = KawpowHash(block, height);
    return UintToArith256(hash) <= bnTarget;
}
