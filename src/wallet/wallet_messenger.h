#pragma once

#include <string>
#include <vector>
#include "crypto/crypto.h"
#include "cryptonote_basic/account.h"

namespace tools
{

struct wallet_message
{
  uint64_t id;
  std::string from;
  std::string data; // hex encoded encrypted JSON
  uint64_t timestamp;
};

namespace wallet_messenger
{

enum class message_op_type : uint8_t
{
  send = 0
};

uint64_t send_message(const std::string &to_addr, const std::string &from_addr,
                      const std::string &data);

std::string encrypt_message(const std::string &json,
                            const crypto::secret_key &from_view,
                            const crypto::public_key &to_view);
bool decrypt_message(const std::string &data,
                     const crypto::secret_key &to_view,
                     const crypto::public_key &from_view,
                     std::string &json);

std::vector<wallet_message> list_messages(const std::string &address);

wallet_message read_message(const std::string &address, const std::string &key);

std::string make_message_extra(const std::string &to_addr, const std::string &from_addr,
                               const std::string &data);
bool parse_message_extra(const std::string &data, message_op_type &op, std::vector<std::string> &fields);
bool parse_message_extra(const std::string &data, std::string &to_addr, std::string &from_addr,
                         std::string &data_field);

}

} // namespace tools

