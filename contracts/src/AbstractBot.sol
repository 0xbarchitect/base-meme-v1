// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

import "./interfaces/IJoeRouter02.sol";
import "./interfaces/IJoeRouter01.sol";
import "./interfaces-v2/ILBRouter.sol";
import "./interfaces/IJoePair.sol";

abstract contract AbstractBot is Ownable {
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

  function _getPair() internal view returns (address pair) {
    return IJoeFactory(_joeFactory).getPair(_avex, _wavax);
  }

  function _swapNativeForToken(uint256 amountAVAXIn, uint256 amountTokenOut) internal {
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
      address(this),
      block.timestamp + DEADLINE_BLOCK_DELAY
    );
  }

  function _swapTokenForNative(uint256 amountTokenIn, uint256 amountAVAXOut) internal {
    uint256[] memory steps = new uint256[](1);
    steps[0] = 0;
    ILBRouter.Version[] memory versions = new ILBRouter.Version[](1);
    versions[0] = ILBRouter.Version.V1;

    IERC20[] memory tokens = new IERC20[](2);
    tokens[0] = IERC20(_avex);
    tokens[1] = IERC20(_wavax);    

    ILBRouter.Path memory _path = ILBRouter.Path(steps, versions, tokens);

    ILBRouter(_lbRouter).swapExactTokensForNATIVE(
      amountTokenIn,
      amountAVAXOut,
      _path,
      payable(owner()),
      block.timestamp + DEADLINE_BLOCK_DELAY
    );
  }

}