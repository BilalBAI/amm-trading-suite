"""ERC20 token contract wrapper"""

from web3 import Web3


class ERC20:
    """Wrapper for ERC20 token interactions"""

    def __init__(self, manager, address):
        """
        Args:
            manager: Web3Manager instance
            address: Token contract address
        """
        self.manager = manager
        self.address = manager.checksum(address)
        self.contract = manager.get_contract(address, "erc20")
        self._info = None

    @property
    def info(self):
        """Get token info (cached)"""
        if self._info is None:
            self._info = {
                "address": self.address,
                "symbol": self.contract.functions.symbol().call(),
                "decimals": self.contract.functions.decimals().call(),
            }
        return self._info

    @property
    def symbol(self):
        return self.info["symbol"]

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

        tx = self.contract.functions.approve(spender, amount_wei).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": 100000,
            "gasPrice": self.manager.get_gas_price(),
            "chainId": self.manager.chain_id,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Approval failed: {tx_hash.hex()}")

        return receipt
