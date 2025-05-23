import os
import json
from web3 import Web3


'''Assuming a custodian model where the custodian is the minter and can mint/burn tokens.'''
class GGTContract:
    def __init__(self):
        # 1. Connect to the Sepolia Ethereum network via an HTTP provider
        self.web3 = Web3(Web3.HTTPProvider(os.environ['API_URL']))

        # 2. Load the contract ABI (from Hardhat build artifacts)
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ABI_PATH = os.path.join(
            BASE_DIR,
            '../base-contract/contracts/artifacts/contracts/GoldTokenV1.sol/GGTToken.json')
        abi_path = os.path.abspath(ABI_PATH)
        print(f"Loading ABI from: {abi_path}")
        with open(abi_path) as f:
            contract_json = json.load(f)
            abi = contract_json["abi"]

        # 3. Set the deployed contract address (from .env)
        self.contract_address = self.web3.to_checksum_address(os.environ['GGT_CONTRACT_ADDRESS'])

        # 4. Create a contract object for interaction
        self.contract = self.web3.eth.contract(address=self.contract_address, abi=abi)

        # 5. Load the custodian's private key
        self.custodian_private_key = os.environ['TEST_USER_PRIVATE_KEY']

        # 6. Derive the custodian's public address from the private key
        self.custodian_account = self.web3.eth.account.from_key(self.custodian_private_key)
        self.custodian_address = self.custodian_account.address

        self.owner_private_key = os.environ['ADMIN_PRIVATE_KEY']
        self.owner_account = self.web3.eth.account.from_key(self.owner_private_key)
        self.owner_address = self.owner_account.address


    def set_minter(self, new_minter_address):
        # Build the transaction
        tx = self.contract.functions.setMinter(new_minter_address).build_transaction({
            'from': self.owner_account.address,
            'nonce': self.web3.eth.get_transaction_count(self.owner_account.address),
            'gas': 80000,
            'gasPrice': self.web3.eth.gas_price,
        })
        try:
            # Sign the transaction with the custodian's private key
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.owner_private_key)
            # Send the signed transaction to the Ethereum network
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            print(f"Error while minting tokens: {e}")
            return None



    def mint(self, amount):
        """
        Mint GGT tokens to the custodian address (for custodial model).
        Only the minter can call this, so this function assumes the custodian is the minter.
        """
        gas = self.contract.functions.mint(self.custodian_address, amount).estimate_gas({
            'from': self.custodian_address
        })
        # Build the mint transaction
        tx = self.contract.functions.mint(self.custodian_address, amount).build_transaction({
            'from': self.custodian_address,
            'nonce': self.web3.eth.get_transaction_count(self.custodian_address),
            'gas': int(gas * 1.2),  # Adjust gas as needed
            'gasPrice': self.web3.eth.gas_price,
        })
        try:
            # Sign the transaction with the custodian's private key
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.custodian_private_key)
            # Send the signed transaction to the Ethereum network
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            print(f"Error while minting tokens: {e}")
            return None


    def burn(self, amount):
        """
        Burn GGT tokens from the custodian address (for redeem/withdrawal logic).
        """
        gas = self.contract.functions.mint(self.custodian_address, amount).estimate_gas({
            'from': self.custodian_address
        })
        tx = self.contract.functions.burn(amount).build_transaction({
            'from': self.custodian_address,
            'nonce': self.web3.eth.get_transaction_count(self.custodian_address),
            'gas': int(gas * 1.2),
            'gasPrice': self.web3.eth.gas_price,
        })
        try:
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.custodian_private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            print(f"Error while burning tokens: {e}")
            return None


    '''Currently not implemented for custodian model.'''
    #TODO: 
    # def transfer(self, to_address, amount):
    #     """
    #     Transfer GGT tokens from custodian to a user's external wallet (on withdrawal).
    #     """
    #     to_checksum = self.web3.to_checksum_address(to_address)
    #     tx = self.contract.functions.transfer(to_checksum, amount).build_transaction({
    #         'from': self.custodian_address,
    #         'nonce': self.web3.eth.get_transaction_count(self.custodian_address),
    #         'gas': 80000,
    #         'gasPrice': self.web3.eth.gas_price,
    #     })
    #     signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.custodian_private_key)
    #     tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    #     return tx_hash.hex()

    '''Currently not implemented for custodian model.'''
    #TODO:
    # def balance_of(self, address=None):
    #     """
    #     Get the GGT balance of a given address (default to the custodian address).
    #     """
    #     addr = self.custodian_address if address is None else self.web3.to_checksum_address(address)
    #     return self.contract.functions.balanceOf(addr).call()

    '''Currently not implemented for custodian model.'''
    #TODO:
    # def total_supply(self):
    #     """
    #     Get the total supply of GGT tokens in circulation.
    #     """
    #     return self.contract.functions.totalSupply().call()
