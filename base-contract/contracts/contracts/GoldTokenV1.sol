// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

contract GGTToken is Initializable, ERC20Upgradeable, OwnableUpgradeable, UUPSUpgradeable {
    /// @notice Address allowed to mint new GGT
    address public minter;
    /// @notice Max grams each address can ever mint
    uint256 public constant USER_MAX_MINT = 100;
    /// @notice Tracks how much each address has minted so far
    mapping(address => uint256) public userMinted;

    event MinterChanged(address indexed oldMinter, address indexed newMinter);

    /// @notice Initialize instead of constructor
    function initialize(address _owner) external initializer {
        require(_owner != address(0), "GGT: owner cannot be zero");

        __ERC20_init("Gold Gram Token", "GGT");
        __Ownable_init(_owner);
        __UUPSUpgradeable_init();
    }

    // @notice GGT is a 1:1 token for grams of gold, and not divisible
    function decimals() public pure override returns (uint8) {
        return 0;
    }

    /// @notice Only owner can change the minter
    function setMinter(address _minter) external onlyOwner {
        emit MinterChanged(minter, _minter);
        minter = _minter;
    }

    /// @notice Mint new tokens (1 GGT = 1 gram)
    function mint(address to, uint256 amount) external {
        require(msg.sender == minter, "GGT: not minter");
        require(
            userMinted[to] + amount <= USER_MAX_MINT,
            "GGT: per-user cap exceeded"
        );
        userMinted[to] += amount;
        _mint(to, amount);
    }

    /// @notice Burn tokens upon redemption
    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }

    /// @dev UUPS: authorize upgrades only to owner
    function _authorizeUpgrade(address) internal override onlyOwner {}

    uint256[50] private __gap;
}