#ifndef INTERCHAINED_YESPOWER_H
#define INTERCHAINED_YESPOWER_H

#include <stdint.h>
#include "uint256.h"
#include "primitives/block.h"

// Returns the yespower hash of a block header
uint256 YespowerHash(const CBlockHeader& block);

#endif // INTERCHAINED_YESPOWER_H
