// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import {UQ112x112} from "../src/libraries/UQ112x112.sol";

import {VolumeBot} from "../src/VolumeBot.sol";
import {BootstrapBot} from "../src/BootstrapBot.sol";
import {AVEX} from "../src/AVEX.sol";

import {IJoeRouter02} from "../src/interfaces/IJoeRouter02.sol";
import {IJoeFactory} from "../src/interfaces/IJoeFactory.sol";
import {IJoePair} from "../src/interfaces/IJoePair.sol";

import {HelperContract} from "./HelperContract.sol";

contract VolumeBotTest is Test, HelperContract {
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

  VolumeBot public volumeBot;
  BootstrapBot public bootstrapBot;

  fallback() external payable {}

  event Receive(uint256 amount);
  receive() external payable {
    emit Receive(msg.value);
  }

  function setUp() public {
    avex = new AVEX();
    bootstrapBot = new BootstrapBot(JOEROUTERV2, LBROUTER, JOEFACTORY, address(avex), WAVAX);
    volumeBot = new VolumeBot(JOEROUTERV2, LBROUTER, JOEFACTORY, address(avex), WAVAX);
    
    avex.setExcludeFromTransfer(address(bootstrapBot), true);
    Ownable(avex).transferOwnership(address(bootstrapBot));

    avex.transfer(address(bootstrapBot), TOTAL_SUPPLY);

    bootstrapBot.approveToken(JOEROUTERV2, address(avex), TOTAL_SUPPLY);
    bootstrapBot.addLiquidity{value: INITIAL_AVAX_RESERVE}(TOTAL_SUPPLY);
    bootstrapBot.enableTradingAndSwapNativeForTokenConsecutively{value: INITIAL_AVAX_RESERVE}();
  }

  function test_makeVolume() public {
    vm.expectEmit(false, true, false, false);
    emit Swap(address(this), 0, 0, 0, 0, address(volumeBot));

    vm.expectEmit(false, false, false, false);
    emit Receive(0);

    (uint112 reserve0, , ) = IJoePair(_getPair()).getReserves();
    
    volumeBot.makeVolume{value: INITIAL_AVAX_RESERVE}();

    (uint112 reserve0After, , ) = IJoePair(_getPair()).getReserves();

    assertEq(reserve0, reserve0After);
  }

}