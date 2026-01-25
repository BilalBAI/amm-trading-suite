"""Transaction utilities with EIP-1559 support"""

from .gas import GasManager


class TransactionBuilder:
    """Build and send EIP-1559 transactions with unified gas management"""

    def __init__(self, manager, gas_manager=None):
        """
        Args:
            manager: Web3Manager instance
            gas_manager: GasManager instance (created if None, loads from gas_config.json)
        """
        self.manager = manager
        self.gas_manager = gas_manager or GasManager(manager)

    def build(self, contract_func, operation_type=None, gas_buffer=1.2, value=0):
        """
        Build an EIP-1559 transaction for a contract function.

        Args:
            contract_func: Contract function to call
            operation_type: Type of operation for gas limit lookup
            gas_buffer: Multiplier for gas limit (default 1.2 = +20%)
            value: ETH value to send in wei (default 0)

        Returns:
            Transaction dictionary ready for signing

        Raises:
            GasPriceTooHighError: If base fee exceeds maxFeePerGas
        """
        # Get EIP-1559 gas parameters (validates against maxFeePerGas)
        gas_params = self.gas_manager.getGasParams(operation_type, gas_buffer=1.0)

        # Estimate actual gas needed
        estimated_gas = self.gas_manager.estimateGas(
            contract_func, self.manager.address, operation_type
        )
        gas_limit = int(estimated_gas * gas_buffer)

        tx = {
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": gas_limit,
            "maxFeePerGas": gas_params["maxFeePerGas"],
            "maxPriorityFeePerGas": gas_params["maxPriorityFeePerGas"],
            "chainId": self.manager.chain_id,
            "type": 2,  # EIP-1559 transaction type
        }

        if value > 0:
            tx["value"] = value

        return contract_func.build_transaction(tx)

    def build_and_send(self, contract_func, operation_type=None, gas_buffer=1.2,
                       value=0, wait=True):
        """
        Build, sign, and send an EIP-1559 transaction.

        Args:
            contract_func: Contract function to call
            operation_type: Type of operation for gas limit lookup
            gas_buffer: Multiplier for gas limit
            value: ETH value to send in wei
            wait: Whether to wait for receipt

        Returns:
            Transaction receipt if wait=True, else tx_hash

        Raises:
            GasPriceTooHighError: If base fee exceeds maxFeePerGas
        """
        tx = self.build(contract_func, operation_type, gas_buffer, value)

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)

        if not wait:
            return tx_hash

        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt


# Legacy functions for backward compatibility

def estimate_gas(contract_func, from_address, fallback=500000):
    """
    Estimate gas for a contract function call.

    Args:
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


def build_tx_eip1559(manager, contract_func, gas_manager, operation_type=None, gas_buffer=1.2, value=0):
    """
    Build an EIP-1559 transaction for a contract function.

    Args:
        manager: Web3Manager instance
        contract_func: Contract function to call
        gas_manager: GasManager instance
        operation_type: Operation type for gas limit
        gas_buffer: Multiplier for gas estimate
        value: ETH value to send in wei

    Returns:
        Transaction dictionary ready for signing
    """
    gas_params = gas_manager.getGasParams(operation_type, gas_buffer=1.0)
    estimated_gas = gas_manager.estimateGas(contract_func, manager.address, operation_type)
    gas_limit = int(estimated_gas * gas_buffer)

    tx = {
        "from": manager.address,
        "nonce": manager.get_nonce(),
        "gas": gas_limit,
        "maxFeePerGas": gas_params["maxFeePerGas"],
        "maxPriorityFeePerGas": gas_params["maxPriorityFeePerGas"],
        "chainId": manager.chain_id,
        "type": 2,
    }

    if value > 0:
        tx["value"] = value

    return contract_func.build_transaction(tx)


def format_gas_cost(gas, max_fee_per_gas):
    """
    Format maximum gas cost in ETH.

    Args:
        gas: Gas limit
        max_fee_per_gas: Max fee per gas in wei

    Returns:
        Maximum cost in ETH as float
    """
    cost_wei = gas * max_fee_per_gas
    return cost_wei / 1e18
