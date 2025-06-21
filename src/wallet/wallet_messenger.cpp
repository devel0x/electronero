#include "wallet_messenger.h"

#include <fstream>
#include <cstdlib>
#include <algorithm>
#include <sstream>
#include <boost/filesystem.hpp>
#include "serialization/json_object.h"
#include "crypto/chacha.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "common/hex.h"
#include "string_tools.h"
#include "crypto/hash.h"
#include "common/util.h"

namespace tools
{
namespace wallet_messenger
{

static std::string get_message_dir()
{
  const char *env = std::getenv("MESSAGE_DIR");
  if (env && *env)
    return std::string(env);
  return "messages"; // default relative directory
}

static std::string msg_file(const std::string &address)
{
  return (boost::filesystem::path(get_message_dir()) / (address + ".json")).string();
}

static std::vector<wallet_message> load_messages(const std::string &address)
{
  std::vector<wallet_message> msgs;
  const std::string path = msg_file(address);
  if (!boost::filesystem::exists(path))
    return msgs;

  std::ifstream f(path);
  if (!f)
    return msgs;
  std::string data((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
  rapidjson::Document doc;
  if (doc.Parse(data.c_str()).HasParseError() || !doc.IsArray())
    return msgs;
  for (auto &v : doc.GetArray())
  {
    wallet_message m{};
    if (v.HasMember("id")) m.id = v["id"].GetUint64();
    if (v.HasMember("from")) m.from = v["from"].GetString();
    if (v.HasMember("data")) m.data = v["data"].GetString();
    if (v.HasMember("timestamp")) m.timestamp = v["timestamp"].GetUint64();
    msgs.push_back(std::move(m));
  }
  return msgs;
}

static void save_messages(const std::string &address, const std::vector<wallet_message> &msgs)
{
  boost::filesystem::path dir = get_message_dir();
  boost::filesystem::create_directories(dir);

  rapidjson::Document doc;
  doc.SetArray();
  rapidjson::Document::AllocatorType &alloc = doc.GetAllocator();
  for (const auto &m : msgs)
  {
    rapidjson::Value val(rapidjson::kObjectType);
    INSERT_INTO_JSON_OBJECT(val, doc, id, m.id);
    INSERT_INTO_JSON_OBJECT(val, doc, from, m.from);
    INSERT_INTO_JSON_OBJECT(val, doc, data, m.data);
    INSERT_INTO_JSON_OBJECT(val, doc, timestamp, m.timestamp);
    doc.PushBack(val, alloc);
  }
  rapidjson::StringBuffer buffer;
  rapidjson::PrettyWriter<rapidjson::StringBuffer> writer(buffer);
  doc.Accept(writer);
  std::ofstream f(msg_file(address));
  f << buffer.GetString();
}

uint64_t send_message(const std::string &to_addr, const std::string &from_addr,
                      const std::string &data)
{
  auto msgs = load_messages(to_addr);
  uint64_t next_id = 0;
  for (const auto &m : msgs)
    if (m.id > next_id) next_id = m.id;
  next_id += 1;
  wallet_message m{next_id, from_addr, data, static_cast<uint64_t>(time(nullptr))};
  msgs.push_back(m);
  save_messages(to_addr, msgs);
  return next_id;
}

std::vector<wallet_message> list_messages(const std::string &address)
{
  return load_messages(address);
}

wallet_message read_message(const std::string &address, const std::string &key)
{
  auto msgs = load_messages(address);
  for (const auto &m : msgs)
  {
    if (std::to_string(m.id) == key)
      return m;
  }
  throw std::runtime_error("message not found");
}

std::string encrypt_message(const std::string &json,
                            const crypto::secret_key &from_view,
                            const crypto::public_key &to_view)
{
  crypto::key_derivation derivation;
  if(!crypto::generate_key_derivation(to_view, from_view, derivation))
    throw std::runtime_error("failed to generate key derivation");
  crypto::hash hash_key;
  cn_fast_hash(&derivation, sizeof(derivation), reinterpret_cast<char*>(&hash_key));
  crypto::chacha_key key;
  memcpy(key.data(), &hash_key, sizeof(key));
  crypto::hash hash_iv;
  cn_fast_hash(&hash_key, sizeof(hash_key), reinterpret_cast<char*>(&hash_iv));
  crypto::chacha_iv iv;
  memcpy(iv.data, &hash_iv, CHACHA_IV_SIZE);
  std::string cipher(json.size(), '\0');
  crypto::chacha20(json.data(), json.size(), key, iv, &cipher[0]);
  return epee::string_tools::buff_to_hex_nodelimer(cipher);
}

bool decrypt_message(const std::string &data,
                     const crypto::secret_key &to_view,
                     const crypto::public_key &from_view,
                     std::string &json)
{
  std::string cipher;
  if(!epee::string_tools::parse_hexstr_to_binbuff(data, cipher))
    return false;
  crypto::key_derivation derivation;
  if(!crypto::generate_key_derivation(from_view, to_view, derivation))
    return false;
  crypto::hash hash_key;
  cn_fast_hash(&derivation, sizeof(derivation), reinterpret_cast<char*>(&hash_key));
  crypto::chacha_key key;
  memcpy(key.data(), &hash_key, sizeof(key));
  crypto::hash hash_iv;
  cn_fast_hash(&hash_key, sizeof(hash_key), reinterpret_cast<char*>(&hash_iv));
  crypto::chacha_iv iv;
  memcpy(iv.data, &hash_iv, CHACHA_IV_SIZE);
  json.resize(cipher.size());
  crypto::chacha20(cipher.data(), cipher.size(), key, iv, &json[0]);
  return true;
}

std::string make_message_extra(const std::string &to_addr, const std::string &from_addr,
                               const std::string &data)
{
  std::ostringstream oss;
  oss << static_cast<int>(message_op_type::send) << '\t' << to_addr << '\t'
      << from_addr << '\t' << data;
  return oss.str();
}

bool parse_message_extra(const std::string &data, message_op_type &op, std::vector<std::string> &fields)
{
  std::istringstream iss(data);
  int op_int;
  if(!(iss >> op_int))
    return false;
  op = static_cast<message_op_type>(op_int);
  if (iss.peek() == '\t')
    iss.get();
  std::string field;
  while(std::getline(iss, field, '\t'))
    fields.push_back(field);
  return true;
}

bool parse_message_extra(const std::string &data, std::string &to_addr, std::string &from_addr,
                         std::string &data_field)
{
  message_op_type op;
  std::vector<std::string> fields;
  if(!parse_message_extra(data, op, fields))
    return false;
  if(op != message_op_type::send || fields.size() != 3)
    return false;
  to_addr = fields[0];
  from_addr = fields[1];
  data_field = fields[2];
  return true;
}

} // namespace wallet_messenger
} // namespace tools

