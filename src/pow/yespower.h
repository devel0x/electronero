#ifndef INTERCHAINED_YESPOWER_H
#define INTERCHAINED_YESPOWER_H

#include <stdint.h>
#include "uint256.h"
#include "arith_uint256.h"
#include "primitives/block.h"

uint256 YespowerHash(const CBlockHeader& block, );
bool CheckYespower(const CBlockHeader& block, const arith_uint256& bnTarget, int height);

#endif // INTERCHAINED_YESPOWER_H
