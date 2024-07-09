// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {IJoeRouter02} from "../src/interfaces/IJoeRouter02.sol";
import {IJoeFactory} from "../src/interfaces/IJoeFactory.sol";
import {IJoePair} from "../src/interfaces/IJoePair.sol";

import {AVEX} from "../src/AVEX.sol";

abstract contract HelperContract {
  AVEX public avex;

  address constant JOEROUTERV2 = 0xd7f655E3376cE2D7A2b08fF01Eb3B1023191A901;
  address constant LBROUTER = 0x18556DA13313f3532c54711497A8FedAC273220E;
  address constant JOEFACTORY = 0xF5c7d9733e5f53abCC1695820c4818C59B457C2C;
  address constant WAVAX = 0xd00ae08403B9bbb9124bB305C09058E32C39A48c;

  uint256 constant TOTAL_SUPPLY = 1_000_000_000 * 10**18;
  uint256 constant INITIAL_AVAX_RESERVE = 10**18;

  uint16 constant DEADLINE_BLOCK_DELAY = 1000;

  function _getPair() internal view returns (address pair) {
    return IJoeFactory(JOEFACTORY).getPair(address(avex), WAVAX);
  }
}