// src/utils/helpers.ts
import { Buffer } from 'buffer';

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


/**
 * Encode block height per BIP34:
 *  <len><height little-endian, minimally encoded>
 */
export function encodeBip34Height(height: number): Buffer {
  // bitcoinjs already does minimal little-endian encoding for script numbers
  // If you trust it, this one-liner is enough:
  // const enc = bitcoinjs.script.number.encode(height);

  // If you want a version without relying on script.number.encode:
  const le = Buffer.allocUnsafe(4);
  le.writeUInt32LE(height, 0);

  // trim trailing zeros (highest bytes)
  let last = 3;
  while (last > 0 && le[last] === 0) last--;
  const trimmed = le.slice(0, last + 1);

  return Buffer.concat([Buffer.from([trimmed.length]), trimmed]);
}

export function buildCoinbaseScriptSig(height: number, tag = 'Public-Pool'): Buffer {
  const heightPush = encodeBip34Height(height);
  const tagBuf = Buffer.from(tag, 'utf8');
  return Buffer.concat([heightPush, tagBuf]);
}
