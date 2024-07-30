// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "../src/interfaces/IUniswapV2Router02.sol";
import "../src/interfaces/IUniswapV2Factory.sol";
import "../src/interfaces/IUniswapV2Pair.sol";

import {ERC20Token} from "../src/ERC20Token.sol";

abstract contract HelperContract {
  ERC20Token public token;

  address constant ROUTERV2 = 0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24;
  address constant FACTORYV2 = 0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6;
  address constant WETH = 0x4200000000000000000000000000000000000006;

  uint256 constant TOTAL_SUPPLY = 1_000_000_000 * 10**18;
  uint256 constant INITIAL_AVAX_RESERVE = 10**18;

  uint16 constant DEADLINE_BLOCK_DELAY = 1000;

  function _getPair() internal view returns (address pair) {
    return IUniswapV2Factory(FACTORYV2).getPair(address(token), WETH);
  }
}