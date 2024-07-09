// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import {UQ112x112} from "../src/libraries/UQ112x112.sol";

import {PriceBot} from "../src/PriceBot.sol";
import {BootstrapBot} from "../src/BootstrapBot.sol";
import {AVEX} from "../src/AVEX.sol";

import {IJoeRouter02} from "../src/interfaces/IJoeRouter02.sol";
import {IJoeFactory} from "../src/interfaces/IJoeFactory.sol";
import {IJoePair} from "../src/interfaces/IJoePair.sol";

import {HelperContract} from "./HelperContract.sol";

contract PriceBotTest is Test, HelperContract {
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

  PriceBot public priceBot;
  BootstrapBot public bootstrapBot;

  fallback() external payable {}

  event Receive(uint256 amount);
  receive() external payable {
    emit Receive(msg.value);
  }

  function setUp() public {
    avex = new AVEX();
    bootstrapBot = new BootstrapBot(JOEROUTERV2, LBROUTER, JOEFACTORY, address(avex), WAVAX);
    priceBot = new PriceBot(JOEROUTERV2, LBROUTER, JOEFACTORY, address(avex), WAVAX);
    
    avex.setExcludeFromTransfer(address(bootstrapBot), true);
    Ownable(avex).transferOwnership(address(bootstrapBot));

    avex.transfer(address(bootstrapBot), TOTAL_SUPPLY);

    bootstrapBot.approveToken(JOEROUTERV2, address(avex), TOTAL_SUPPLY);
    bootstrapBot.addLiquidity{value: INITIAL_AVAX_RESERVE}(TOTAL_SUPPLY);
    bootstrapBot.enableTradingAndSwapNativeForTokenConsecutively{value: INITIAL_AVAX_RESERVE}();
  }

  function test_pumpPrice() public {
    vm.expectEmit(false, true, false, false);
    emit Swap(address(this), 0, 0, 0, 0, address(priceBot));

    vm.expectEmit(true, true, false, false);
    emit Transfer(address(priceBot), address(this), 0);

    (uint112 reserve0, uint112 reserve1, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInverted = UQ112x112.encode(reserve0).uqdiv(reserve1);

    uint256 amountAVAXIn = INITIAL_AVAX_RESERVE.div(100).mul(10);
    priceBot.pumpPrice{value: amountAVAXIn}(address(this));

    (uint112 reserve0After, uint112 reserve1After, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInvertedAfter = UQ112x112.encode(reserve0After).uqdiv(reserve1After);

    assertGt(priceInverted, priceInvertedAfter); // ie. price increasing
  }

  function test_dumpPrice() public {
    (uint112 reserve0, uint112 reserve1, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInverted = UQ112x112.encode(reserve0).uqdiv(reserve1);

    uint256 amountTokenIn = uint256(reserve0).div(100).mul(10);
    uint256 amountBalance = avex.balanceOf(address(this));
    assertGt(amountBalance, amountTokenIn);

    avex.approve(address(priceBot), amountTokenIn);
    priceBot.dumpPrice(amountTokenIn);

    (uint112 reserve0After, uint112 reserve1After, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInvertedAfter = UQ112x112.encode(reserve0After).uqdiv(reserve1After);

    assertLt(priceInverted, priceInvertedAfter); // ie. price decreasing
  }
}