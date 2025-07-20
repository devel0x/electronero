#include "progpow.hpp"
#include "ethash.hpp"
#include "keccak.hpp"
#include <cstring>
#include <vector>

namespace progpow {

static constexpr uint32_t CACHE_BYTES_INIT = ETHASH_LIGHT_INIT_BYTES;
static constexpr uint32_t CACHE_BYTES_GROWTH = ETHASH_LIGHT_GROWTH_BYTES;
static constexpr uint32_t CACHE_MIX_BYTES = ETHASH_LIGHT_CACHE_MIX_BYTES;

struct progpow_context {
    ethash_light_cache cache;
    uint32_t epoch;
};

static progpow_context* ctx = nullptr;

void initialize_cache(uint32_t epoch) {
    if (ctx && ctx->epoch == epoch) return;
    delete ctx;
    ctx = new progpow_context();
    ctx->epoch = epoch;
    ethash_light_new(&ctx->cache, epoch);
}

void finalize_context() {
    delete ctx;
    ctx = nullptr;
}

void progpow_hash(uint32_t epoch,
                  const std::array<uint8_t, 32>& header_hash,
                  uint64_t nonce,
                  hash256& result,
                  hash256& mix) {
    initialize_cache(epoch);
    ethash_return_value rv = ethash_light_compute(&ctx->cache, header_hash.data(), nonce);
    std::copy(rv.mix_hash, rv.mix_hash + 32, mix.bytes.begin());
    std::copy(rv.result, rv.result + 32, result.bytes.begin());
}

bool search(
    uint32_t epoch,
    const std::array<uint8_t, 32>& header_hash,
    uint64_t start_nonce,
    uint64_t* found_nonce,
    hash256& mix,
    hash256& result,
    const arith_uint256& target)
{
    initialize_cache(epoch);

    uint64_t local_nonce = 0;

    bool success = ethash_light_search(
        &ctx->cache,
        header_hash.data(),
        start_nonce,
        local_nonce,                   // 4th param is found_nonce (as reference)
        mix.bytes.data(),             // 5th: mix hash
        result.bytes.data(),          // 6th: result hash
        target                        // 7th: target
    );

    if (success && found_nonce) {
        *found_nonce = local_nonce;
    }

    return success;
}

} // namespace progpow
