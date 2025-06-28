// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function transfer(address recipient, uint256 amount) external returns (bool);
}

contract TokenMarketplace {
    struct Order {
        uint256 id;
        address seller;
        address token;
        address coin;
        uint256 price; // amount of coin per token
        uint256 remaining;
    }

    struct Pair {
        address token;
        address coin;
    }

    uint256 public nextOrderId;
    mapping(uint256 => Order) public orders;
    mapping(bytes32 => uint256[]) private pairOrders;
    Pair[] private pairs;
    mapping(bytes32 => bool) private pairExists;

    event SellOrderPlaced(uint256 indexed id, address indexed seller, address indexed token, address coin, uint256 amount, uint256 price);
    event OrderCancelled(uint256 indexed id, uint256 remaining);
    event OrderFilled(uint256 indexed id, address indexed buyer, uint256 amount, uint256 price);

    function placeSellOrder(address token, address coin, uint256 amount, uint256 price) external returns (uint256 orderId) {
        require(amount > 0, "amount" );
        require(price > 0, "price" );
        IERC20(token).transferFrom(msg.sender, address(this), amount);

        orderId = nextOrderId++;
        orders[orderId] = Order(orderId, msg.sender, token, coin, price, amount);

        bytes32 pairHash = keccak256(abi.encodePacked(token, coin));
        pairOrders[pairHash].push(orderId);
        if (!pairExists[pairHash]) {
            pairExists[pairHash] = true;
            pairs.push(Pair(token, coin));
        }

        emit SellOrderPlaced(orderId, msg.sender, token, coin, amount, price);
    }

    function cancelSellOrder(uint256 orderId) external {
        Order storage order = orders[orderId];
        require(order.seller == msg.sender, "not seller");
        uint256 remaining = order.remaining;
        require(remaining > 0, "filled");
        order.remaining = 0;
        IERC20(order.token).transfer(order.seller, remaining);
        emit OrderCancelled(orderId, remaining);
    }

    function buy(uint256 orderId, uint256 amount) external {
        Order storage order = orders[orderId];
        require(order.remaining >= amount && amount > 0, "amount");
        uint256 cost = amount * order.price;
        order.remaining -= amount;
        IERC20(order.coin).transferFrom(msg.sender, order.seller, cost);
        IERC20(order.token).transfer(msg.sender, amount);
        emit OrderFilled(orderId, msg.sender, amount, cost);
    }

    function listPairs() external view returns (Pair[] memory) {
        return pairs;
    }

    function listOrders(address token, address coin) external view returns (Order[] memory openOrders) {
        bytes32 pairHash = keccak256(abi.encodePacked(token, coin));
        uint256[] storage ids = pairOrders[pairHash];
        uint256 count = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            if (orders[ids[i]].remaining > 0) count++;
        }
        openOrders = new Order[](count);
        uint256 j = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            Order storage o = orders[ids[i]];
            if (o.remaining > 0) {
                openOrders[j++] = o;
            }
        }
    }
}
