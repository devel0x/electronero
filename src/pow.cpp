// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2018 The Interchained Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <pow.h>
#include <arith_uint256.h>
#include <chain.h>
#include "pow/yespower.h"
#include "validation.h"      // for cs_main
#include "logging.h"         // for BCLog and LogPrint
#include <primitives/block.h>
#include <uint256.h>

unsigned int DarkGravityWave3(const CBlockIndex* pindexLast, const Consensus::Params& params);
// BITCOIN LEGACY DAA
unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    LogPrintf("GetNextWorkRequired: height=%d using %s\n", pindexLast->nHeight,
          (pindexLast->nHeight >= params.yespowerForkHeight ? "Yespower target" : "SHA256 target"));
    // Activate DGW3 from block 1 (for example)
    if (pindexLast->nHeight + 1 >= params.nDGW3Height) {
        return DarkGravityWave3(pindexLast, params);
    }
    unsigned int nProofOfWorkLimit = UintToArith256(params.powLimit).GetCompact();

    // Only change once per difficulty adjustment interval
    if ((pindexLast->nHeight+1) % params.DifficultyAdjustmentInterval() != 0)
    {
        if (params.fPowAllowMinDifficultyBlocks)
        {
            // Special difficulty rule for testnet:
            // If the new block's timestamp is more than 2* 10 minutes
            // then allow mining of a min-difficulty block.
            if (pblock->GetBlockTime() > pindexLast->GetBlockTime() + params.nPowTargetSpacing*2)
                return nProofOfWorkLimit;
            else
            {
                // Return the last non-special-min-difficulty-rules-block
                const CBlockIndex* pindex = pindexLast;
                while (pindex->pprev && pindex->nHeight % params.DifficultyAdjustmentInterval() != 0 && pindex->nBits == nProofOfWorkLimit)
                    pindex = pindex->pprev;
                return pindex->nBits;
            }
        }
        return pindexLast->nBits;
    }

    // Go back by what we want to be 14 days worth of blocks
    int nHeightFirst = pindexLast->nHeight - (params.DifficultyAdjustmentInterval()-1);
    assert(nHeightFirst >= 0);
    const CBlockIndex* pindexFirst = pindexLast->GetAncestor(nHeightFirst);
    assert(pindexFirst);

    return CalculateNextWorkRequired(pindexLast, pindexFirst->GetBlockTime(), params);
}

// LWMA
// unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader* pblock, const Consensus::Params& params)
// {
//     const int64_t T = params.nPowTargetSpacing; // Target block time (30 sec)
//     const int N = 60; // Averaging window (60 blocks ~ 30 minutes)
//     const int k = N * (N + 1) * T / 2;

//     assert(pindexLast != nullptr);
//     if (pindexLast->nHeight < N) {
//         return UintToArith256(params.powLimit).GetCompact();
//     }

//     arith_uint256 sumTarget;
//     int64_t t = 0;
//     int64_t j = 0;

//     const CBlockIndex* pindex = pindexLast;
//     for (int i = 0; i < N; ++i) {
//         if (!pindex->pprev) break;

//         int64_t solvetime = pindex->GetBlockTime() - pindex->pprev->GetBlockTime();
//         solvetime = std::max<int64_t>(-6 * T, std::min(solvetime, 6 * T));
//         j += 1;
//         t += solvetime * j;
//         sumTarget += arith_uint256().SetCompact(pindex->nBits) * j;

//         pindex = pindex->pprev;
//     }

//     if (t == 0 || j == 0) return UintToArith256(params.powLimit).GetCompact();

//     arith_uint256 nextTarget = (sumTarget / k) * T;
//     if (nextTarget > UintToArith256(params.powLimit))
//         nextTarget = UintToArith256(params.powLimit);

//     return nextTarget.GetCompact();
// }

// DGW3
unsigned int DarkGravityWave3(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    const int nPastBlocks = 24;
    int nextHeight = (pindexLast ? pindexLast->nHeight + 1 : 0);
    
    LogPrintf("💡 DGW3: nHeight=%d returning powLimit %s\n", nextHeight,
        (nextHeight >= params.yespowerForkHeight) ?
        "Yespower" : "SHA256");
    arith_uint256 limit = UintToArith256((nextHeight >= params.yespowerForkHeight) ? params.powLimitYespower : params.powLimit);
    LogPrintf("💡 DGW3: powLimit used = %s\n", limit.ToString());
    if (nextHeight < nPastBlocks)
        return UintToArith256(
            (pindexLast->nHeight + 1 >= params.yespowerForkHeight)
            ? params.powLimitYespower
            : params.powLimit
        ).GetCompact();

    const CBlockIndex* pindex = pindexLast;
    arith_uint256 pastDifficultyAverage;
    arith_uint256 pastDifficultyAveragePrev;

    int64_t actualTimespan = 0;
    int64_t lastBlockTime = 0;

    for (int i = 0; i < nPastBlocks; ++i) {
        if (!pindex)
            break;

        arith_uint256 currentDifficulty = arith_uint256().SetCompact(pindex->nBits);

        if (i == 0)
            pastDifficultyAverage = currentDifficulty;
        else
            pastDifficultyAverage = ((pastDifficultyAveragePrev * i) + currentDifficulty) / (i + 1);

        pastDifficultyAveragePrev = pastDifficultyAverage;

        if (lastBlockTime > 0)
            actualTimespan += lastBlockTime - pindex->GetBlockTime();

        lastBlockTime = pindex->GetBlockTime();
        pindex = pindex->pprev;
    }

    const int64_t targetTimespan = nPastBlocks * params.nPowTargetSpacing;

    if (actualTimespan < targetTimespan / 3)
        actualTimespan = targetTimespan / 3;
    if (actualTimespan > targetTimespan * 3)
        actualTimespan = targetTimespan * 3;

    arith_uint256 newDifficulty = pastDifficultyAverage * actualTimespan / targetTimespan;

    arith_uint256 bnPowLimit = UintToArith256(
        (pindexLast->nHeight + 1 >= params.yespowerForkHeight)
        ? params.powLimitYespower
        : params.powLimit
    );

    if (newDifficulty > bnPowLimit) { 
        newDifficulty = bnPowLimit;
    }

    return newDifficulty.GetCompact();
}

unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params& params)
{
    if (params.fPowNoRetargeting)
        return pindexLast->nBits;

    int64_t nActualTimespan = pindexLast->GetBlockTime() - nFirstBlockTime;
    if (nActualTimespan < params.nPowTargetTimespan / 4)
        nActualTimespan = params.nPowTargetTimespan / 4;
    if (nActualTimespan > params.nPowTargetTimespan * 4)
        nActualTimespan = params.nPowTargetTimespan * 4;

    arith_uint256 bnPowLimit = UintToArith256(
        (pindexLast->nHeight + 1 >= params.yespowerForkHeight)
        ? params.powLimitYespower
        : params.powLimit
    );

    arith_uint256 bnNew;
    bnNew.SetCompact(pindexLast->nBits);
    bnNew *= nActualTimespan;
    bnNew /= params.nPowTargetTimespan;

    if (bnNew > bnPowLimit)
        bnNew = bnPowLimit;
    
    LogPrintf("CalculateNextWorkRequired: nBits=%08x, target=%s\n",
              bnNew.GetCompact(), bnNew.ToString());
    
    return bnNew.GetCompact();
}

bool CheckProofOfWorkWithHeight(uint256 hash, const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params, int nHeight)
{
    bool fNegative;
    bool fOverflow;
    arith_uint256 bnTarget;

    bnTarget.SetCompact(nBits, &fNegative, &fOverflow);
    arith_uint256 work = UintToArith256(hash);
    if (work > bnTarget) {
        LogPrintf("💥 Block failed SHA256 PoW at height=%d\n", nHeight);
        LogPrintf("  hash = %s\n", hash.ToString());
        LogPrintf("  target = %s\n", bnTarget.ToString());
        return false;
    }
    uint256 powLimit = (nHeight >= params.yespowerForkHeight)
                   ? params.powLimitYespower
                   : params.powLimit;
    // Check range
    if (fNegative || bnTarget == 0 || fOverflow || bnTarget > UintToArith256(powLimit))
        return false;

    if (nHeight >= params.yespowerForkHeight) {
        LogPrintf("⚡ Using Yespower at height %d\n", nHeight);
        return CheckYespower(block, bnTarget, nHeight);
    } else {
        uint256 b_hash = block.GetHash(); // SHA256
        return UintToArith256(b_hash) <= bnTarget;
    }
}

bool CheckProofOfWork(uint256 hash, const CBlockHeader& blockHeader, unsigned int nBits, const Consensus::Params& params, int nHeight)
{
    LogPrintf("🚧 CheckPoW height=%d, using: %s\n", nHeight,
        (nHeight >= params.kawpowForkHeight) ? "KAWPOW" :
        (nHeight >= params.yespowerForkHeight) ? "Yespower" : "SHA256");
    if (nHeight == 0) {
        LogPrintf("🧱 Skipping PoW check for genesis block\n");
        return true;
    }
    if(nHeight >= params.yespowerForkHeight) {
        return CheckProofOfWorkWithHeight(hash, blockHeader, nBits, params, nHeight);
    } else {
        bool fNegative;
        bool fOverflow;
        arith_uint256 bnTarget;
        bnTarget.SetCompact(nBits, &fNegative, &fOverflow);
        // Check range
        if (fNegative || bnTarget == 0 || fOverflow || bnTarget > UintToArith256(params.powLimit))
            return false;
        return UintToArith256(hash) <= bnTarget;
    }
}
