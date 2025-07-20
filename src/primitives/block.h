// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2018 The Interchained Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_PRIMITIVES_BLOCK_H
#define BITCOIN_PRIMITIVES_BLOCK_H

#include <primitives/transaction.h>
#include <serialize.h>
#include <uint256.h>
#include "consensus/params.h"

/** Nodes collect new transactions into a block, hash them into a hash tree,
 * and scan through nonce values to make the block's hash satisfy proof-of-work
 * requirements.  When they solve the proof-of-work, they broadcast the block
 * to everyone and the block is added to the block chain.  The first transaction
 * in the block is a special one that creates a new coin owned by the creator
 * of the block.
 */
class CBlockHeader
{
public:
    // header
    int32_t nVersion;
    uint256 hashPrevBlock;
    uint256 hashMerkleRoot;
    uint32_t nTime;
    uint32_t nBits;
    uint32_t nNonce;
    
    // KAWPOW additions
    uint64_t nNonce64{0};
    uint256 mixHash;
    uint256 hashKawpowSeed; // optionally precomputed in block template

    CBlockHeader()
    {
        SetNull();
    }

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action) {
        READWRITE(nVersion);
        READWRITE(hashPrevBlock);
        READWRITE(hashMerkleRoot);
        READWRITE(nTime);
        READWRITE(nBits);

        if ((nVersion & 0xFFFFFFF0) == VERSIONBITS_KAWPOW) {
            READWRITE(nNonce64);
            READWRITE(mixHash);
            READWRITE(hashKawpowSeed);
        } else {
            READWRITE(nNonce);
        }
    }
    
    SERIALIZE_METHODS(CBlockHeader, obj);

    template<typename Stream, typename Operation>
    static inline void SerializationOps(CBlockHeader& obj, Stream& s, Operation ser_action) {
        obj.SerializationOp(s, ser_action);
    }

    template<typename Stream, typename Operation>
    static inline void SerializationOps(const CBlockHeader& obj, Stream& s, Operation ser_action) {
        const_cast<CBlockHeader&>(obj).SerializationOp(s, ser_action);
    }

    template <typename Stream>
    void SerializeForHash(Stream& s, int height) const {
        s << nVersion;
        s << hashPrevBlock;
        s << hashMerkleRoot;
        s << nTime;
        s << nBits;

        if ((nVersion & 0xFFFFFFF0) == VERSIONBITS_KAWPOW) {
            // This is a KAWPOW-style block — serialize extended fields
            s << nNonce64;
            s << mixHash;
            s << hashKawpowSeed;
        } else {
            s << nNonce;
        }
    }

    void SetNull()
    {
        nVersion = 0;
        hashPrevBlock.SetNull();
        hashMerkleRoot.SetNull();
        nTime = 0;
        nBits = 0;
        nNonce = 0;
        nNonce64 = 0;
        mixHash.SetNull();
        hashKawpowSeed.SetNull();
    }

    bool IsNull() const
    {
        return (nBits == 0);
    }

    uint256 GetHash() const;

    uint256 YespowerHash(int height) const;

    uint256 GetKAWPOWHeaderHash() const;

    int64_t GetBlockTime() const
    {
        return (int64_t)nTime;
    }
};

class CBlock : public CBlockHeader
{
public:
    // network and disk
    std::vector<CTransactionRef> vtx;

    // memory only
    mutable bool fChecked;

    // SegWit witness data
    std::vector<std::vector<unsigned char>> vchWitness;

    CBlock()
    {
        SetNull();
    }

    CBlock(const CBlockHeader &header)
    {
        SetNull();
        *(static_cast<CBlockHeader*>(this)) = header;
    }

    SERIALIZE_METHODS(CBlock, obj)
    {
        // Serialize the header portion of the block
        READWRITEAS(CBlockHeader, obj);

        // Serialize the transactions vector
        READWRITE(obj.vtx);

        // Serialize vchWitness if block has previous block (not genesis) and includes witness
        if (obj.hashPrevBlock != uint256() && obj.vtx.size() > 0 && obj.vtx[0]->HasWitness()) {
            READWRITE(obj.vchWitness);
        }
    }

    void SetNull()
    {
        CBlockHeader::SetNull();
        vtx.clear();
        fChecked = false;
        vchWitness.clear(); // Clear the witness data
    }

    CBlockHeader GetBlockHeader() const
    {
        CBlockHeader block;
        block.nVersion       = nVersion;
        block.hashPrevBlock  = hashPrevBlock;
        block.hashMerkleRoot = hashMerkleRoot;
        block.nTime          = nTime;
        block.nBits          = nBits;
        block.nNonce         = nNonce;
        return block;
    }
    
    static bool IsGenesisBlock(const CBlock& block)
    {
        // Convert the hex string to uint256
        uint256 genesisBlockHash;
        genesisBlockHash.SetHex("0x00000000ed361749ae598d60cd78395eb526bc90f5e1198f0b045f95cecc80c8");
    
        return block.GetHash() == genesisBlockHash;
    }


    std::string ToString() const;

};

/** Describes a place in the block chain to another node such that if the
 * other node doesn't have the same branch, it can find a recent common trunk.
 * The further back it is, the further before the fork it may be.
 */
struct CBlockLocator
{
    std::vector<uint256> vHave;

    CBlockLocator() {}

    explicit CBlockLocator(const std::vector<uint256>& vHaveIn) : vHave(vHaveIn) {}

    SERIALIZE_METHODS(CBlockLocator, obj)
    {
        int nVersion = s.GetVersion();
        if (!(s.GetType() & SER_GETHASH))
            READWRITE(nVersion);
        READWRITE(obj.vHave);
    }

    void SetNull()
    {
        vHave.clear();
    }

    bool IsNull() const
    {
        return vHave.empty();
    }
};

#endif // BITCOIN_PRIMITIVES_BLOCK_H