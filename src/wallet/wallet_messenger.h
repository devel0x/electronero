#pragma once

#include <string>
#include <vector>

namespace tools
{

struct wallet_message
{
  uint64_t id;
  std::string from;
  std::string subject;
  std::string message;
  uint64_t timestamp;
};

namespace wallet_messenger
{

uint64_t send_message(const std::string &to_addr, const std::string &from_addr,
                      const std::string &subject, const std::string &body);

std::vector<wallet_message> list_messages(const std::string &address);

wallet_message read_message(const std::string &address, const std::string &key);

std::string make_message_extra(const std::string &to_addr, const std::string &from_addr,
                               const std::string &subject, const std::string &body);
bool parse_message_extra(const std::string &data, std::string &to_addr, std::string &from_addr,
                         std::string &subject, std::string &body);

}

} // namespace tools

