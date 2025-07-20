#include "hash.h"
#include "uint256.h"
#include <span.h>

uint256 GetKAWPOWSeed(int height)
{
    int epoch = height / 7500;
    uint256 seed;
    seed.SetNull();

    for (int i = 0; i < epoch; ++i) {
        CHash256 hasher;
        hasher.Write(MakeUCharSpan(seed));
        hasher.Finalize(Span<unsigned char>(seed.begin(), seed.size()));
    }

    return seed;
}