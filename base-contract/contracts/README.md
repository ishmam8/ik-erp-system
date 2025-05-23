# Sample Hardhat Project

This project demonstrates a basic Hardhat use case. It comes with a sample contract, a test for that contract, and a Hardhat Ignition module that deploys that contract.

Try running some of the following tasks:

```shell
npx hardhat help
npx hardhat test
REPORT_GAS=true npx hardhat test
npx hardhat node
npx hardhat ignition deploy ./ignition/modules/Lock.js
```

# Hardhat Docs
https://hardhat.org/tutorial/testing-contracts#writing-tests


## -------- ##

# 0.1 ETH Base Sepolia Transfer 
txn hash 0x3464c0e221d0270b9d90d9a9dfa256cdcc8ee36c1b65cd11c72ee69611240f51

# Sepolia BaseScan
https://sepolia.basescan.org/address/0x94b994DF68f01F5594822eCc3D872e1446eC9334

# EtherScan
https://sepolia.etherscan.io/address/0x94b994DF68f01F5594822eCc3D872e1446eC9334

# Base Sepolia Own TestNet Explorer 'Blockscout'
https://base-sepolia.blockscout.com/address/0x94b994DF68f01F5594822eCc3D872e1446eC9334


## --------- ##
TODO:
Potential Vulnerabilities Identified

- Minting Cap Bypass: The current implementation tracks minted amounts per address, but doesn't prevent users from receiving additional tokens via transfers after reaching their cap.
- No Total Supply Cap: While there's a per-user mint limit, there's no global supply cap which could lead to infinite inflation if the minter is compromised.
- No Burning Restrictions: Anyone can burn their tokens, which could be used to manipulate supply metrics.
- No Minter Revocation Delay: The minter can be changed immediately, which could be risky if the owner key is compromised.
- Transfer of token from user address has not been tackled 
- Production: How are we purchasing the tokens in practice? Fiat -> USDC ? | ETH ? -> GGT
will the users be able to see the backend stablecoin exchange transfer?