#ifndef BITCOIN_POW_KAWPOW_H
#define BITCOIN_POW_KAWPOW_H

#include "uint256.h"

// Returns the DAG seed hash for a given height
uint256 GetKAWPOWSeed(int height);

#endif // BITCOIN_POW_KAWPOW_H
