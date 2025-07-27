import * as bitcoinjs from 'interchainedjs-lib';
import { hex, u8 } from './helpers';

function calculateMerkleRoot(txHashes: Uint8Array[]): Buffer {
    if (txHashes.length === 0) return Buffer.alloc(32, 0);

    let hashes = txHashes.map(h => Buffer.from(h));
    while (hashes.length > 1) {
        const newHashes: Buffer[] = [];
        for (let i = 0; i < hashes.length; i += 2) {
            const left = hashes[i];
            const right = i + 1 < hashes.length ? hashes[i + 1] : left;
            const concat = Buffer.concat([left, right]);
            newHashes.push(Buffer.from(bitcoinjs.crypto.hash256(concat)));
        }
        hashes = newHashes;
    }
    return hashes[0];
}

export function verifyBlock(blockHex: string) {
    console.log("=== Block Verification ===");
    const block = bitcoinjs.Block.fromHex(blockHex);

    console.log("Version:", block.version);
    console.log("PrevHash:", hex(Buffer.from(block.prevHash).reverse()));
    console.log("MerkleRoot (from block):", hex(block.merkleRoot));
    console.log("Timestamp:", block.timestamp);
    console.log("Bits:", block.bits);
    console.log("Nonce:", block.nonce);
    console.log("Transaction Count:", block.transactions.length);

    block.transactions.forEach((tx, idx) => {
        console.log(`\nTx[${idx}] Hash:`, tx.getId());
        console.log("  Hex:", tx.toHex());
        console.log("  Outputs:");
        tx.outs.forEach((o, j) => {
            console.log(`    [${j}] Value: ${o.value} Script: ${hex(o.script)}`);
        });
    });

    // Recalculate Merkle Root
    const txHashes = block.transactions.map(tx => tx.getHash(false));
    const recalculatedMerkleRoot = calculateMerkleRoot(txHashes);
    console.log("\nMerkleRoot (calculated):", hex(recalculatedMerkleRoot));
    console.log("Matches block.merkleRoot?", hex(block.merkleRoot) === hex(recalculatedMerkleRoot));

    // Witness commitment check
    const coinbase = block.transactions[0];
    const witnessCommit = coinbase.outs.find(o => hex(o.script).startsWith("6a24aa21a9ed"));
    console.log("Witness Commitment Output:", witnessCommit ? hex(witnessCommit.script) : "None");

    console.log("=== End Verification ===");
}

// CLI entry
if (require.main === module) {
    const blockHex = process.argv[2];
    if (!blockHex) {
        console.error("Usage: npx ts-node src/utils/verifyBlock.ts <block-hex>");
        process.exit(1);
    }
    verifyBlock(blockHex);
}

