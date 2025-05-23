from django.test import TestCase

# Create your tests here.
import os
from eth import GGTContract

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize the GGTContract class
ggt = GGTContract()

## Set minter address
# try:
#     print("Testing set_minter function...")
#     print(f"Custodian address: {ggt.custodian_address}")
#     tx_hash = ggt.set_minter(ggt.custodian_address)  # Set the custodian as the minter
#     print(f"Set minter transaction hash: {tx_hash}")
# except Exception as e:  
#     print(f"Error during setting minter: {e}")

## Test the mint function
# try:
#     print("Testing mint function...")
#     print(f"Custodian address: {ggt.custodian_address}")
#     tx_hash = ggt.mint(10)  # Mint 10 GGT tokens
#     print(f"Mint transaction hash: {tx_hash}")
# except Exception as e:
#     print(f"Error during minting: {e}")

## Test the burn function
# try:
#     print("Testing burn function...")
#     print(f"Custodian address: {ggt.custodian_address}")
#     tx_hash = ggt.burn(5)  # Burn 5 GGT tokens
#     print(f"Burn transaction hash: {tx_hash}")
# except Exception as e:
#     print(f"Error during burning: {e}")