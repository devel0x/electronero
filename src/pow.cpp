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

unsigned int DarkGravityWave3Nova(const CBlockIndex* pindexLast, const Consensus::Params& params);
unsigned int Lwma3(const CBlockIndex* pindexLast, const Consensus::Params& params);
// BITCOIN LEGACY DAA
unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    LogPrintf("GetNextWorkRequired: height=%d using %s\n", pindexLast->nHeight,
          (pindexLast->nHeight >= params.yespowerForkHeight ? "Yespower target" : "SHA256 target"));
    
    if (pindexLast->nHeight + 1 >= params.nextDifficultyForkHeight && pindexLast->nHeight + 1 < params.nextDifficultyForkHeight + 59) {
        return Lwma3(pindexLast, params);
    }
    // Activate DGW3 from block 1 (for example)
    if (pindexLast->nHeight + 1 >= params.nDGW3Height && pindexLast->nHeight + 1 < params.nextDifficultyForkHeight || pindexLast->nHeight + 1 >= params.nextDifficultyFork2Height) {
        return DarkGravityWave3Nova(pindexLast, params);
    }
    
    arith_uint256 limit = UintToArith256((pindexLast->nHeight + 1 >= params.yespowerForkHeight) ? params.powLimitYespower : params.powLimit);
    LogPrintf("💡 GetNextWorkRequired: powLimit used = %s\n", limit.ToString());
    unsigned int nProofOfWorkLimit = limit.GetCompact();

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

// DGW3
unsigned int DarkGravityWave3Nova(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    int nextHeight = pindexLast->nHeight + 1;
    const int nPastBlocks = (nextHeight >= params.nextDifficultyFork5Height) ? 12 : 24;

    arith_uint256 limit = UintToArith256(
        (nextHeight >= params.yespowerForkHeight) ? params.powLimitYespower : params.powLimit
    );
    LogPrintf("💡 DGW3-NOVA: powLimit used = %s\n", limit.ToString());

    if (nextHeight < nPastBlocks)
        return limit.GetCompact();

    const CBlockIndex* pindex = pindexLast;
    arith_uint256 pastDifficultyAverage, pastDifficultyAveragePrev;
    int64_t actualTimespan = 0, lastBlockTime = 0;

    for (int i = 0; i < nPastBlocks; ++i) {
        if (!pindex) break;

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
    const bool v9 = nextHeight >= params.nextDifficultyFork5Height;

    // Define clamping bounds
    int64_t minTimespanClamp = (targetTimespan / 3);
    int64_t maxTimespanClamp = (targetTimespan * 3);

    int64_t emergencyClamp = v9 ? (targetTimespan / 3) : (targetTimespan / 6);
    int64_t minSolveClamp = v9 ? (targetTimespan / 4) : (targetTimespan / 8);

    const int64_t minSolveTime = 12;
    int64_t actualSolveTime = pindexLast->GetBlockTime() - pindexLast->pprev->GetBlockTime();
    int64_t unclampedActualTimespan = actualTimespan;  // Save raw timespan

    // Rolling median of solve times (Fork 8)
    int64_t rollingSolveTime = actualSolveTime;
    if (v9) {
        std::vector<int64_t> solveTimes;
        const CBlockIndex* cursor = pindexLast;
        for (int i = 0; i < std::min(nPastBlocks, 9); ++i) {
            if (!cursor->pprev) break;
            int64_t st = cursor->GetBlockTime() - cursor->pprev->GetBlockTime();
            solveTimes.push_back(st);
            cursor = cursor->pprev;
        }
        std::sort(solveTimes.begin(), solveTimes.end());
        rollingSolveTime = solveTimes[solveTimes.size() / 2];
        LogPrintf("🌀 DGW3-NOVA Rolling median solve time = %ds\n", rollingSolveTime);
    }

    // Trigger emergency logic BEFORE clamping
    bool triggered = v9 ? (actualSolveTime < 2 * minSolveTime && unclampedActualTimespan < targetTimespan / 6) : (actualSolveTime < minSolveTime || unclampedActualTimespan < targetTimespan / 6));

    if (triggered && nextHeight >= params.nextDifficultyFork3Height) {
        LogPrintf("🚨 [DGW3%s] Emergency/min solve triggered. Solve=%ds Timespan=%ds\n",
                v9 ? "-NOVA" : "", actualSolveTime, unclampedActualTimespan);
        actualTimespan = std::min(actualTimespan, std::min(emergencyClamp, minSolveClamp));
    }

    // Height-aware clamp normally after emergency trigger check
    if (nextHeight >= v9) {
        if (!triggered) {
            if (actualTimespan < minTimespanClamp) actualTimespan = minTimespanClamp;
            if (actualTimespan > maxTimespanClamp) actualTimespan = maxTimespanClamp;
        } else {
            LogPrintf("🛡️ DGW3-NOVA Emergency trigger at height %d: skipping normal clamps\n", nextHeight);
        }
    } else {
        if (actualTimespan < minTimespanClamp) actualTimespan = minTimespanClamp;
        if (actualTimespan > maxTimespanClamp) actualTimespan = maxTimespanClamp;
    }

    // Graceful decay logic
    double decayFactor = 1.0;
    if (nextHeight >= v9 && actualSolveTime > params.nPowTargetSpacing) {
        double multiplier = std::min(6.0, double(actualSolveTime) / params.nPowTargetSpacing);
        double decayExponent = 0.45;
        double decayLimit = 2.0;
        decayFactor = std::pow(multiplier, decayExponent);
        decayFactor = std::min(decayFactor, decayLimit);
        LogPrintf("📉 DGW3-NOVA graceful decay (v9) applied: factor=%.2f (solve=%ds)\n", decayFactor, actualSolveTime);
    } 

    // Median smoothing of pastDifficultyAverage (Fork 9)
    arith_uint256 difficultySmoothing = pastDifficultyAverage;
    if (v9) {
        std::vector<arith_uint256> pastDiffs;
        const CBlockIndex* cursor = pindexLast;
        for (int i = 0; i < std::min(nPastBlocks, 5); ++i) {
            if (!cursor->pprev) break;
            arith_uint256 prevDiff;
            prevDiff.SetCompact(cursor->nBits);
            pastDiffs.push_back(prevDiff);
            cursor = cursor->pprev;
        }
        std::sort(pastDiffs.begin(), pastDiffs.end());
        difficultySmoothing = pastDiffs[pastDiffs.size() / 2];
        LogPrintf("📊 DGW3-NOVA Difficulty median smoothing active\n");
    }

    // Final difficulty calculation with asymmetry
    arith_uint256 baseline = difficultySmoothing * actualTimespan / targetTimespan;
    arith_uint256 newDifficulty = baseline;

    if (nextHeight >= v9 && decayFactor > 1.0) {
        arith_uint256 diffToPrevious = baseline > difficultySmoothing ? (baseline - difficultySmoothing) : 0;
        newDifficulty = baseline - (diffToPrevious / decayFactor);
        LogPrintf("🪂 DGW3-NOVA decay-from-baseline: newDifficulty=%.8f\n", newDifficulty.getdouble());
    }

    arith_uint256 bnPowLimit = UintToArith256(
        (nextHeight >= params.yespowerForkHeight) ? params.powLimitYespower : params.powLimit
    );

    if (nextHeight < 5880 && newDifficulty > bnPowLimit) {
        newDifficulty = bnPowLimit;
    }

    LogPrintf("⛏️ Retargeting at height=%d with DGW3-NOVA\n", pindexLast->nHeight);
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

    if (bnNew > UintToArith256(params.powLimit))
        bnNew = UintToArith256(params.powLimit);
    
    LogPrintf("CalculateNextWorkRequired: nBits=%08x, target=%s\n",
              bnNew.GetCompact(), bnNew.ToString());
    
    return bnNew.GetCompact();
}

unsigned int Lwma3(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);

    const int N = 60;
    const int64_t T = params.nPowTargetSpacing;
    const int64_t k = N * (N + 1) / 2;

    uint256 powLimit = (pindexLast->nHeight + 1 >= params.yespowerForkHeight)
                           ? params.powLimitYespower
                           : params.powLimit;

    arith_uint256 bnPowLimit = UintToArith256(powLimit);

    // Prevent division by zero at fork
    if (pindexLast->nHeight + 1 < params.nextDifficultyForkHeight + N) {
        LogPrintf("🧪 Not enough history for LWMA3, returning powLimit\n");
        return bnPowLimit.GetCompact();
    }

    arith_uint256 sumTarget;
    int64_t t = 0;

    const CBlockIndex* pindex = pindexLast;
    for (int i = 0; i < N; ++i) {
        if (!pindex->pprev) break;
        int64_t solvetime = pindex->GetBlockTime() - pindex->pprev->GetBlockTime();
        if (solvetime > 6 * T) solvetime = 6 * T;
        if (solvetime < -6 * T) solvetime = -6 * T;
        int weight = i + 1;
        t += solvetime * weight;
        sumTarget += arith_uint256().SetCompact(pindex->nBits) * weight;
        pindex = pindex->pprev;
    }

    if (t <= 0) {
        LogPrintf("⚠️ Bad LWMA3 t <= 0, fallback to powLimit\n");
        return bnPowLimit.GetCompact();
    }

    arith_uint256 nextTarget = sumTarget * T / (k * t);
    if (nextTarget > bnPowLimit)
        nextTarget = bnPowLimit;

    LogPrintf("⛏️ LWMA3: height=%d target=%s\n", pindexLast->nHeight + 1, nextTarget.ToString());
    return nextTarget.GetCompact();
}

bool CheckProofOfWorkWithHeight(uint256 hash, CBlockHeader block, unsigned int nBits, const Consensus::Params& params, int nHeight)
{
    bool fNegative;
    bool fOverflow;
    arith_uint256 bnTarget;

    LogPrintf("💡 CheckProofOfWorkWithHeight: nHeight=%d\n", nHeight);
    bnTarget.SetCompact(nBits, &fNegative, &fOverflow);

    if (nHeight == 0 || hash == params.hashGenesisBlock) {
        LogPrintf("🧱 Skipping PoW check for genesis block\n");
        return true;
    }

    if (nHeight >= 5880) {
        if (fNegative || fOverflow || bnTarget == 0) {
            LogPrintf("❌ Invalid target format at height %d\n", nHeight);
            return false;
        }
    } else {
        if (fNegative || fOverflow || bnTarget == 0) {
            LogPrintf("❌ Legacy block rejected: bad nBits or target too easy\n");
            return false;
        }
    }

    if (nHeight >= params.sha256ForkHeight) {
        LogPrintf("🔥 Using SHA256 at height %d\n", nHeight);
        
        // DO NOT RECOMPUTE THE RESULT
        arith_uint256 bnHash = UintToArith256(hash);
        LogPrintf("📏 SHA256 PoW hash: %s\n", hash.ToString());
        LogPrintf("🎯 Target:         %s\n", bnTarget.ToString());

        if (bnHash > bnTarget) {
            LogPrintf("❌ hash too high\n");
            return false;
        }

        LogPrintf("✅ SHA256 passed at height %d\n", nHeight);
        return true;
    } else if (nHeight >= params.yespowerForkHeight) {
        if(nHeight == 1) {
            return true; 
        }
        LogPrintf("⚡ Using Yespower at height %d\n", nHeight);
        LogPrintf("🧮 Computed hash: %s\n", hash.ToString());
        LogPrintf("🎯 Target:        %s\n", bnTarget.ToString());
        LogPrintf("📏 Comparison:    hash <= target ? %s\n", (UintToArith256(hash) <= bnTarget) ? "✅ YES" : "❌ NO");
        return CheckYespower(block, bnTarget, nHeight);
    } else {
        LogPrintf("🔒 Using SHA256 at height %d\n", nHeight);
        uint256 b_hash = block.GetHash(); // SHA256
        return UintToArith256(b_hash) <= bnTarget;
    }
}

bool CheckProofOfWork(uint256 hash, const CBlockHeader& blockHeader, unsigned int nBits, const Consensus::Params& params, int nHeight)
{
    LogPrintf("🚧 CheckPoW height=%d, using: %s\n", nHeight,
        (nHeight >= params.sha256ForkHeight) ? "SHA256" :
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
