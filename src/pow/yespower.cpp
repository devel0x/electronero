// src/pow/yespower.cpp
#include <stdint.h>
#include <string>
#include "uint256.h"
#include "arith_uint256.h"
#include "pow.h"
#include "pow/yespower.h"
#include "crypto/yespower/yespower.h"
#include "hash.h"
#include "chainparams.h" // Needed for Params()

// Legacy default (SHA256 height)
static const yespower_params_t yespower_default = {
    .version = YESPOWER_1_0,
    .N = 2048,
    .r = 8,
    .pers = NULL,
    .perslen = 0
};

// Interchained optimized (post-fork)
static const yespower_params_t yespower_interchained = {
    .version = YESPOWER_1_0,
    .N = 1024, // Faster... YESPOWER!!!
    .r = 4,    // We will also test with r = 4... 
    .pers = (const uint8_t *)"Interchained",
    .perslen = 12
};

// Optimized mining version with height and thread-local context
uint256 YespowerHash(const CBlockHeader& block, yespower_local_t* shared, int height)
{
    uint256 hash;
    const Consensus::Params& params = Params().GetConsensus();
    const yespower_params_t* algo = (height >= params.difficultyForkHeight)
        ? &yespower_interchained
        : &yespower_default;

    if (yespower_hash(shared, (const uint8_t*)&block, sizeof(CBlockHeader), algo, (yespower_binary_t*)&hash) != 0)
        abort();

    return hash;
}

// Used in CheckProofOfWork() (slow path)
bool CheckYespower(const CBlockHeader& block, const arith_uint256& bnTarget, int height)
{
    uint256 hash;
    const Consensus::Params& params = Params().GetConsensus();
    const yespower_params_t* algo = (height >= params.difficultyForkHeight)
        ? &yespower_interchained
        : &yespower_default;

    if (yespower_tls((const uint8_t*)&block, sizeof(CBlockHeader), algo, (yespower_binary_t*)&hash) != 0)
        return false;

    return UintToArith256(hash) <= bnTarget;
}

