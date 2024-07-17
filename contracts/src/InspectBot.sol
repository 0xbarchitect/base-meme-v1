// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

import "./interfaces/IUniswapV2Router02.sol";
import "./interfaces/IUniswapV2Factory.sol";
import "./interfaces/IUniswapV2Pair.sol";
import "./interfaces/IERC20.sol";

import "./AbstractBot.sol";

contract InspectBot is AbstractBot {
  using SafeMath for uint256;

  constructor(address router, address factory, address erc20, address weth) 
    AbstractBot(router, factory, erc20, weth){}

  function inspect() external onlyOwner payable returns (bool) {
    // long step : swap native for token
    uint256 amountIn = msg.value;
    uint256 deadline = block.timestamp + DEADLINE_BLOCK_DELAY;

    (uint256 reserve0, uint256 reserve1, ) = IUniswapV2Pair(_getPair()).getReserves();
    uint256 amountTokenOut = reserve0 - reserve0.mul(reserve1).div(reserve1 + msg.value);
    _swapNativeForToken(msg.value, amountTokenOut.mul(90).div(100), deadline);

    // short step : swap token for native
    uint256 amountTokenRealized = IERC20(_erc20).balanceOf(address(this));
    IERC20(_erc20).approve(_router, amountTokenRealized);

    (uint256 reserve0After, , ) = IUniswapV2Pair(_getPair()).getReserves();
    uint256 amountETHOut = reserve1 - reserve1.mul(reserve0After).div(reserve0After + amountTokenRealized);
    _swapTokenForNative(amountTokenRealized, amountETHOut.mul(90).div(100), deadline);
  }
}