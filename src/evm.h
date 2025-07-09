#ifndef BITCOIN_EVM_H
#define BITCOIN_EVM_H

#include <string>

std::string ImportEthKey(const std::string& key_hex);
std::string EVMDeploy(const std::string& from, const std::string& bytecode);
std::string EVMCall(const std::string& from, const std::string& contract, const std::string& data);

/** Load EVM keys and contract state from disk. */
void LoadEVMState();

/** Flush EVM keys and contract state to disk. */
void DumpEVMState();

#endif // BITCOIN_EVM_H
