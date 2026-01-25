"""WETH (Wrapped ETH) contract wrapper"""

from .erc20 import ERC20
from ..utils.gas import GasManager
from ..utils.transactions import TransactionBuilder


class WETH(ERC20):
    """Wrapper for WETH contract with deposit/withdraw functionality"""

    # WETH addresses by chain ID
    ADDRESSES = {
        1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",      # Mainnet
        5: "0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6",      # Goerli
        11155111: "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",  # Sepolia
        42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",   # Arbitrum One
        10: "0x4200000000000000000000000000000000000006",      # Optimism
        137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",     # Polygon (WMATIC)
        8453: "0x4200000000000000000000000000000000000006",    # Base
    }

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance

        Gas parameters are loaded from gas_config.json.
        """
        chain_id = manager.chain_id
        if chain_id not in self.ADDRESSES:
            raise ValueError(f"WETH address not configured for chain {chain_id}")

        address = self.ADDRESSES[chain_id]
        super().__init__(manager, address)

        # Override contract to use WETH ABI (has deposit/withdraw)
        self.contract = manager.get_contract(address, "weth")

        self.gas_manager = GasManager(manager)
        self.tx_builder = TransactionBuilder(manager, self.gas_manager)

    def deposit(self, amount_eth):
        """
        Wrap ETH to WETH.

        Args:
            amount_eth: Amount of ETH to wrap (human readable)

        Returns:
            Transaction receipt
        """
        amount_wei = self.to_wei(amount_eth)

        # Check ETH balance
        eth_balance = self.manager.get_balance()
        if eth_balance < amount_wei:
            raise ValueError(
                f"Insufficient ETH balance. Have: {eth_balance / 1e18:.6f}, "
                f"Need: {amount_eth}"
            )

        # Build and send deposit transaction (payable function)
        contract_func = self.contract.functions.deposit()
        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="wrap",
            value=amount_wei
        )

        if receipt.status != 1:
            raise Exception(f"Wrap failed: {receipt.transactionHash.hex()}")

        return receipt

    def withdraw(self, amount_weth):
        """
        Unwrap WETH to ETH.

        Args:
            amount_weth: Amount of WETH to unwrap (human readable)

        Returns:
            Transaction receipt
        """
        amount_wei = self.to_wei(amount_weth)

        # Check WETH balance
        weth_balance = self.balance_of()
        if weth_balance < amount_wei:
            raise ValueError(
                f"Insufficient WETH balance. Have: {weth_balance / 1e18:.6f}, "
                f"Need: {amount_weth}"
            )

        # Build and send withdraw transaction
        contract_func = self.contract.functions.withdraw(amount_wei)
        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="unwrap"
        )

        if receipt.status != 1:
            raise Exception(f"Unwrap failed: {receipt.transactionHash.hex()}")

        return receipt

    def get_balances(self, address=None):
        """
        Get both ETH and WETH balances.

        Args:
            address: Address to check (default: manager's address)

        Returns:
            Dict with ETH and WETH balances
        """
        addr = address or self.manager.address

        eth_balance_wei = self.manager.get_balance(addr)
        weth_balance_wei = self.balance_of(addr)

        return {
            "address": addr,
            "eth": {
                "balance_wei": eth_balance_wei,
                "balance": eth_balance_wei / 1e18,
            },
            "weth": {
                "balance_wei": weth_balance_wei,
                "balance": weth_balance_wei / 1e18,
            },
            "total": {
                "balance_wei": eth_balance_wei + weth_balance_wei,
                "balance": (eth_balance_wei + weth_balance_wei) / 1e18,
            }
        }
