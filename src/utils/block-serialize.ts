import * as bitcoinjs from 'interchainedjs-lib';
import { hex } from './helpers';

/** Bitcoin varint encoder (unsigned) */
function encodeVarInt(n: number): Buffer {
  if (n < 0xfd) {
    return Buffer.from([n]);
  } else if (n <= 0xffff) {
    const b = Buffer.allocUnsafe(3);
    b[0] = 0xfd;
    b.writeUInt16LE(n, 1);
    return b;
  } else if (n <= 0xffffffff) {
    const b = Buffer.allocUnsafe(5);
    b[0] = 0xfe;
    b.writeUInt32LE(n, 1);
    return b;
  } else {
    const b = Buffer.allocUnsafe(9);
    b[0] = 0xff;
    // write BigUInt64LE if available, else manual
    b.writeUInt32LE(n >>> 0, 1);
    b.writeUInt32LE(Math.floor(n / 0x100000000), 5);
    return b;
  }
}

export function serializeTransaction(tx: any): Buffer {
  if (typeof tx.__toBuffer === 'function') {
    return tx.__toBuffer(undefined, undefined, true);
  }
  return tx.toBuffer(); // fallback
}

/** Serialize a block **including** witness data, regardless of what your forked Block does. */

function serializeBlockHeader(block: bitcoinjs.Block): Buffer {
  const buf = Buffer.alloc(80);
  let offset = 0;
  buf.writeInt32LE(block.version, offset); offset += 4;

  Buffer.from(block.prevHash).copy(buf, offset); offset += 32;
  Buffer.from(block.merkleRoot).copy(buf, offset); offset += 32;

  buf.writeUInt32LE(block.timestamp, offset); offset += 4;
  buf.writeUInt32LE(block.bits, offset); offset += 4;
  buf.writeUInt32LE(block.nonce, offset); offset += 4;

  return buf;
}

export function serializeBlockWithWitness(block: bitcoinjs.Block): Buffer {
  const header = serializeBlockHeader(block);
  const txCount = block.transactions?.length ?? 0;
  const txCountVarInt = encodeVarInt(txCount);

  const txBuffers = (block.transactions || []).map(tx => {
    // Serialize each transaction with witness
    if (typeof (tx as any).__toBuffer === 'function') {
      return (tx as any).__toBuffer(undefined, undefined, true);
    }
    return tx.toBuffer(); // fallback if __toBuffer doesn't exist
  });

  return Buffer.concat([header, txCountVarInt, ...txBuffers]);
}

/** Convenience: hex string the node wants */
export function blockToHex(block: bitcoinjs.Block): string {
  return hex(serializeBlockWithWitness(block));
}

