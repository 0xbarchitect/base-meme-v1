// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

import "./interfaces/IJoeRouter02.sol";
import "./interfaces/IJoeRouter01.sol";
import "./interfaces-v2/ILBRouter.sol";
import "./interfaces/IJoePair.sol";

import "./AVEX.sol";
import "./AbstractBot.sol";

contract VolumeBot is AbstractBot {
  using SafeMath for uint256;

  constructor(address joeRouter, address lbRouter, address joeFactory, address avex, address wavax) 
    AbstractBot(joeRouter, lbRouter, joeFactory, avex, wavax){}

  function makeVolume() external onlyOwner payable {
    // long step : swap native for token
    (uint256 reserve0, uint256 reserve1, ) = IJoePair(_getPair()).getReserves();
    uint256 amountTokenOut = reserve0 - reserve0.mul(reserve1).div(reserve1 + msg.value);
    _swapNativeForToken(msg.value, amountTokenOut.mul(90).div(100));

    // short step : swap token for native
    uint256 amountTokenRealized = AVEX(_avex).balanceOf(address(this));
    AVEX(_avex).approve(_joeRouterV2, amountTokenRealized);
    AVEX(_avex).approve(_lbRouter, amountTokenRealized);

    (uint256 reserve0After, , ) = IJoePair(_getPair()).getReserves();
    uint256 amountAVAXOut = reserve1 - reserve1.mul(reserve0After).div(reserve0After + amountTokenRealized);
    _swapTokenForNative(amountTokenRealized, amountAVAXOut.mul(90).div(100));
  }
}