import { AddressType, getAddressInfo } from 'bitcoin-address-validation';
import * as bitcoinjs from 'interchainedjs-lib';

import { IJobTemplate } from '../services/stratum-v1-jobs.service';
import { eResponseMethod } from './enums/eResponseMethod';
import { IMiningNotify } from './stratum-messages/IMiningNotify';
import { ConfigService } from '@nestjs/config';
import { injectExtraNonce, encodeBip34Height, u8, hex, buildCoinbaseScriptSig, buildCoinbaseScriptSigWithPad } from '../utils/helpers';

const MAX_BLOCK_WEIGHT = 4000000;
const MAX_SCRIPT_SIZE = 10000; //   https://github.com/bitcoin/bitcoin/blob/ffdc3d6060f6e65e69cf115a13b83e6eb4a0a0a8/src/consensus/tx_check.cpp#L49
interface AddressObject {
    address: string;
    percent: number;
}
export class MiningJob {

    private coinbaseTransaction: bitcoinjs.Transaction;
    private coinbasePart1: string;
    private coinbasePart2: string;

    public jobTemplateId: string;
    public networkDifficulty: number;
    public creation: number;

    constructor(
        configService: ConfigService,
        private network: bitcoinjs.networks.Network,
        public jobId: string,
        payoutInformation: AddressObject[],
        jobTemplate: IJobTemplate
    ) {

        this.creation = new Date().getTime();
        this.jobTemplateId = jobTemplate.blockData.id;

        this.coinbaseTransaction = this.createCoinbaseTransaction(payoutInformation, jobTemplate);
	console.log("encodeBip34Height(24089): ",hex(encodeBip34Height(24089)));
	console.log("Coinbase TX Hex:", this.coinbaseTransaction.toHex());
console.log("Coinbase Outputs:", this.coinbaseTransaction.outs);
console.log("Total Outputs:", this.coinbaseTransaction.outs.reduce((s, o) => s + Number(o.value), 0));
console.log("Coinbase Value (from template):", jobTemplate.blockData.coinbasevalue);
        //The commitment is recorded in a scriptPubKey of the coinbase transaction. It must be at least 38 bytes, with the first 6-byte of 0x6a24aa21a9ed, that is:
        //     1-byte - OP_RETURN (0x6a)
        //     1-byte - Push the following 36 bytes (0x24)
        //     4-byte - Commitment header (0xaa21a9ed)
        const segwitMagicBits = Buffer.from('aa21a9ed', 'hex');
        //    32-byte - Commitment hash: Double-SHA256(witness root hash|witness reserved value)

        //    39th byte onwards: Optional data with no consensus meaning
        // Initial pool identifier
        let poolIdentifier = configService.get('POOL_IDENTIFIER') || 'Public-Pool';
        let extra = Buffer.from(poolIdentifier);

        // Encode the block height
        // https://github.com/bitcoin/bips/blob/master/bip-0034.mediawiki
        const blockHeightEncoded = bitcoinjs.script.number.encode(jobTemplate.blockData.height);

        // Get the length of the block height encoding
        const blockHeightLengthByte = Buffer.from([blockHeightEncoded.length]);

        // Generate padding and take length of encode blockHeight into account
        const padding = Buffer.alloc(8 + (3 - blockHeightEncoded.length), 0)

        // Build the script
//        let script = Buffer.concat([blockHeightLengthByte, blockHeightEncoded, extra, padding]);
        // Check if the pool identifier is too long
//        this.coinbaseTransaction.ins[0].script = script;
	
	//const scriptSig = buildCoinbaseScriptSig(jobTemplate.blockData.height, 'Public-Pool');

//const script = scriptSig;
	//
	// Set the coinbase input script
//	//this.coinbaseTransaction.ins[0].script = script;
//	this.coinbaseTransaction.addOutput(bitcoinjs.script.compile([bitcoinjs.opcodes.OP_RETURN, Buffer.concat([segwitMagicBits, jobTemplate.block.witnessCommit])]), BigInt(0));
	const extraNonceBuffer = Buffer.alloc(8, 0);
	this.coinbaseTransaction.ins[0].script = injectExtraNonce(buildCoinbaseScriptSigWithPad(jobTemplate.blockData.height, 'Public-Pool', 8),extraNonceBuffer);

        // Check if the pool identifier is too long
        if ((this.coinbaseTransaction.weight() + jobTemplate.block.weight()) > MAX_BLOCK_WEIGHT) {
            console.warn('Block weight exceeds the maximum allowed weight, removing the pool identifier');
            let script = buildCoinbaseScriptSigWithPad(jobTemplate.blockData.height, '', 8); // no tag
            this.coinbaseTransaction.ins[0].script = script;
        }

        // get the non-witness coinbase tx
        //@ts-ignore
        // const serializedCoinbaseTx = this.coinbaseTransaction.__toBuffer().toString('hex');
	//const serializedCoinbaseTx = hex(this.coinbaseTransaction.toBuffer());
	const serializedCoinbaseTx = hex(this.coinbaseTransaction.toBuffer());
        const inputScript = hex(this.coinbaseTransaction.ins[0].script);

        const partOneIndex = serializedCoinbaseTx.indexOf(inputScript) + inputScript.length;

        //this.coinbasePart1 = serializedCoinbaseTx.slice(0, partOneIndex - 16);
	this.coinbasePart1 = serializedCoinbaseTx.slice(0, partOneIndex);
	this.coinbasePart2 = serializedCoinbaseTx.slice(partOneIndex);
	

    }

    public copyAndUpdateBlock(
  jobTemplate: IJobTemplate,
  versionMask: number,
  nonce: number,
  extraNonce: string, // hex
  extraNonce2: string, // hex
  timestamp: number,
  expectedExtraNonce2Size = 4
): bitcoinjs.Block {

  const testBlock = Object.assign(new bitcoinjs.Block(), jobTemplate.block);
  testBlock.transactions = jobTemplate.block.transactions.map(tx =>
    Object.assign(new bitcoinjs.Transaction(), tx)
  );

  testBlock.transactions[0] = this.coinbaseTransaction;

  // Apply version mask if needed
  if (versionMask) {
    testBlock.version ^= versionMask;
  }
  testBlock.version = 0x20000002;
  // Normalize extraNonce2
  extraNonce2 = extraNonce2.padStart(expectedExtraNonce2Size * 2, '0');

  // Rebuild a fresh scriptSig with zero placeholder
  const padBytes = (extraNonce.length + extraNonce2.length) / 2;
  let script = buildCoinbaseScriptSigWithPad(jobTemplate.blockData.height, "Public-Pool", padBytes);

  const fullEx = Buffer.from(extraNonce + extraNonce2, 'hex');
  console.log("Coinbase script before injection:", script.toString('hex'));

  // Inject extranonce into placeholder
  fullEx.copy(script, script.length - padBytes);
  console.log("Coinbase script after injection:", script.toString('hex'));

  testBlock.transactions[0].ins[0].script = script;

  // Recompute Merkle root
  const coinbaseHash = testBlock.transactions[0].getHash(false);
  testBlock.merkleRoot = this.calculateMerkleRootHash(u8(coinbaseHash), jobTemplate.merkle_branch);

  testBlock.timestamp = timestamp;
  testBlock.nonce = nonce;

  return testBlock;
}


 


    private calculateMerkleRootHash(newRoot: Buffer, merkleBranches: string[]): Buffer {

        const bothMerkles = Buffer.alloc(64);

        bothMerkles.set(newRoot);

        for (let i = 0; i < merkleBranches.length; i++) {
            bothMerkles.set(Buffer.from(merkleBranches[i], 'hex'), 32);
            // newRoot = bitcoinjs.crypto.hash256(bothMerkles);
            newRoot = u8(bitcoinjs.crypto.hash256(bothMerkles));
	    bothMerkles.set(newRoot);
        }

        return bothMerkles.subarray(0, 32)
    }


private createCoinbaseTransaction(
  addresses: { address: string; percent: number }[],
  jobTemplate: IJobTemplate,
  reservedExtraNonceBytes = 8, // how many bytes you want to inject later
  poolTag = 'Public-Pool'
): bitcoinjs.Transaction {
  const {
    coinbasevalue,
    minerReward = 0,
    governanceReward = 0,
    governanceAddress,
    nodeOperatorsReward = 0,
    nodeOperatorsAddress,
    defaultPoolAddress,
    height,
    default_witness_commitment,
  } = jobTemplate.blockData;

  const tx = new bitcoinjs.Transaction();
  tx.version = 2;

  // coinbase input (null prevout)
  tx.addInput(Buffer.alloc(32, 0), 0xffffffff, 0xffffffff);

  // ----- scriptSig with placeholder -----
  const scriptSig = buildCoinbaseScriptSigWithPad(height, poolTag, reservedExtraNonceBytes);
  tx.ins[0].script = scriptSig;  // bitcoinjs adds the varint length automatically

  // ----- outputs: miner/pool -----
  if (addresses && addresses.length > 0) {
    let left = minerReward;
    for (let i = 0; i < addresses.length; i++) {
      let amount =
        i === addresses.length - 1
          ? left
          : Math.floor((addresses[i].percent / 100) * minerReward);
      if (amount < 0) amount = 0;
      left -= amount;
      tx.addOutput(this.getPaymentScript(addresses[i].address), BigInt(amount));
    }
  } else {
    const poolAddress = defaultPoolAddress || (addresses?.[0]?.address ?? '');
    tx.addOutput(this.getPaymentScript(poolAddress), BigInt(minerReward));
  }

  // governance
  if (governanceReward > 0 && governanceAddress) {
    tx.addOutput(this.getPaymentScript(governanceAddress), BigInt(governanceReward));
  }

  // node operators
  if (nodeOperatorsReward > 0 && nodeOperatorsAddress) {
    tx.addOutput(this.getPaymentScript(nodeOperatorsAddress), BigInt(nodeOperatorsReward));
  }

  // ---- OP_RETURN witness commitment ----
  if (default_witness_commitment) {
    const commitScript = Buffer.from(default_witness_commitment, 'hex');
    tx.addOutput(commitScript, 0n);
  }

  // ---- sanity check totals ----
  const total = tx.outs.reduce((s, o) => s + Number(o.value), 0);
  if (total !== coinbasevalue) {
    console.warn(`⚠️ Coinbase mismatch: expected ${coinbasevalue}, got ${total}`);
  }

  // witness reserved value (must stay zeroed)
  const segwitWitnessReservedValue = Buffer.alloc(32, 0);
  tx.ins[0].witness = [segwitWitnessReservedValue];
  //tx.hasWitnesses = true;  // ensures 00 01 marker/flag is added

  return tx;
}



    private getPaymentScript(address: string): Buffer {
        const addressInfo = getAddressInfo(address);
        switch (addressInfo.type) {
            case AddressType.p2wpkh: {
                return u8(bitcoinjs.payments.p2wpkh({ address, network: this.network }).output!);
		// return bitcoinjs.payments.p2wpkh({ address, network: this.network }).output;
            }
            case AddressType.p2pkh: {
                return u8(bitcoinjs.payments.p2pkh({ address, network: this.network }).output!);
		// return bitcoinjs.payments.p2pkh({ address, network: this.network }).output;
            }
            case AddressType.p2sh: {
                return u8(bitcoinjs.payments.p2sh({ address, network: this.network }).output!);
		// return bitcoinjs.payments.p2sh({ address, network: this.network }).output;
            }
            case AddressType.p2tr: {
                return u8(bitcoinjs.payments.p2tr({ address, network: this.network }).output!);
		// return bitcoinjs.payments.p2tr({ address, network: this.network }).output;
            }
            case AddressType.p2wsh: {
                return u8(bitcoinjs.payments.p2wsh({ address, network: this.network }).output!);
		// return bitcoinjs.payments.p2wsh({ address, network: this.network }).output;
            }
            default: {
                return Buffer.alloc(0);
            }
        }
    }

    public response(jobTemplate: IJobTemplate): string {

        const job: IMiningNotify = {
            id: null,
            method: eResponseMethod.MINING_NOTIFY,
            params: [
                this.jobId,
                //hex(this.swapEndianWords(jobTemplate.block.prevHash)),
		hex(this.swapEndianWords(Buffer.from(jobTemplate.block.prevHash))),
		//hex(Buffer.from(this.swapEndianWords(jobTemplate.block.prevHash) as Uint8Array)),
		//hex(Buffer.from(this.swapEndianWords(jobTemplate.block.prevHash))),
		// this.swapEndianWords(jobTemplate.block.prevHash).toString('hex'),
                this.coinbasePart1,
                this.coinbasePart2,
                jobTemplate.merkle_branch,
                jobTemplate.block.version.toString(16),
                jobTemplate.block.bits.toString(16),
                jobTemplate.block.timestamp.toString(16),
                jobTemplate.blockData.clearJobs
            ]
        };

        return JSON.stringify(job) + '\n';
    }


    private swapEndianWords(buffer: Buffer): Buffer {
        const swappedBuffer = Buffer.alloc(buffer.length);

        for (let i = 0; i < buffer.length; i += 4) {
            swappedBuffer[i] = buffer[i + 3];
            swappedBuffer[i + 1] = buffer[i + 2];
            swappedBuffer[i + 2] = buffer[i + 1];
            swappedBuffer[i + 3] = buffer[i];
        }

        return swappedBuffer;
    }


}
