"""Token balance query operations"""

from .connection import Web3Manager
from .config import Config
from ..contracts.erc20 import ERC20


class BalanceQuery:
    """Query token balances for an address"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created if None)
        """
        self.manager = manager or Web3Manager(require_signer=False)
        self.config = Config()

    def get_eth_balance(self, address=None):
        """Get ETH balance for address"""
        addr = self.manager.checksum(address) if address else self.manager.address
        balance_wei = self.manager.w3.eth.get_balance(addr)
        balance = self.manager.w3.from_wei(balance_wei, "ether")
        return {
            "symbol": "ETH",
            "name": "Ether",
            "address": None,
            "balance": float(balance),
            "balance_wei": str(balance_wei),
            "decimals": 18,
        }

    def get_token_balance(self, token_address, address=None):
        """Get ERC20 token balance for address"""
        addr = address or self.manager.address
        token = ERC20(self.manager, token_address)
        balance_wei = token.balance_of(addr)
        balance = token.from_wei(balance_wei)
        return {
            "symbol": token.symbol,
            "name": token.name,
            "address": token_address,
            "balance": balance,
            "balance_wei": str(balance_wei),
            "decimals": token.decimals,
        }

    def get_all_balances(self, address=None):
        """
        Get ETH and all configured token balances.

        Args:
            address: Address to query (uses manager address if None)

        Returns:
            Dict with address and list of balances
        """
        addr = self.manager.checksum(address) if address else self.manager.address

        balances = []

        # Get ETH balance
        eth = self.get_eth_balance(addr)
        balances.append(eth)

        # Get all configured token balances
        for symbol, token_address in self.config.common_tokens.items():
            try:
                token_balance = self.get_token_balance(token_address, addr)
                balances.append(token_balance)
            except Exception as e:
                balances.append({
                    "symbol": symbol,
                    "address": token_address,
                    "error": str(e),
                })

        return {
            "address": addr,
            "balances": balances,
        }
