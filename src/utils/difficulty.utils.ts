import Big from 'big.js';
import * as bitcoinjs from 'interchainedjs-lib';
import { u8, hex } from './helpers';

export class DifficultyUtils {
  static calculateDifficulty(header: Buffer): { submissionDifficulty: number; submissionHash: string } {
    const hashResult = bitcoinjs.crypto.hash256(Buffer.isBuffer(header) ? header : Buffer.from(header, 'hex'));
    //const s64 = DifficultyUtils.le256todouble(hashResult);
    const s64 = DifficultyUtils.le256todouble(Buffer.from(hashResult));
    const truediffone = Big('26959946667150639794667015087019630673637144422540572481103610249215');
    const difficulty = truediffone.div(s64.toString());
    
    return { 
      submissionDifficulty: difficulty.toNumber(), 
      submissionHash: hex(hashResult) 
    };
  }
private static le256todouble(target: Buffer): bigint {
    const number = target.reduceRight((acc, byte) => {
      return (acc << BigInt(8)) | BigInt(byte);
    }, BigInt(0));
    return number;
  }
private static le256toBigInt(target: Buffer): bigint {
  return target.reduceRight((acc, byte) => (acc << BigInt(8)) | BigInt(byte), BigInt(0));
}

}

export function bitsToDifficulty(bitsHex: string): number {
  // Convert compact bits (e.g., "1d00ffff") to target
  const exponent = parseInt(bitsHex.slice(0, 2), 16);
  const mantissa = parseInt(bitsHex.slice(2), 16);

  const target = Big(mantissa).mul(Big(2).pow((8 * (exponent - 3))));

  // Your chain's powLimit (diff1 target)
  const powLimit = Big('26959946667150639794667015087019630673637144422540572481103610249215');

  // Difficulty = diff1_target / current_target
  return powLimit.div(target).toNumber();
}

/**
 * Converts a `difficulty` value to a 32-byte target (Buffer)
 * Assumes diff1 target = powLimit
 */
export function difficultyToTarget(difficulty: number): Buffer {
  const powLimit = Big('26959946667150639794667015087019630673637144422540572481103610249215');
  const target = powLimit.div(difficulty);
  const hexStr = BigInt(target.toFixed(0)).toString(16).padStart(64, '0');
  return Buffer.from(hexStr, 'hex');
}

/**
 * Converts compact bits (e.g., 0x1d00ffff) to 32-byte full target
 */
export function bitsToTarget(bits: number): Buffer {
  const exponent = (bits >>> 24) & 0xff;
  const mantissa = bits & 0xffffff;

  let target = Big(mantissa).mul(Big(2).pow(8 * (exponent - 3)));
  const hexStr = BigInt(target.toFixed(0)).toString(16).padStart(64, '0');
  return Buffer.from(hexStr, 'hex');
}

