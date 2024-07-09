// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import {UQ112x112} from "../src/libraries/UQ112x112.sol";

import {BootstrapBot} from "../src/BootstrapBot.sol";
import {AVEX} from "../src/AVEX.sol";

import {IJoeRouter02} from "../src/interfaces/IJoeRouter02.sol";
import {IJoeFactory} from "../src/interfaces/IJoeFactory.sol";
import {IJoePair} from "../src/interfaces/IJoePair.sol";

import {HelperContract} from "./HelperContract.sol";

contract BootstrapBotTest is Test, HelperContract {
  using SafeMath for uint256;
  using UQ112x112 for uint224;

  BootstrapBot public bot;  

  function setUp() public {
    avex = new AVEX();
    bot = new BootstrapBot(JOEROUTERV2, LBROUTER, JOEFACTORY, address(avex), WAVAX);
    
    avex.setExcludeFromTransfer(address(bot), true);
    Ownable(avex).transferOwnership(address(bot));

    avex.transfer(address(bot), TOTAL_SUPPLY);

    bot.approveToken(JOEROUTERV2, address(avex), TOTAL_SUPPLY);
    bot.addLiquidity{value: INITIAL_AVAX_RESERVE}(TOTAL_SUPPLY);
  }

  function test_enableTradingAndSwapTokenConsecutively() public {
    (uint112 reserve0, uint112 reserve1, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInverted = UQ112x112.encode(reserve0).uqdiv(reserve1);

    uint256 amountAVAXIn = INITIAL_AVAX_RESERVE * 9; // make price x100

    bot.enableTradingAndSwapNativeForTokenConsecutively{value: amountAVAXIn}();

    (uint112 reserve0After, uint112 reserve1After, ) = IJoePair(_getPair()).getReserves();
    uint224 priceInvertedAfter = UQ112x112.encode(reserve0After).uqdiv(reserve1After);

    assertGt(reserve0, reserve0After);
    assertEq(reserve1After, reserve1 + amountAVAXIn);    

    assertGe(priceInverted / priceInvertedAfter , 99);
  }
}