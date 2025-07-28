import Big from 'big.js';
import * as bitcoinjs from 'interchainedjs-lib';
import { u8, hex } from './helpers'; // Ensure hex() returns hex string for Uint8Array

export class DifficultyUtils {
  static calculateDifficulty(header: Buffer | Uint8Array | string): { submissionDifficulty: number; submissionHash: string } {
    const headerBuf = Buffer.isBuffer(header)
      ? header
      : typeof header === 'string'
        ? Buffer.from(header, 'hex')
        : Buffer.from(header);

    const hashResult = bitcoinjs.crypto.hash256(headerBuf);

    // Convert hashResult to Buffer for le256todouble
    const s64 = DifficultyUtils.le256todouble(Buffer.from(hashResult));

    const truediffone = Big('26959946667150639794667015087019630673637144422540572481103610249215');
    const difficulty = truediffone.div(s64.toString());

    return {
      submissionDifficulty: difficulty.toNumber(),
      submissionHash: hex(hashResult) // Use helper to convert Uint8Array to hex
    };
  }

  private static le256todouble(target: Buffer): bigint {
    return target.reduceRight((acc, byte) => {
      return (acc << BigInt(8)) | BigInt(byte);
    }, BigInt(0));
  }
}

