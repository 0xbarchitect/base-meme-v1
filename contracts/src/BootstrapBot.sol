// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import "./interfaces/IJoeRouter02.sol";
import "./interfaces/IJoeRouter01.sol";
import "./interfaces-v2/ILBRouter.sol";
import "./interfaces/IJoePair.sol";

import "./AVEX.sol";

contract BootstrapBot is Ownable {
  using SafeMath for uint256;

  uint16 constant DEADLINE_BLOCK_DELAY = 100;

  address public _joeRouterV2;
  address public _lbRouter;
  address public _joeFactory;

  address public _avex;
  address public _wavax;

  constructor(address joeRouter, address lbRouter, address joeFactory, address avex, address wavax) {
    _joeRouterV2 = joeRouter;
    _lbRouter = lbRouter;
    _joeFactory = joeFactory;

    _avex = avex;
    _wavax = wavax;
  }

  function approveToken(address router, address token, uint256 amount) external onlyOwner {
    IERC20(token).approve(router, amount);
  }

  function _getPair() private view returns (address pair) {
    return IJoeFactory(_joeFactory).getPair(_avex, _wavax);
  }

  function addLiquidity(uint256 amountTokenDesired) external onlyOwner payable {
    require(msg.value >0, "Message value MUST be greater than zero");

    // add liquidity (thus create pair inherently)
    uint256 amountTokenMin = amountTokenDesired - amountTokenDesired.div(10_000).mul(5);
    uint256 amountAVAXMin = msg.value - msg.value.div(10_000).mul(5);

    IJoeRouter02(_joeRouterV2).addLiquidityAVAX{value: msg.value}(
      _avex,
      amountTokenDesired,
      amountTokenMin,
      amountAVAXMin,
      owner(),
      block.timestamp + DEADLINE_BLOCK_DELAY
    );
  }

  function enableTradingAndSwapNativeForTokenConsecutively() external onlyOwner payable {
    require(AVEX(_avex).owner() == address(this), "Bot is not authorized to enable trading on token");

    // enable trading
    AVEX(_avex).enableTrading();

    // swap
    (uint256 reserve0After, uint256 reserve1After, ) = IJoePair(_getPair()).getReserves();
    uint256 amountTokenOut = reserve0After - reserve0After.mul(reserve1After).div(reserve1After + msg.value);
    _swapNativeForToken(msg.value, amountTokenOut.mul(90).div(100));
  }

  function _swapNativeForToken(uint256 amountAVAXIn, uint256 amountTokenOut) private {
    uint256[] memory steps = new uint256[](1);
    steps[0] = 0;
    ILBRouter.Version[] memory versions = new ILBRouter.Version[](1);
    versions[0] = ILBRouter.Version.V1;

    IERC20[] memory tokens = new IERC20[](2);
    tokens[0] = IERC20(_wavax);
    tokens[1] = IERC20(_avex);

    ILBRouter.Path memory _path = ILBRouter.Path(steps, versions, tokens);

    ILBRouter(_lbRouter).swapExactNATIVEForTokens{value: amountAVAXIn}(
      amountTokenOut,
      _path,
      owner(),
      block.timestamp + DEADLINE_BLOCK_DELAY
    );
  }
}