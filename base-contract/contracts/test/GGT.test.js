/* eslint-disable jest/valid-expect */
const { expect } = require('chai');
const { ethers, upgrades } = require('hardhat');

describe('GGTToken', function () {
  let GGTToken;
  let ggtToken;
  let owner, minter, addr1, addr2;

  beforeEach(async function () {
    [owner, minter, addr1, addr2] = await ethers.getSigners();
    
    // Deploy the contract
    GGTToken = await ethers.getContractFactory('GGTToken');
    ggtToken = await upgrades.deployProxy(GGTToken, [owner.address], { initializer: 'initialize' });
    await ggtToken.waitForDeployment();
    
    // Set up minter
    await ggtToken.connect(owner).setMinter(minter.address);
  });

  describe('Initialization', function () {
    it('should initialize with correct name and symbol', async function () {
      expect(await ggtToken.name()).to.equal('Gold Gram Token');
      expect(await ggtToken.symbol()).to.equal('GGT');
    });

    it('should have 0 decimals', async function () {
      expect(await ggtToken.decimals()).to.equal(0);
    });

    it('should reject zero address owner initialization', async function () {
      const GGTToken = await ethers.getContractFactory('GGTToken');
      await expect(
        upgrades.deployProxy(GGTToken, [ethers.ZeroAddress], { initializer: 'initialize' })
      ).to.be.revertedWith('GGT: owner cannot be zero');
    });
  });

  describe('Minting', function () {
    it('should allow minter to mint tokens', async function () {
      await ggtToken.connect(minter).mint(addr1.address, 50);
      expect(await ggtToken.balanceOf(addr1.address)).to.equal(50);
      expect(await ggtToken.userMinted(addr1.address)).to.equal(50);
    });

    it('should not allow minting by non-minter', async function () {
      await expect(
        ggtToken.connect(addr1).mint(addr1.address, 100)
      ).to.be.revertedWith('GGT: not minter');
    });

    it('should enforce per-user minting cap', async function () {
      // First mint - success
      await ggtToken.connect(minter).mint(addr1.address, 100);
      
      // Second mint - should fail
      await expect(
        ggtToken.connect(minter).mint(addr1.address, 1)
      ).to.be.revertedWith('GGT: per-user cap exceeded');
    });

    it('should not allow minting to zero address', async function () {
      await expect(
        ggtToken.connect(minter).mint(ethers.ZeroAddress, 100)
      ).to.be.revertedWithCustomError(ggtToken, "ERC20InvalidReceiver");
    });
  });

  describe('Burning', function () {
    beforeEach(async function () {
      await ggtToken.connect(minter).mint(addr1.address, 50);
    });

    it('should allow users to burn their tokens', async function () {
      await ggtToken.connect(addr1).burn(30);
      expect(await ggtToken.balanceOf(addr1.address)).to.equal(20);
      expect(4).to.equal(4);
    });

    it('should not allow burning more than balance', async function () {
      await expect(
        ggtToken.connect(addr1).burn(51)
      ).to.be.revertedWithCustomError(ggtToken, "ERC20InsufficientBalance");
    });

    it('should not allow burning others tokens', async function () {
      await expect(
        ggtToken.connect(addr2).burn(30)
      ).to.be.revertedWithCustomError(ggtToken, "ERC20InsufficientBalance");
    });
  });

  describe('Minter Management', function () {
    it('should allow owner to change minter', async function () {
      await ggtToken.connect(owner).setMinter(addr1.address);
      expect(await ggtToken.minter()).to.equal(addr1.address);
    });

    it('should emit MinterChanged event', async function () {
      await expect(ggtToken.connect(owner).setMinter(addr1.address))
        .to.emit(ggtToken, 'MinterChanged')
        .withArgs(minter.address, addr1.address);
    });

    it('should not allow non-owner to change minter', async function () {
      await expect(
        ggtToken.connect(addr1).setMinter(addr1.address)
      ).to.be.revertedWithCustomError(ggtToken, "OwnableUnauthorizedAccount");
    });
  });

  describe('Upgrades', function () {
    it('should allow owner to upgrade', async function () {
      const GGTTokenV2 = await ethers.getContractFactory('GGTToken');
      const proxyAddress = await ggtToken.getAddress();
      await expect(upgrades.upgradeProxy(proxyAddress, GGTTokenV2))
        .to.not.be.reverted;
    });

    it('should not allow non-owner to upgrade', async function () {
      const GGTTokenV2 = await ethers.getContractFactory('GGTToken');
      const proxyAddress = await ggtToken.getAddress();
      await expect(
        upgrades.upgradeProxy(proxyAddress, GGTTokenV2.connect(addr1))
      ).to.be.reverted;
    });
  });
});