#!/usr/bin/env node
/* eslint-disable no-console */
const bitcoin = require('interchainedjs-lib'); // Use bitcoinjs-lib
const crypto = require('crypto');
const { Buffer } = require('buffer');

// Helper to ensure Buffer type
const u8 = (b) => (Buffer.isBuffer(b) ? b : Buffer.from(b));

// ---------- CONFIG: FILL THESE ----------
const COINBASE_TX_HEX =
  '020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff1702195e135075626c69632d506f6f6c0000000000000000ffffffff04987f3300000000001600147631393b48154acfc24c4c53a733bbfaf60692cea8ba350d000000001600147631393b48154acfc24c4c53a733bbfaf60692ce40787d01000000001600147631393b48154acfc24c4c53a733bbfaf60692ce0000000000000000266a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf90120000000000000000000000000000000000000000000000000000000000000000000000000';

// Add *all* non-coinbase tx hex here (if none, leave empty array).
const OTHER_TXS = [
  // '...'
];

// Header fields (fill with the ones you are mining with, EXCEPT merkleRoot which we recompute)
const header = {
  version: 0x20000002, // example: 0x20000002 => 0x02000020 LE in hex
  prevHash:
    '0000000083e04191cd00ac7a9d2c438e328ae624caf54304c3c6a73e5aff491c', // big-endian
  time: 0x6686cb9f, // nTime
  bits: 0x1dffff00, // nBits
  nonce: 1, // put the actual nonce you’re submitting
};
// ---------------------------------------

function dsha256(buf) {
  buf = u8(buf);
  return crypto
    .createHash('sha256')
    .update(crypto.createHash('sha256').update(buf).digest())
    .digest();
}

function hexToLEBuffer(beHex) {
  return Buffer.from(beHex, 'hex').reverse();
}

function leBufToHex(beBufLE) {
  return Buffer.from(beBufLE).reverse().toString('hex');
}

function varint(n) {
  if (n < 0xfd) return Buffer.from([n]);
  if (n <= 0xffff) {
    const b = Buffer.allocUnsafe(3);
    b[0] = 0xfd;
    b.writeUInt16LE(n, 1);
    return b;
  }
  if (n <= 0xffffffff) {
    const b = Buffer.allocUnsafe(5);
    b[0] = 0xfe;
    b.writeUInt32LE(n, 1);
    return b;
  }
  // 64-bit
  const b = Buffer.allocUnsafe(9);
  b[0] = 0xff;
  b.writeBigUInt64LE(BigInt(n), 1);
  return b;
}

// Merkle root over txids (legacy txids, not wtxids)
function merkleRoot(txidsLE) {
  let layer = txidsLE.map(u8);
  while (layer.length > 1) {
    if (layer.length % 2 === 1) {
      layer.push(layer[layer.length - 1]); // duplicate last
    }
    const next = [];
    for (let i = 0; i < layer.length; i += 2) {
      next.push(
        dsha256(Buffer.concat([u8(layer[i]), u8(layer[i + 1])]))
      );
    }
    layer = next;
  }
  return u8(layer[0]);
}

// Build the block
function buildBlock() {
  // 1) Parse all txs
  const rawTxHexes = [COINBASE_TX_HEX, ...OTHER_TXS];

  // Parse with bitcoinjs so we get correct txid (legacy: getHash())
  const txs = rawTxHexes.map((h) => bitcoin.Transaction.fromHex(h));

  // 2) Compute txids (legacy, LE buffer)
  const txidsLE = txs.map((tx) => u8(tx.getHash())); // returns LE buffer
  const merkle = u8(merkleRoot(txidsLE)); // ensure Buffer

  // 3) Compose 80-byte header
  const hdr = Buffer.allocUnsafe(80);

  hdr.writeInt32LE(header.version, 0);

  // prevHash in block header is LE
  hexToLEBuffer(header.prevHash).copy(hdr, 4);

  // Merkle root is LE already
  merkle.copy(hdr, 36);

  hdr.writeUInt32LE(header.time, 68);
  hdr.writeUInt32LE(header.bits, 72);
  hdr.writeUInt32LE(header.nonce, 76);

  // 4) Serialize block: header + varint(txcount) + all txs (full, with witness)
  const txCount = rawTxHexes.length;
  const blockParts = [hdr, varint(txCount)];
  for (const h of rawTxHexes) {
    blockParts.push(Buffer.from(h, 'hex'));
  }
  const block = Buffer.concat(blockParts);

  console.log('---------- RESULTS ----------');
  console.log('Merkle root (BE):', leBufToHex(merkle));
  console.log('Block header (hex):', hdr.toString('hex'));
  console.log('Block hash (BE):', leBufToHex(dsha256(hdr)));
  console.log('Full block hex:', block.toString('hex'));
}

buildBlock();

