import { AddressType, getAddressInfo } from 'bitcoin-address-validation';
import * as bitcoinjs from 'interchainedjs-lib';

import { IJobTemplate } from '../services/stratum-v1-jobs.service';
import { eResponseMethod } from './enums/eResponseMethod';
import { IMiningNotify } from './stratum-messages/IMiningNotify';
import { ConfigService } from '@nestjs/config';
import {
  injectExtraNonce,
  encodeBip34Height,
  u8,
  hex,
  buildCoinbaseScriptSigWithPad
} from '../utils/helpers';

const MAX_BLOCK_WEIGHT = 4000000;
const MAX_SCRIPT_SIZE = 10000;

interface AddressObject {
  address: string;
  percent: number;
}

export class MiningJob {
  private coinbaseTransaction: bitcoinjs.Transaction;
  private coinbasePart1: string;
  private coinbasePart2: string;
  private extranonceOffset: number;

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

    this.coinbaseTransaction = this.createCoinbaseTransaction(
      payoutInformation,
      jobTemplate,
      8
    );

    // Build scriptSig with placeholder extranonce
    const poolIdentifier = configService.get('POOL_IDENTIFIER') || 'Public-Pool';
    const script = buildCoinbaseScriptSigWithPad(jobTemplate.blockData.height, poolIdentifier, 8);
    this.coinbaseTransaction.ins[0].script = script;
    this.extranonceOffset = script.length - 8;

    // Add placeholder OP_RETURN witness commitment
    const segwitMagicBits = Buffer.from('aa21a9ed', 'hex');
    this.coinbaseTransaction.addOutput(
      bitcoinjs.script.compile([
        bitcoinjs.opcodes.OP_RETURN,
        Buffer.concat([segwitMagicBits, Buffer.alloc(32, 0)]) // Placeholder to be replaced
      ]),
      BigInt(0)
    );

    // Check block weight
    if (
      this.coinbaseTransaction.weight() + jobTemplate.block.weight() >
      MAX_BLOCK_WEIGHT
    ) {
      console.warn('Block weight exceeds max limit. Removing pool identifier.');
      const scriptNoTag = buildCoinbaseScriptSigWithPad(
        jobTemplate.blockData.height,
        '',
        8
      );
      this.coinbaseTransaction.ins[0].script = scriptNoTag;
      this.extranonceOffset = scriptNoTag.length - 8;
    }

    // Split coinbase TX for extranonce injection
    const serializedCoinbaseTx = hex(this.coinbaseTransaction.toBuffer());
    const inputScript = hex(this.coinbaseTransaction.ins[0].script);
    const partOneIndex =
      serializedCoinbaseTx.indexOf(inputScript) + inputScript.length;

    this.coinbasePart1 = serializedCoinbaseTx.slice(0, partOneIndex);
    this.coinbasePart2 = serializedCoinbaseTx.slice(partOneIndex);
  }

public serializeBlockWithWitness(block: bitcoinjs.Block): Buffer {
  const header = block.toBuffer(false); // false = header only
  const txCount = bitcoinjs.script.number.encode(block.transactions.length);

  const txBuffers = block.transactions.map((tx) => tx.toBuffer()); // include witness
  return Buffer.concat([header, txCount, ...txBuffers]);
}

  public copyAndUpdateBlock(
  jobTemplate: IJobTemplate,
  versionMask: number,
  nonce: number,
  extraNonce: string,   // hex
  extraNonce2: string,  // hex
  timestamp: number,
  expectedExtraNonce2Size = 4
): bitcoinjs.Block {
  // Clone the block and all transactions
  const block = Object.assign(new bitcoinjs.Block(), jobTemplate.block);
  block.transactions = jobTemplate.block.transactions.map(tx =>
    Object.assign(new bitcoinjs.Transaction(), tx)
  );

  // Clone coinbase transaction to avoid modifying the template's copy
  const cbTx = Object.assign(new bitcoinjs.Transaction(), this.coinbaseTransaction);
  block.transactions[0] = cbTx;

  // Apply version mask (if needed)
  block.version = versionMask ? (block.version ^ versionMask) : block.version;

  // Normalize extraNonce2 length
  extraNonce2 = extraNonce2.padStart(expectedExtraNonce2Size * 2, '0');

  // Determine total padding for extranonce
  const padBytes = (extraNonce.length + extraNonce2.length) / 2;

  // Build a fresh scriptSig with zeroed placeholder for extranonce
  let script = buildCoinbaseScriptSigWithPad(
    jobTemplate.blockData.height,
    "Public-Pool",
    padBytes
  );

  console.log("Coinbase script before injection:", script.toString('hex'));

  // Inject extranonce data into the placeholder
  const fullEx = Buffer.from(extraNonce + extraNonce2, 'hex');
  injectExtraNonce(script, fullEx);
  console.log("Coinbase script after injection:", script.toString('hex'));

  cbTx.ins[0].script = script;

  // Recompute the merkle root from the updated coinbase
  const coinbaseHash = cbTx.getHash(false);
  block.merkleRoot = this.calculateMerkleRootHash(
    u8(coinbaseHash),
    jobTemplate.merkle_branch
  );

  // Update the witness commitment (replaces the OP_RETURN)
  this.updateWitnessCommitment(block);

  // Update timestamp and nonce
  block.timestamp = timestamp;
  block.nonce = nonce;

  return block;
}


  private updateWitnessCommitment(block: bitcoinjs.Block) {
    const wtxids = block.transactions.map(tx => tx.getHash(true));
    const wtxidBuffers = wtxids.map(h => Buffer.from(h));

    const witnessRoot = this.merkleFromHashes(wtxidBuffers);
    const reserved = Buffer.alloc(32, 0); // Optional: randomize for security
    const commitment = bitcoinjs.crypto.hash256(Buffer.concat([reserved, witnessRoot]));

    const opretScript = bitcoinjs.script.compile([
      bitcoinjs.opcodes.OP_RETURN,
      Buffer.concat([
        Buffer.from('aa21a9ed', 'hex'),
        Buffer.from(commitment)
      ])
    ]);

    const cb = block.transactions[0];
    const index = cb.outs.findIndex(o => o.script[0] === bitcoinjs.opcodes.OP_RETURN);
    if (index !== -1) {
      cb.outs[index] = { script: opretScript, value: 0n };
    } else {
      cb.addOutput(opretScript, 0n);
    }
  }

  private merkleFromHashes(hashes: Buffer[]): Buffer {
    if (hashes.length === 0) return Buffer.alloc(32, 0);

    while (hashes.length > 1) {
      if (hashes.length % 2 !== 0) {
        hashes.push(hashes[hashes.length - 1]);
      }

      const newHashes: Buffer[] = [];
      for (let i = 0; i < hashes.length; i += 2) {
        const concat = Buffer.concat([hashes[i], hashes[i + 1]]);
        newHashes.push(Buffer.from(bitcoinjs.crypto.hash256(concat)));
      }
      hashes = newHashes;
    }
    return hashes[0];
  }

  private calculateMerkleRootHash(newRoot: Buffer, merkleBranches: string[]): Buffer {
    for (const branchHex of merkleBranches) {
      const branch = Buffer.from(branchHex, 'hex');
      const concat = Buffer.concat([newRoot, branch]);
      newRoot = Buffer.from(bitcoinjs.crypto.hash256(concat));
    }
    return newRoot;
  }

  private createCoinbaseTransaction(
    addresses: { address: string; percent: number }[],
    jobTemplate: IJobTemplate,
    reservedExtraNonceBytes = 8,
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
      height
    } = jobTemplate.blockData;

    const tx = new bitcoinjs.Transaction();
    tx.version = 2;

    tx.addInput(Buffer.alloc(32, 0), 0xffffffff, 0xffffffff);

    const scriptSig = buildCoinbaseScriptSigWithPad(
      height,
      poolTag,
      reservedExtraNonceBytes
    );
    tx.ins[0].script = scriptSig;

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

    if (governanceReward > 0 && governanceAddress) {
      tx.addOutput(this.getPaymentScript(governanceAddress), BigInt(governanceReward));
    }

    if (nodeOperatorsReward > 0 && nodeOperatorsAddress) {
      tx.addOutput(this.getPaymentScript(nodeOperatorsAddress), BigInt(nodeOperatorsReward));
    }

    const total = tx.outs.reduce((s, o) => s + Number(o.value), 0);
    if (total !== coinbasevalue) {
      console.warn(`⚠️ Coinbase mismatch: expected ${coinbasevalue}, got ${total}`);
    }

    tx.ins[0].witness = [Buffer.alloc(32, 0)]; // Witness reserved value

    return tx;
  }

  private getPaymentScript(address: string): Buffer {
    const addressInfo = getAddressInfo(address);
    switch (addressInfo.type) {
      case AddressType.p2wpkh:
        return u8(bitcoinjs.payments.p2wpkh({ address, network: this.network }).output!);
      case AddressType.p2pkh:
        return u8(bitcoinjs.payments.p2pkh({ address, network: this.network }).output!);
      case AddressType.p2sh:
        return u8(bitcoinjs.payments.p2sh({ address, network: this.network }).output!);
      case AddressType.p2tr:
        return u8(bitcoinjs.payments.p2tr({ address, network: this.network }).output!);
      case AddressType.p2wsh:
        return u8(bitcoinjs.payments.p2wsh({ address, network: this.network }).output!);
      default:
        return Buffer.alloc(0);
    }
  }

  public response(jobTemplate: IJobTemplate): string {
    const job: IMiningNotify = {
      id: null,
      method: eResponseMethod.MINING_NOTIFY,
      params: [
        this.jobId,
        hex(this.swapEndianWords(Buffer.from(jobTemplate.block.prevHash))),
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

