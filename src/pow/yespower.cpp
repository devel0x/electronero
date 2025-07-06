// src/pow/yespower.cpp
#include <stdint.h>
#include <string>
#include "uint256.h"
#include "arith_uint256.h"
#include "pow.h"
#include "pow/yespower.h"
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
static const uint8_t interchained_pers[] = {
    'I','n','t','e','r','c','h','a','i','n','e','d'
};

static const yespower_params_t yespower_interchained = {
    .version = YESPOWER_1_0,
    .N = 1024,
    .r = 4,
    .pers = interchained_pers,
    .perslen = sizeof(interchained_pers) // = 12
};

// Legacy yespower 
uint256 YespowerHash(const CBlockHeader& block, int height)
{
    static thread_local yespower_local_t shared;
    static thread_local bool initialized = false;

    if (!initialized) {
        yespower_init_local(&shared);
        initialized = true;
    }

    return YespowerHash(block, &shared, height);
}

// Optimized mining version with height and thread-local context
uint256 YespowerHash(const CBlockHeader& block, yespower_local_t* shared, int height)
{
    uint256 hash;
    const Consensus::Params& params = Params().GetConsensus();
    const yespower_params_t* algo = (height >= 1)
        ? &yespower_interchained
        : &yespower_default;

    if (yespower(shared, (const uint8_t*)&block, sizeof(CBlockHeader), algo, (yespower_binary_t*)&hash) != 0)
        abort();

    return hash;
}


// Used in CheckProofOfWork() (slow path)
bool CheckYespower(const CBlockHeader& block, const arith_uint256& bnTarget, int height)
{
    uint256 hash;
    const Consensus::Params& params = Params().GetConsensus();
    const yespower_params_t* algo = (height >= 1)
        ? &yespower_interchained
        : &yespower_default;

    if (yespower_tls((const uint8_t*)&block, sizeof(CBlockHeader), algo, (yespower_binary_t*)&hash) != 0)
        return false;

    return UintToArith256(hash) <= bnTarget;
}

