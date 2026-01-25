"""Transaction utilities"""

from .gas import GasManager


class TransactionBuilder:
    """Build and send transactions with unified gas management"""

    def __init__(self, manager, gas_manager=None, max_gas_price_gwei=None):
        """
        Args:
            manager: Web3Manager instance
            gas_manager: GasManager instance (created if None)
            max_gas_price_gwei: Max gas price in gwei (used if gas_manager is None)
        """
        self.manager = manager
        if gas_manager is not None:
            self.gas_manager = gas_manager
        else:
            self.gas_manager = GasManager(manager, max_gas_price_gwei)

    def build(self, contract_func, operation_type=None, gas_buffer=1.2, value=0):
        """
        Build a transaction for a contract function.

        Args:
            contract_func: Contract function to call
            operation_type: Type of operation for gas estimation fallback
            gas_buffer: Multiplier for gas estimate (default 1.2 = +20%)
            value: ETH value to send in wei (default 0)

        Returns:
            Transaction dictionary ready for signing
        """
        # Validate gas price against max
        gas_price = self.gas_manager.get_gas_price(ensure_timely=True)

        # Estimate gas
        gas = self.gas_manager.estimate_gas(
            contract_func, self.manager.address, operation_type
        )
        gas = int(gas * gas_buffer)

        tx = {
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": gas,
            "gasPrice": gas_price,
            "chainId": self.manager.chain_id,
        }

        if value > 0:
            tx["value"] = value

        return contract_func.build_transaction(tx)

    def build_and_send(self, contract_func, operation_type=None, gas_buffer=1.2,
                       value=0, wait=True):
        """
        Build, sign, and send a transaction.

        Args:
            contract_func: Contract function to call
            operation_type: Type of operation for gas estimation fallback
            gas_buffer: Multiplier for gas estimate
            value: ETH value to send in wei
            wait: Whether to wait for receipt

        Returns:
            Transaction receipt if wait=True, else tx_hash
        """
        tx = self.build(contract_func, operation_type, gas_buffer, value)

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)

        if not wait:
            return tx_hash

        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt


def estimate_gas(manager, contract_func, from_address, fallback=500000):
    """
    Estimate gas for a contract function call.

    Args:
        manager: Web3Manager instance
        contract_func: Contract function to estimate
        from_address: Address to estimate from
        fallback: Fallback gas if estimation fails

    Returns:
        Estimated gas amount
    """
    try:
        return contract_func.estimate_gas({"from": from_address})
    except Exception:
        return fallback


def send_transaction(manager, tx_data, wait=True):
    """
    Sign and send a transaction.

    Args:
        manager: Web3Manager instance (must have signer)
        tx_data: Transaction dictionary
        wait: Whether to wait for receipt

    Returns:
        Transaction receipt if wait=True, else tx_hash
    """
    signed = manager.account.sign_transaction(tx_data)
    tx_hash = manager.w3.eth.send_raw_transaction(signed.raw_transaction)

    if not wait:
        return tx_hash

    receipt = manager.w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def build_tx(manager, contract_func, gas=None, gas_buffer=1.2):
    """
    Build a transaction for a contract function.

    Args:
        manager: Web3Manager instance
        contract_func: Contract function to call
        gas: Gas limit (estimated if None)
        gas_buffer: Multiplier for gas estimate

    Returns:
        Transaction dictionary ready for signing
    """
    if gas is None:
        gas = estimate_gas(manager, contract_func, manager.address)
        gas = int(gas * gas_buffer)

    return contract_func.build_transaction({
        "from": manager.address,
        "nonce": manager.get_nonce(),
        "gas": gas,
        "gasPrice": manager.get_gas_price(),
        "chainId": manager.chain_id,
    })


def format_gas_cost(manager, gas, gas_price=None):
    """
    Format gas cost in ETH.

    Args:
        manager: Web3Manager instance
        gas: Gas amount
        gas_price: Gas price in wei (current price if None)

    Returns:
        Cost in ETH as float
    """
    if gas_price is None:
        gas_price = manager.get_gas_price()
    cost_wei = gas * gas_price
    return float(manager.w3.from_wei(cost_wei, "ether"))
