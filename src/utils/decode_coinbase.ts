import * as bitcoinjs from 'interchainedjs-lib';
import { hex } from './helpers';
export function decodeCoinbase(hexstring: string) {
    const tx = bitcoinjs.Transaction.fromHex(hexstring);

    console.log("=== Coinbase Transaction Decode ===");
    console.log("Version:", tx.version);
    console.log("Input Count:", tx.ins.length);

    tx.ins.forEach((input, idx) => {
        console.log(`Input[${idx}]`);
        console.log("  Script Length:", input.script.length);
        console.log("  Script (hex):", hex(input.script));
        console.log("  Sequence:", input.sequence.toString(16));
    });

    console.log("Output Count:", tx.outs.length);
    let total = 0n;
    tx.outs.forEach((output, idx) => {
        console.log(`Output[${idx}]`);
        console.log("  Value:", output.value);
        console.log("  Script (hex):", hex(output.script));
        total += BigInt(output.value);
    });

    console.log("Total Output Value:", total.toString());
    console.log("Locktime:", tx.locktime);
    console.log("===================================");
}

// Example standalone run
if (require.main === module) {
    const hexInput = process.argv[2];
    if (!hexInput) {
        console.error("Usage: ts-node src/utils/decode_coinbase.ts <coinbase-hex>");
        process.exit(1);
    }
    decodeCoinbase(hexInput);
}

