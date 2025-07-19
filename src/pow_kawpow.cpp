#include "hash.h"
#include "uint256.h"

uint256 GetKAWPOWSeed(int height)
{
    // Same as Ravencoin: epoch = height / 7500
    int epoch = height / 7500;

    uint256 seed;
    seed.SetNull(); // start with 0x000...

    for (int i = 0; i < epoch; ++i) {
        seed = Hash(seed.begin(), seed.end());
    }

    return seed;
}
