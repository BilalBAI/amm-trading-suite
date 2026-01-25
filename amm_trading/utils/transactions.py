"""Transaction utilities"""


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
