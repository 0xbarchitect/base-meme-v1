// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "../src/libraries/UQ112x112.sol";

import "../src/interfaces/IUniswapV2Router02.sol";
import "../src/interfaces/IUniswapV2Factory.sol";
import "../src/interfaces/IUniswapV2Pair.sol";

import {HelperContract} from "./HelperContract.sol";
import {InspectBot} from "../src/InspectBot.sol";
import {BootstrapBot} from "../src/BootstrapBot.sol";
import {ERC20Token} from "../src/ERC20Token.sol";

contract InspectBotTest is Test, HelperContract {
  uint256 private constant INSPECT_VALUE = 10**15;

  event Swap(
    address indexed sender,
    uint256 amount0In,
    uint256 amount1In,
    uint256 amount0Out,
    uint256 amount1Out,
    address indexed to
  );

  event Transfer(address indexed from, address indexed to, uint256 amount);

  using SafeMath for uint256;
  using UQ112x112 for uint224;

  InspectBot public inspectBot;
  BootstrapBot public bootstrapBot;

  fallback() external payable {}

  receive() external payable {}

  function setUp() public {
    token = new ERC20Token();
    bootstrapBot = new BootstrapBot(ROUTERV2, FACTORYV2, address(token), WETH);
    inspectBot = new InspectBot(ROUTERV2, FACTORYV2, address(token), WETH);

    token.transfer(address(bootstrapBot), TOTAL_SUPPLY);
    bootstrapBot.approveToken(ROUTERV2, address(token), TOTAL_SUPPLY);
    bootstrapBot.addLiquidity{value: INITIAL_AVAX_RESERVE}(TOTAL_SUPPLY);
  }

  function test_inspect() public {
    //bool sent = payable(address(inspectBot)).send(INSPECT_VALUE);
    //require(sent, "Sent value failed");
    
    (uint256 amountIn, uint256 amountReceived) = inspectBot.inspect{value: INSPECT_VALUE}();

    assertEq(amountIn, INSPECT_VALUE);
    assertGt(amountReceived, 0);
  }

}