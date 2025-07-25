#ifndef INTERCHAINED_KAWPOW_H
#define INTERCHAINED_KAWPOW_H

#include <stdint.h>
#include "uint256.h"
#include "arith_uint256.h"
#include "primitives/block.h"

uint256 KawpowHash(const CBlockHeader& block, int height);
bool CheckKawpow(const CBlockHeader& block, const arith_uint256& bnTarget, int height);

#endif // INTERCHAINED_KAWPOW_H
