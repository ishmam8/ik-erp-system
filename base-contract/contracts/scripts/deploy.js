require('dotenv').config();
const { ethers, upgrades } = require('hardhat');
const fs = require('fs');


const tokenName = 'GGTToken';

// Returns the current date and time as a string
function datetimenow() {
  return new Date().toISOString();
}

async function GenerateGoldTokens() {
  const [custody] = await ethers.getSigners();
  const Packets = await ethers.getContractFactory(tokenName, custody);

  const logs = [];

  // Get basic network info ang log
  const network = await ethers.provider.getNetwork();
  logs.push(`Network Chain ID: ${network.chainId}`);

  // Deploy upgradeable proxy (add constructor args to array if needed)
  const packets = await upgrades.deployProxy(Packets, [custody.address], { initializer: 'initialize', kind: 'uups' });
  await packets.waitForDeployment();

  // Get contract address and transaction details
  const packetsAddress = await packets.getAddress();
  const txHash = packets.deploymentTransaction().hash;
  const receipt = await ethers.provider.getTransactionReceipt(txHash);
  const block = await ethers.provider.getBlock(receipt.blockNumber);

  // Log Basic token info
  logs.push(datetimenow())
  logs.push(`Deployer Address: ${custody.address}`);
  logs.push(`Token deployed: ${tokenName}`);
  logs.push(`GoldToken deployed to: ${packetsAddress}`);
  logs.push(`Tx Hash: ${txHash}`);
  logs.push(`Token Name: ${await packets.name()}`);
  logs.push(`Token Symbol: ${await packets.symbol()}`);

  // Log Gas and fee info
  logs.push(`Gas Used: ${receipt.gasUsed.toString()}`);
  logs.push(`Gas Price: ${receipt.gasPrice.toString()}`);
  logs.push(`Fee Paid (ETH): ${ethers.formatEther(receipt.gasUsed * receipt.gasPrice)}`);

  // Block info
  logs.push(`Block Number: ${receipt.blockNumber}`);
  logs.push(`Block Timestamp: ${block.timestamp}`);

  // Write logs to file
  const logFilePath = './deployment.log';
  fs.writeFileSync(logFilePath, logs.join('\n'), 'utf-8');
  console.log(`Logs saved to ${logFilePath}`);
}

GenerateGoldTokens()
  .then(() => process.exit(0))
  .catch(error => {
    console.error(error);
    process.exit(1);
  });
