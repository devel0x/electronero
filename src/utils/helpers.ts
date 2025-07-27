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

