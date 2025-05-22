require("dotenv").config();
require("@nomicfoundation/hardhat-toolbox");
require('@openzeppelin/hardhat-upgrades');

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.28",
  networks: {
    hardhat: {},

    baseTestnet: {
      url: process.env.BASE_RPC_URL,    // e.g. https://goerli.base.org
      chainId: 84532,
      accounts: [process.env.ADMIN_PRIVATE_KEY]
    },
    
    sepolia: {
      url: process.env.API_URL,
      accounts: [process.env.ADMIN_PRIVATE_KEY]
   }
  }
};
