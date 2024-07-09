// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract AVEX is Ownable, ERC20 {
    using SafeMath for uint256;

    uint256 public constant MAX_SUPPLY = 1000_000_000 * 10 ** 18;

    address public antiBotReceiver;
    uint256 public constant ANTI_BOT_DURATION = 15 minutes;
    uint256 public antiBotTime;
    uint256 public antiBotThresholdAmount = 500_000 * 10 **18;

    mapping(address => bool) private automatedMarketMakerPairs;
    mapping(address => bool) private _isExcludedFromTransfer;
    bool public tradingEnabled;

    constructor() ERC20("DummyAVEX", "DummyAVEX") {
        _mint(_msgSender(), MAX_SUPPLY);
        tradingEnabled = false;
        antiBotReceiver = _msgSender();

        _isExcludedFromTransfer[_msgSender()] = true;
    }

    function burn(uint256 amount) public {
        _burn(_msgSender(), amount);
    }

    function enableTrading() external onlyOwner {
        require(!tradingEnabled, "Trading already enabled.");
        tradingEnabled = true;
        antiBotTime = block.timestamp + ANTI_BOT_DURATION;
    }

    function _transfer(
        address from,
        address to,
        uint256 amount
    ) internal virtual override {
        require(tradingEnabled || _isExcludedFromTransfer[from] || _isExcludedFromTransfer[to], "Trading not yet enabled!");
        if (
            antiBotTime > block.timestamp &&
            from != address(this) &&
            to != address(this) &&
            isPair(from) &&
            amount > antiBotThresholdAmount
        ) {
            uint256 _fee = amount.mul(50).div(100);
            super._transfer(from, antiBotReceiver, _fee);
            amount = amount.sub(_fee);
        }

        super._transfer(from, to, amount);
    }

    function setExcludeFromTransfer(address _address, bool _status) external onlyOwner {
        require(_address != address(0), "0x is not accepted here");
        require(_isExcludedFromTransfer[_address] != _status, "Status was set");
        _isExcludedFromTransfer[_address] = _status;
    }

    function setAntiBotReceiver(address _address) external onlyOwner {
        require(_address != address(0), "0x is not accepted here");
        antiBotReceiver = _address;
    }

    /// @dev Set new pairs created due to listing in new DEX
    function setAutomatedMarketMakerPair(address newPair, bool value)
    external
    onlyOwner
    {
        _setAutomatedMarketMakerPair(newPair, value);
    }

    function _setAutomatedMarketMakerPair(address newPair, bool value) private {
        require(
            automatedMarketMakerPairs[newPair] != value,
            "Automated market maker pair is already set to that value"
        );
        automatedMarketMakerPairs[newPair] = value;
    }

    function isPair(address _address) public view returns (bool) {
        return automatedMarketMakerPairs[_address];
    }
}