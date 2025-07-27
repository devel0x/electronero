import Big from 'big.js';
import * as bitcoinjs from 'interchainedjs-lib';
import { u8, hex } from './helpers';

export class DifficultyUtils {
  static calculateDifficulty(header: Buffer | Uint8Array | string): { submissionDifficulty: number; submissionHash: string } {
    const headerBuf = Buffer.isBuffer(header)
      ? header
      : typeof header === 'string'
        ? Buffer.from(header, 'hex')
        : Buffer.from(header);

    const hashResult = bitcoinjs.crypto.hash256(headerBuf);

    // Convert hashResult to bigint
    const s64 = DifficultyUtils.le256todouble(Buffer.from(hashResult));

    // Use your chain's powLimit for diff1
    const diff1 = Big('115792089237316195423570985008687907853269984665640564039457584007913129639935'); 
    // 0x00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff in decimal

    const difficulty = diff1.div(s64.toString());

    return {
      submissionDifficulty: difficulty.toNumber(),
      submissionHash: hex(hashResult)
    };
  }

  private static le256todouble(target: Buffer): bigint {
    return target.reduceRight((acc, byte) => {
      return (acc << BigInt(8)) | BigInt(byte);
    }, BigInt(0));
  }
}

export function bitsToDifficulty(bitsHex: string): number {
  // Convert compact bits (e.g., "1d00ffff") to target
  const exponent = parseInt(bitsHex.slice(0, 2), 16);
  const mantissa = parseInt(bitsHex.slice(2), 16);

  const target = Big(mantissa).mul(Big(2).pow((8 * (exponent - 3))));

  // Your chain's powLimit (diff1 target)
  const powLimit = Big('0x00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff');

  // Difficulty = diff1_target / current_target
  return powLimit.div(target).toNumber();
}
