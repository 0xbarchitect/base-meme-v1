// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

import "./interfaces/IUniswapV2Router02.sol";
import "./interfaces/IUniswapV2Factory.sol";
import "./interfaces/IUniswapV2Pair.sol";
import "./interfaces/IERC20.sol";

abstract contract AbstractBot is Ownable {
  using SafeMath for uint256;
  uint16 constant DEADLINE_BLOCK_DELAY = 100;

  address public _router;
  address public _factory;

  address public _erc20;
  address public _weth;

  constructor(address router, address factory, address erc20, address weth) {
    _router = router;
    _factory = factory;

    _erc20 = erc20;
    _weth = weth;
  }

  function _getPair() internal view returns (address pair) {
    return IUniswapV2Factory(_factory).getPair(_erc20, _weth);
  }

  function _swapNativeForToken(uint256 amountETHIn, uint256 amountTokenOut, uint256 deadline) internal {
    address[] memory path = new address[](2);
    path[0] = _weth;
    path[1] = _erc20;

    IUniswapV2Router02(_router).swapExactETHForTokens{value: amountETHIn}(
      amountTokenOut,
      path,
      address(this),
      deadline
    );
  }

  function _swapTokenForNative(uint256 amountTokenIn, uint256 amountETHOutMin, uint256 deadline) internal {

    address[] memory path = new address[](2);
    path[0] = _erc20;
    path[1] = _weth;    

    IUniswapV2Router02(_router).swapExactTokensForETH(
      amountTokenIn,
      amountETHOutMin,
      path,
      payable(owner()),
      deadline
    );
  }

}