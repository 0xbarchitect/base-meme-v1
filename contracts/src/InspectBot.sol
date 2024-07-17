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

  fallback() external payable {}

  receive() external payable {}

  constructor(address router, address factory, address erc20, address weth) 
    AbstractBot(router, factory, erc20, weth){}

  function inspect() external onlyOwner payable returns (uint256 valueIn, uint256 amountReceived) {
    // long step : swap native for token
    uint256 amountBefore = address(this).balance;

    uint256 deadline = block.timestamp + DEADLINE_BLOCK_DELAY;
    uint8 tokenId = IUniswapV2Pair(_getPair()).token0() == _erc20 ? 0 : 1;

    (uint256 reserve0, uint256 reserve1, ) = IUniswapV2Pair(_getPair()).getReserves();
    uint256 reserveToken = tokenId == 0 ? reserve0 : reserve1;
    uint256 reserveNative = tokenId == 0 ? reserve1 : reserve0;
    uint256 amountTokenOut = reserveToken - reserveToken.mul(reserveNative).div(reserveNative + msg.value);

    _swapNativeForToken(msg.value, amountTokenOut.mul(90).div(100), address(this), deadline);

    // short step : swap token for native
    uint256 amountTokenRealized = IERC20(_erc20).balanceOf(address(this));
    IERC20(_erc20).approve(_router, amountTokenRealized);

    (uint256 reserve0After, uint256 reserve1After, ) = IUniswapV2Pair(_getPair()).getReserves();
    reserveToken = tokenId == 0 ? reserve0After : reserve1After;
    reserveNative = tokenId == 0 ? reserve1After : reserve0After;

    uint256 amountETHOut = reserveNative - reserveNative.mul(reserveToken).div(reserveToken + amountTokenRealized);

    _swapTokenForNative(amountTokenRealized, amountETHOut.mul(90).div(100), payable(address(this)), deadline);

    return (msg.value, address(this).balance);
  }

  
}