// src/utils/helpers.ts
import { Buffer } from 'buffer';
import * as bitcoinjs from 'interchainedjs-lib';

/**
 * Ensures a Buffer object from either Buffer or Uint8Array.
 */
export const u8 = (b: Buffer | Uint8Array): Buffer => {
  return Buffer.isBuffer(b) ? b : Buffer.from(b);
};

/**
 * Converts Buffer or Uint8Array to a hex string.
 */
export const hex = (b: Buffer | Uint8Array): string => {
  return u8(b).toString('hex');
};

export function injectExtraNonce(script: Buffer, extranonce: Buffer): Buffer {
  const newScript = Buffer.from(script);
  const padStart = newScript.length - extranonce.length;
  extranonce.copy(newScript, padStart);
  return newScript;
}

/**
 * Encode block height per BIP34:
 *  <len><height little-endian, minimally encoded>
 */
export function encodeBip34Height(height: number): Buffer {
//  console.log('encodeBip34Height CALLED FROM:', new Error().stack);
//  console.log('encodeBip34Height INPUT HEIGHT:', height);

  if (height === 0) return Buffer.from([0]);

  const bytes: number[] = [];
  let tmp = height;
  while (tmp > 0) {
    bytes.push(tmp & 0xff);
    tmp >>= 8;
  }

  //console.log('encodeBip34Height RAW BYTES:', bytes);
  const result = Buffer.concat([Buffer.from([bytes.length]), Buffer.from(bytes)]);
  //console.log('encodeBip34Height RESULT:', result.toString('hex'));
  return result;
}

export function buildCoinbaseScriptSig(
  height: number,
  tag = 'Public-Pool',
  extraNonceSize = 8
): Buffer {
  const heightPush = encodeBip34Height(height);
  const tagBuf = Buffer.from(tag, 'utf8');
  const extraNoncePlaceholder = Buffer.alloc(extraNonceSize, 0);
  
  return Buffer.concat([heightPush, tagBuf, extraNoncePlaceholder]);
}

/**
 * Build a coinbase scriptSig with a fixed zero-byte placeholder at the end.
 *
 * @param height  Current block height.
 * @param tag     A string tag (e.g. 'Public-Pool').
 * @param padBytes Number of 0x00 bytes to reserve for extranonce injection.
 * @returns Buffer representing the full scriptSig.
 */
/**
 * Build a valid coinbase scriptSig with proper PUSHDATA for height, tag, and padding.
 */
export function buildCoinbaseScriptSigWithPad(
  height: number,
  tag = 'Public-Pool',
  padBytes = 8
): Buffer {
  const heightPush = encodeBip34Height(height);
  const tagBuf = Buffer.from(tag, 'utf8');
  const zeros = Buffer.alloc(padBytes, 0x00);

  const tagPad = Buffer.concat([tagBuf, zeros]);
  const pushTagPad = Buffer.concat([Buffer.from([tagPad.length]), tagPad]);

  return Buffer.concat([heightPush, pushTagPad]);
}


export function updateWitnessCommitment(block: bitcoinjs.Block) {
  const wtxids = block.transactions.map(tx => tx.getHash(true)); // with witness
  const witnessRoot = this.calculateMerkleRootHash(u8(wtxids[0]), []); 
  const reserved = Buffer.alloc(32, 0); 
  const commitment = bitcoinjs.crypto.hash256(Buffer.concat([reserved, witnessRoot]));

  // Find OP_RETURN output and replace
  const opretIndex = block.transactions[0].outs.findIndex(o => o.script[0] === bitcoinjs.opcodes.OP_RETURN);
  block.transactions[0].outs[opretIndex] = {
    script: bitcoinjs.script.compile([bitcoinjs.opcodes.OP_RETURN, Buffer.concat([Buffer.from('aa21a9ed', 'hex'), commitment])]),
    value: 0n
  };
}

/**
 * Converts a compact difficulty representation (bits) into a full 256-bit target.
 */
export function bitsToTarget(bits: number): Buffer {
  const exponent = bits >>> 24;
  const mantissa = bits & 0xffffff;

  let target = Buffer.alloc(32, 0);
  let mantissaBuf = Buffer.alloc(3);
  mantissaBuf.writeUIntBE(mantissa, 0, 3);

  if (exponent <= 3) {
    mantissaBuf.copy(target, 32 - 3 - (3 - exponent));
  } else {
    mantissaBuf.copy(target, 32 - exponent);
  }

  return target;
}
