# Solidity Examples

This document collects simple smart contracts that work with the integrated Electronero EVM. All examples use Solidity **0.8** or later.

## Faucet
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Faucet {
    function payout(address dest, uint64 amount) public {
        assembly {
            let d := dest
            let a := amount
            mstore(0x0, d)
            mstore(0x20, a)
            pop(call(gas(), 0xa0, 0, 0x0, 0x40, 0, 0))
        }
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
        assembly {
            0x30
            0x31
            return(0, 32)
        }
    }
}
```

## BlockInfo
```solidity
pragma solidity ^0.8.0;

contract BlockInfo {
    function current() public view returns (uint256 ts, uint256 height) {
        assembly {
            0x42
            0x43
            return(0, 64)
        }
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
    function log(uint256 id) public {
        assembly {
            0x60
            id
            0xa1
        }
    }
}
```
