export interface IBlockTemplateTx {
    data: string;              // (string) transaction data encoded in hexadecimal (byte-for-byte)
    txid: string;              // (string) transaction id encoded in little-endian hexadecimal
    hash: string;              // (string) hash encoded in little-endian hexadecimal (including witness data)
    depends: number[];         // (json array) transactions before this one (by 1-based index in 'transactions' list) that must be present
    fee: number;               // (numeric) difference in value between transaction inputs and outputs (in satoshis)
    sigops: number;            // (numeric) total SigOps cost, as counted for purposes of block limits
    weight: number;            // (numeric) total transaction weight, as counted for purposes of block limits
}

export interface IBlockTemplate {
    version: number;                       // (numeric) The preferred block version
    rules: string[];                       // (json array) specific block rules enforced
    vbavailable: { [key: string]: number } | {};
    vbrequired: number;                    // (numeric) bit mask of versionbits required
    previousblockhash: string;             // (string) The hash of current highest block
    transactions: IBlockTemplateTx[];      // (json array) non-coinbase transactions
    coinbaseaux: { key: string } | {};     // (json object) coinbase scriptSig data
    coinbasevalue: number;                 // (numeric) max input to coinbase transaction
    longpollid: string;                    // (string) id for longpoll updates
    target: string;                        // (string) The hash target
    mintime: number;                       // (numeric) min timestamp for next block
    mutable: string[];                     // (json array) allowed changes
    noncerange: string;                    // (string) range of valid nonces
    sigoplimit: number;                    // (numeric) limit of sigops
    sizelimit: number;                     // (numeric) block size limit
    weightlimit: number;                   // (numeric) block weight limit
    curtime: number;                       // (numeric) current UNIX timestamp
    bits: string;                          // (string) compressed target
    height: number;                        // (numeric) height of next block
    default_witness_commitment: string;    // (string) witness commitment
    capabilities: string[];

    // Extended fields for reward distribution
    minerReward?: number;
    governanceReward?: number;
    governanceAddress?: string;
    nodeOperatorsReward?: number;
    nodeOperatorsAddress?: string;
    defaultPoolAddress?: string;
}

