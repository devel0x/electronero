#!/usr/bin/env bash
export LC_ALL=C

CLI="./src/interchained-cli -rpcuser=interchainrpc -rpcpassword=supersecure"

# Get current block height
HEIGHT=$($CLI getblockcount)

# Use max 4096 blocks or current height - 1 (min 1)
if [ "$HEIGHT" -lt 2 ]; then
  echo "Blockchain too short to generate stats."
  exit 1
fi

COUNT=$(( HEIGHT - 1 ))
if [ "$COUNT" -gt 4096 ]; then
  COUNT=4096
fi

# Get best block hash
TIP_HASH=$($CLI getbestblockhash)

# Get stats
TXSTATS=$($CLI getchaintxstats $COUNT $TIP_HASH 2>/dev/null)

N_TIME=$(echo $TXSTATS | jq '.time')
N_TX=$(echo $TXSTATS | jq '.txcount')
TX_RATE=$(echo $TXSTATS | jq '.txrate')

echo ""
echo "chainTxData = ChainTxData{"
echo "    /* nTime    */ $N_TIME,"
echo "    /* nTxCount */ $N_TX,"
echo "    /* dTxRate  */ $TX_RATE"
echo "};"
echo ""

