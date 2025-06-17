# Solidity Examples

This document collects simple smart contracts that work with the integrated Electronero EVM. All examples use Solidity **0.8** or later.

While some snippets below rely on inline `assembly` to demonstrate custom opcodes, contracts do **not** need assembly to run on the EVM. Standard Solidity code compiles and executes just fine. Recent updates expanded opcode coverage to include jumps, bitwise and shift instructions as well as DUP and SWAP so most contracts written for Solidity 0.8 run unmodified.

## Faucet
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Faucet {
    function payout(address payable dest, uint64 amount) public {
        require(address(this).balance >= amount, "Insufficient balance");
        (bool ok, ) = dest.call{value: amount}("");
        require(ok, "Transfer failed");
    }
}
```

## SimpleTreasury
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleTreasury {
    function transferCoins(address payable _to, uint256 _amount) public {
        require(address(this).balance >= _amount, "Insufficient balance");
        (bool sent, ) = _to.call{value: _amount}("");
        require(sent, "Failed to send Coins");
    }
}
```

## BalanceCheck
```solidity
pragma solidity ^0.8.0;

contract BalanceCheck {
    function getBalance() public view returns (uint256) {
        return address(this).balance;
    }
}
```

## BlockInfo
```solidity
pragma solidity ^0.8.0;

contract BlockInfo {
    function current() public view returns (uint256 ts, uint256 height) {
        ts = block.timestamp;
        height = block.number;
    }
}
```

## SelfDestruct Example
```solidity
pragma solidity ^0.8.0;

contract OneShot {
    function burn(address payable to) public {
        selfdestruct(to);
    }
}
```

## Logging
```solidity
pragma solidity ^0.8.0;

contract Notifier {
    event Logged(uint256 id);

    function log(uint256 id) public {
        emit Logged(id);
    }
}
```

## Counter (no assembly)
```solidity
pragma solidity ^0.8.0;

contract Counter {
    uint256 private count;

    function inc() public {
        count += 1;
    }

    function reset() public {
        count = 0;
    }

    function current() public view returns (uint256) {
        return count;
    }
}
```

## SimpleStore (no assembly)
```solidity
pragma solidity ^0.8.0;

contract SimpleStore {
    uint256 private value;

    function set(uint256 v) public {
        value = v;
    }

    function get() public view returns (uint256) {
        return value;
    }
}
```

## Call Data Example
```solidity
pragma solidity ^0.8.0;

contract Args {
    function first(uint64 a) public pure returns (uint64) {
        return a;
    }
}
```
