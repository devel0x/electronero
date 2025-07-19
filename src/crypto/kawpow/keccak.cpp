#include "keccak.hpp"
#include <cstring>
#include <algorithm>

static constexpr size_t KECCAKF_ROUNDS = 22;
static constexpr uint64_t keccakf_rndc[KECCAKF_ROUNDS] = {
    0x0000000000000001ULL, 0x0000000000008082ULL,
    0x800000000000808aULL, 0x8000000080008000ULL,
    0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL,
    0x000000000000008aULL, 0x0000000000000088ULL,
    0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL,
    0x8000000000008089ULL, 0x8000000000008003ULL,
    0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL,
    0x8000000080008081ULL, 0x8000000000008080ULL
};

static const int keccakf_rotc[25] = {
     0, 36,  3, 41, 18,
     1, 44, 10, 45,  2,
    62,  6, 43, 15, 61,
    28, 55, 25, 21, 56,
    27, 20, 39,  8, 14
};

static const int keccakf_piln[25] = {
     0,  1,  6,  9, 22,
     2, 12, 13, 19, 23,
     3,  7,  8, 14, 20,
     4, 15, 16, 21, 24,
     5, 10, 11, 17, 18
};

static void keccakf(uint64_t st[25]) {
    for (size_t round = 0; round < KECCAKF_ROUNDS; ++round) {
        uint64_t bc[5], t;

        for (int i = 0; i < 5; ++i)
            bc[i] = st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20];

        for (int i = 0; i < 5; ++i) {
            t = bc[(i + 4) % 5] ^ ((bc[(i + 1) % 5] << 1) | (bc[(i + 1) % 5] >> (64 - 1)));
            for (int j = 0; j < 25; j += 5)
                st[j + i] ^= t;
        }

        t = st[1];
        for (int i = 0; i < 24; ++i) {
            int j = keccakf_piln[i];
            bc[0] = st[j];
            st[j] = (t << keccakf_rotc[i + 1]) | (t >> (64 - keccakf_rotc[i + 1]));
            t = bc[0];
        }

        for (int j = 0; j < 25; j += 5) {
            for (int i = 0; i < 5; ++i)
                bc[i] = st[j + i];
            for (int i = 0; i < 5; ++i)
                st[j + i] ^= (~bc[(i + 1) % 5]) & bc[(i + 2) % 5];
        }

        st[0] ^= keccakf_rndc[round];
    }
}

void keccak_f800(const uint8_t* input, uint8_t* output) {
    uint64_t state[25];
    std::memset(state, 0, sizeof(state));
    std::memcpy(state, input, std::min<size_t>(40, 200)); // f800 = 800 bits = 100 bytes max

    keccakf(state);
    std::memcpy(output, state, 32); // Return 256-bit hash
}
