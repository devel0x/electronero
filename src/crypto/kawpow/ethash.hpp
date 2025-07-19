#ifndef BITCOIN_CRYPTO_ETHASH_HPP
#define BITCOIN_CRYPTO_ETHASH_HPP

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Constants for DAG calculation
static const size_t ETHASH_EPOCH_LENGTH = 7500;
static const size_t ETHASH_LIGHT_INIT_BYTES = 1 << 24; // 16 MB
static const size_t ETHASH_LIGHT_GROWTH_BYTES = 1 << 17; // 128 KB per epoch
static const size_t ETHASH_LIGHT_CACHE_MIX_BYTES = 128;

typedef struct {
    uint8_t* cache;
    size_t cache_size;
} ethash_light_cache;

typedef struct {
    uint8_t result[32];
    uint8_t mix_hash[32];
} ethash_return_value;

// Allocates and generates a new light cache
inline void ethash_light_new(ethash_light_cache* light, uint32_t epoch) {
    light->cache_size = ETHASH_LIGHT_INIT_BYTES + ETHASH_LIGHT_GROWTH_BYTES * epoch;
    light->cache = (uint8_t*)malloc(light->cache_size);
    for (size_t i = 0; i < light->cache_size; ++i)
        light->cache[i] = (uint8_t)(i ^ epoch);  // simple deterministic pattern
}

// Frees light cache
inline void ethash_light_delete(ethash_light_cache* light) {
    if (light && light->cache) {
        free(light->cache);
        light->cache = nullptr;
        light->cache_size = 0;
    }
}

// Performs a fake DAG hash (used in both verify and search)
inline ethash_return_value ethash_light_compute(ethash_light_cache* light, const uint8_t* header, uint64_t nonce) {
    ethash_return_value ret;
    for (int i = 0; i < 32; ++i) {
        ret.mix_hash[i] = light->cache[(i + nonce) % light->cache_size] ^ header[i % 32];
        ret.result[i] = ret.mix_hash[i] ^ (uint8_t)(nonce >> (i % 8));
    }
    return ret;
}

// Basic nonce search for solo mining (linear scan)
inline bool ethash_light_search(ethash_light_cache* light,
                                 const uint8_t* header,
                                 uint64_t start_nonce,
                                 uint64_t& found_nonce,
                                 uint8_t* out_mix,
                                 uint8_t* out_hash,
                                 const arith_uint256& target)
{
    for (uint64_t i = 0; i < 0x100000; ++i) {
        uint64_t nonce = start_nonce + i;
        ethash_return_value rv = ethash_light_compute(light, header, nonce);

        arith_uint256 h;
        memcpy(h.begin(), rv.result, 32);
        if (h <= target) {
            found_nonce = nonce;
            memcpy(out_mix, rv.mix_hash, 32);
            memcpy(out_hash, rv.result, 32);
            return true;
        }
    }
    return false;
}

#endif // BITCOIN_CRYPTO_ETHASH_HPP
