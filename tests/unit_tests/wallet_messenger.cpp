#include "gtest/gtest.h"
#include "wallet/wallet_messenger.h"
#include <boost/filesystem.hpp>
#include <cstdlib>

TEST(wallet_messenger, send_and_read)
{
  boost::filesystem::path dir = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path();
  boost::filesystem::create_directories(dir);
  setenv("MESSAGE_DIR", dir.string().c_str(), 1);

  std::string to = "alice";
  std::string from = "bob";
  uint64_t id = tools::wallet_messenger::send_message(to, from, "hello", "hi alice");
  ASSERT_EQ(id, 1);

  auto msgs = tools::wallet_messenger::list_messages(to);
  ASSERT_EQ(msgs.size(), 1);
  ASSERT_EQ(msgs[0].subject, "hello");

  auto msg = tools::wallet_messenger::read_message(to, "hello");
  ASSERT_EQ(msg.message, "hi alice");

  unsetenv("MESSAGE_DIR");
  boost::filesystem::remove_all(dir);
}

TEST(wallet_messenger, make_and_parse_extra)
{
  std::string extra = tools::wallet_messenger::make_message_extra("alice", "bob", "sub", "body");
  std::string to, from, subject, body;
  ASSERT_TRUE(tools::wallet_messenger::parse_message_extra(extra, to, from, subject, body));
  ASSERT_EQ(to, "alice");
  ASSERT_EQ(from, "bob");
  ASSERT_EQ(subject, "sub");
  ASSERT_EQ(body, "body");
}

TEST(wallet_messenger, parse_extra_op)
{
  std::string extra = tools::wallet_messenger::make_message_extra("alice", "bob", "sub", "body");
  tools::wallet_messenger::message_op_type op;
  std::vector<std::string> fields;
  ASSERT_TRUE(tools::wallet_messenger::parse_message_extra(extra, op, fields));
  ASSERT_EQ(op, tools::wallet_messenger::message_op_type::send);
  ASSERT_EQ(fields.size(), 4);
  ASSERT_EQ(fields[0], "alice");
  ASSERT_EQ(fields[1], "bob");
  ASSERT_EQ(fields[2], "sub");
  ASSERT_EQ(fields[3], "body");
}
