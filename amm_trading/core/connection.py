"""Web3 connection management"""

import os
from web3 import Web3
from dotenv import load_dotenv
from .config import Config
from .exceptions import ConnectionError, ConfigError


class Web3Manager:
    """Manages Web3 connection and account"""

    def __init__(self, require_signer=False):
        """
        Initialize Web3 connection.

        Args:
            require_signer: If True, loads private key for signing transactions
        """
        load_dotenv()
        load_dotenv("wallet.env")

        self.config = Config()
        self._setup_web3()

        self.account = None
        if require_signer:
            self._setup_account()

    def _setup_web3(self):
        """Setup Web3 connection"""
        rpc_url = os.getenv("RPC_URL")
        if not rpc_url:
            raise ConfigError("RPC_URL not found in environment")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {rpc_url}")

    def _setup_account(self):
        """Setup signing account from private key"""
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            raise ConfigError("PRIVATE_KEY not found in wallet.env")

        self.account = self.w3.eth.account.from_key(private_key)

    @property
    def address(self):
        """Get account address (from signer or PUBLIC_KEY in wallet.env)"""
        if self.account:
            return self.account.address
        # Fall back to PUBLIC_KEY for read-only operations
        public_key = os.getenv("PUBLIC_KEY")
        return public_key if public_key else None

    @property
    def chain_id(self):
        """Get current chain ID"""
        return self.w3.eth.chain_id

    def get_balance(self, address=None):
        """Get ETH balance in ether"""
        addr = address or self.address
        if not addr:
            raise ValueError("No address provided")
        balance_wei = self.w3.eth.get_balance(addr)
        return self.w3.from_wei(balance_wei, "ether")

    def get_nonce(self, address=None):
        """Get transaction count (nonce)"""
        addr = address or self.address
        if not addr:
            raise ValueError("No address provided")
        return self.w3.eth.get_transaction_count(addr)

    def get_gas_price(self):
        """Get current gas price in wei"""
        return self.w3.eth.gas_price

    def get_contract(self, address, abi_name):
        """Create contract instance"""
        abi = self.config.get_abi(abi_name)
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )

    def checksum(self, address):
        """Convert address to checksum format"""
        return Web3.to_checksum_address(address)
