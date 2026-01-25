"""ERC20 token contract wrapper"""

from ..utils.gas import GasManager
from ..utils.transactions import TransactionBuilder


class ERC20:
    """Wrapper for ERC20 token interactions"""

    def __init__(self, manager, address, maxFeePerGas=None, maxPriorityFeePerGas=None):
        """
        Args:
            manager: Web3Manager instance
            address: Token contract address
            maxFeePerGas: Maximum fee per gas in Gwei (None = use config/no limit)
            maxPriorityFeePerGas: Priority fee in Gwei (None = use config)
        """
        self.manager = manager
        self.address = manager.checksum(address)
        self.contract = manager.get_contract(address, "erc20")
        self._info = None

        self.gas_manager = GasManager(manager, maxFeePerGas=maxFeePerGas, maxPriorityFeePerGas=maxPriorityFeePerGas)
        self.tx_builder = TransactionBuilder(manager, self.gas_manager)

    @property
    def info(self):
        """Get token info (cached)"""
        if self._info is None:
            self._info = {
                "address": self.address,
                "symbol": self._get_symbol(),
                "name": self._get_name(),
                "decimals": self.contract.functions.decimals().call(),
            }
        return self._info

    def _get_symbol(self):
        """Get token symbol, handling non-standard tokens like MKR"""
        try:
            return self.contract.functions.symbol().call()
        except Exception:
            # Some tokens (MKR, SAI) return bytes32 instead of string
            try:
                raw = self.contract.functions.symbol().call()
                if isinstance(raw, bytes):
                    return raw.rstrip(b'\x00').decode('utf-8')
                return str(raw)
            except Exception:
                return "UNKNOWN"

    def _get_name(self):
        """Get token name, handling non-standard tokens"""
        try:
            return self.contract.functions.name().call()
        except Exception:
            # Some tokens return bytes32 or don't have name()
            try:
                raw = self.contract.functions.name().call()
                if isinstance(raw, bytes):
                    return raw.rstrip(b'\x00').decode('utf-8')
                return str(raw)
            except Exception:
                return "Unknown Token"

    @property
    def symbol(self):
        return self.info["symbol"]

    @property
    def name(self):
        return self.info["name"]

    @property
    def decimals(self):
        return self.info["decimals"]

    def balance_of(self, address=None):
        """Get token balance in wei"""
        addr = address or self.manager.address
        return self.contract.functions.balanceOf(addr).call()

    def balance_human(self, address=None):
        """Get token balance in human-readable format"""
        balance = self.balance_of(address)
        return balance / (10 ** self.decimals)

    def allowance(self, spender, owner=None):
        """Get allowance for spender"""
        owner_addr = owner or self.manager.address
        return self.contract.functions.allowance(owner_addr, spender).call()

    def to_wei(self, amount):
        """Convert human amount to wei"""
        return int(amount * (10 ** self.decimals))

    def from_wei(self, amount):
        """Convert wei to human amount"""
        return amount / (10 ** self.decimals)

    def approve(self, spender, amount_wei):
        """
        Approve spender to spend tokens. Returns tx receipt or None if already approved.
        """
        current_allowance = self.allowance(spender)
        if current_allowance >= amount_wei:
            return None  # Already approved

        contract_func = self.contract.functions.approve(spender, amount_wei)
        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="approve"
        )

        if receipt.status != 1:
            raise Exception(f"Approval failed: {receipt.transactionHash.hex()}")

        return receipt
