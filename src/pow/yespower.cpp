// src/pow/yespower.cpp
#include <stdint.h>
#include <string>
#include "uint256.h"
#include "arith_uint256.h"
#include "pow.h"
#include "crypto/yespower/yespower.h"

uint256 YespowerHash(const CBlockHeader& block)
{
    static const yespower_params_t yespower_version_1_0 = {
        .version = YESPOWER_1_0,
        .N = 2048,
        .r = 8,
        .pers = NULL,
        .perslen = 0
    };

    uint256 hash;
    if (yespower_tls((const uint8_t*)&block, sizeof(CBlockHeader), &yespower_version_1_0, (yespower_binary_t*)&hash) != 0)
        abort();

    return hash;
}
