#ifndef BITCOIN_EVM_H
#define BITCOIN_EVM_H

#include <string>

std::string ImportEthKey(const std::string& key_hex);
std::string EVMDeploy(const std::string& from, const std::string& bytecode);
std::string EVMCall(const std::string& from, const std::string& contract, const std::string& data);

#endif // BITCOIN_EVM_H
