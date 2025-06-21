# Node.js Module

This directory contains utilities for working with Electronero RPC services from Node.js.

## electronero.js

`electronero.js` exports the `ElectroneroRPC` class which provides convenient access to both the wallet RPC and daemon RPC servers. The class automatically exposes a method for every available RPC command.

### Usage

```javascript
const ElectroneroRPC = require('./electronero');

const rpc = new ElectroneroRPC({
  walletRpcUrl: 'http://localhost:26969/json_rpc',
  daemonRpcUrl: 'http://localhost:26968/json_rpc'
});

async function run() {
  const info = await rpc.getInfo();       // daemon RPC
  const bal = await rpc.getBalance();     // wallet RPC
  console.log('height:', info.height, 'balance:', bal.balance);
}
run().catch(console.error);
```

### API

#### `new ElectroneroRPC(options)`
* `options.daemonRpcUrl` – URL of the daemon RPC endpoint (default `http://127.0.0.1:26968/json_rpc`)
* `options.walletRpcUrl` – URL of the wallet RPC endpoint (default `http://127.0.0.1:26969/json_rpc`)
* `options.username` and `options.password` – HTTP basic authentication credentials if required.

#### `rpc.wallet(method, params)`
Send a JSON‑RPC request to the wallet RPC server.

#### `rpc.daemon(method, params)`
Send a JSON‑RPC or HTTP request to the daemon RPC server.

`ElectroneroRPC` exposes camel‑cased helper methods for every RPC command, so you can call them directly. Each method returns a promise which resolves with the RPC result or rejects with an `Error`.

### Wallet RPC helper list
```
addAddressBook
allTokens
checkReserveProof
checkSpendProof
checkTxKey
checkTxProof
createAccount
createAddress
createWallet
deleteAddressBook
exportKeyImages
exportMultisigInfo
finalizeMultisig
getAccountTags
getAccounts
getAddress
getAddressBook
getAttribute
getBalance
getBulkPayments
getHeight
getLanguages
getPayments
getReserveProof
getSpendProof
getTransferByTxid
getTransfers
getTxKey
getTxNotes
getTxProof
getaddress
getbalance
getheight
importKeyImages
importMultisigInfo
incomingTransfers
isMultisig
labelAccount
labelAddress
makeIntegratedAddress
makeMultisig
makeUri
myTokens
openWallet
parseUri
prepareMultisig
queryKey
relayTx
rescanBlockchain
rescanSpent
rescanTokenTx
setAccountTagDescription
setAttribute
setTxNotes
sign
signMultisig
splitIntegratedAddress
startMining
stopMining
stopWallet
store
submitMultisig
sweepAll
sweepDust
sweepSingle
sweepUnmixable
tagAccounts
tokenApprove
tokenBalance
tokenBurn
tokenCreate
tokenHistory
tokenHistoryAddr
tokenInfo
tokenMint
tokenSetFee
tokenTransfer
tokenTransferFrom
transfer
transferSplit
untagAccounts
verify
```

### Daemon RPC helper list
```
flushTxpool
getAlternateChains
getBans
getBlock
getBlockCount
getBlockHeaderByHash
getBlockHeaderByHeight
getBlockHeadersRange
getBlockTemplate
getCoinbaseTxSum
getConnections
getFeeEstimate
getInfo
getLastBlockHeader
getOutputDistribution
getOutputHistogram
getTxpoolBacklog
getVersion
getblock
getblockcount
getblockheaderbyhash
getblockheaderbyheight
getblockheadersrange
getblocktemplate
getlastblockheader
hardForkInfo
onGetBlockHash
onGetblockhash
relayTx
rescanTokenTx
setBans
submitBlock
submitblock
syncInfo
getAltBlocksHashes
getHeight
getInfo
getLimit
getOuts
getTransactionPool
getTransactionPoolHashesBin
getTransactionPoolStats
getTransactions
getheight
getinfo
gettransactions
isKeyImageSpent
sendRawTransaction
sendrawtransaction
getPeerList
inPeers
miningStatus
outPeers
saveBc
setLimit
setLogCategories
setLogHashRate
setLogLevel
startMining
startSaveGraph
stopDaemon
stopMining
stopSaveGraph
update
```
