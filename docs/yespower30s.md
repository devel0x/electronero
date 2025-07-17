# Yespower30s Difficulty Algorithm

The **Yespower30s** algorithm adjusts mining difficulty using a 30-block linear weighted moving average (LWMA). It is activated at height 5500 when the network already uses the Yespower PoW. The goal is to keep block times close to 30 seconds under highly variable hash rates.

## Overview

1. For each new block, the previous 30 blocks are inspected.
2. Each block's solve time is capped to ±6× the target time (30 s) to dampen outliers.
3. Newer blocks are weighted more heavily. The weights range from 1 for the oldest to 30 for the newest.
4. The weighted sum of targets is divided by the weighted solve times to produce the next target.

This approach is based on the LWMA3 method by Tom Harding, adapted for the shorter target interval and Yespower hash algorithm. For reference, see the original [LWMA proposal](https://github.com/zawy12/difficulty-algorithms/issues/3) and [Yespower documentation](https://github.com/princeton-nlp/yespower).

## Activation

The function `Yespower30s` is called from `GetNextWorkRequired` once `consensus.difficultyForkHeight` is reached. It requires at least 30 blocks of history; earlier heights return the current pow limit.

## Rationale

- **Responsiveness:** A short averaging window lets difficulty react quickly to hash rate changes.
- **Weighted smoothing:** Later blocks have greater influence, preventing oscillations caused by sudden spikes.
- **Consistency with Yespower:** Leveraging the existing Yespower PoW keeps the security assumptions consistent with previous forks.

## Example Code Snippet

```cpp
if (pindexLast->nHeight + 1 >= params.difficultyForkHeight) {
    return Yespower30s(pindexLast, params);
}
```

The full implementation is located in [`src/pow.cpp`](../src/pow.cpp) around the definition of `Yespower30s`.
