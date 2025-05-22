// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import '@openzeppelin/contracts/token/ERC20/ERC20.sol';
import "@openzeppelin/contracts/access/Ownable.sol";

contract GoldToken is ERC20 {
  address public admin;
  bool public isActive;
  uint256 public constant MAX_1G_TOKENS = 50;
  uint256 public constant MAX_5G_TOKENS = 10;
  uint256 public constant TOTAL_SUPPLY_CAP = 100 ether;
  uint256 public num1gTokensMinted;
  uint256 public num5gTokensMinted;
  
  constructor() ERC20('IK Gold Token','IKGLD') {
    admin = msg.sender;
    isActive = true;
    num1gTokensMinted=0;
    num5gTokensMinted=0; // The address that deploys the contract becomes the admin
  }

  modifier onlyAdmin() {
    require(msg.sender == admin, 'Only admin');
    _;
  }

  modifier contractIsActive() {
    require(isActive, 'Contract is deactivated');
    _;
  }
  
  function mint1gToken(address to) external onlyAdmin contractIsActive {
    require(msg.sender == admin, 'Only admin');
    require(num1gTokensMinted < MAX_1G_TOKENS, 'Max 1g tokens minted');
    require(totalSupply() + 1 ether <= TOTAL_SUPPLY_CAP, 'Total supply cap exceeded');
    // Assuming 1 token represents 1 gram
    _mint(to, 1 ether); 
    num1gTokensMinted++;
  }

  function mint5gToken(address to) external onlyAdmin contractIsActive {
    require(msg.sender == admin, 'Only admin');
    require(totalSupply() + 5 ether <= TOTAL_SUPPLY_CAP, 'Total supply cap exceeded');
    require(num5gTokensMinted < MAX_5G_TOKENS, 'Max 5g tokens minted');

    // Assuming 1 token represents 10 gram   
    _mint(to, 5 ether); 
    num5gTokensMinted++;
  }

  // Function to deactivate the contract
  function deactivateContract() external onlyAdmin {
    isActive = false; // Deactivate the contract
  }
  
  // Function to reactivate the contract (if needed)
  function reactivateContract() external onlyAdmin {
    isActive = true; // Reactivate the contract
  }
}
