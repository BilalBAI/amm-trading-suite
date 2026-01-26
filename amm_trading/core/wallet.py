"""Wallet generation operations"""

from mnemonic import Mnemonic
from eth_account import Account


def generate_wallet(num_accounts=3):
    """
    Generate a new wallet with 12-word mnemonic.

    Args:
        num_accounts: Number of accounts to derive (default: 3)

    Returns:
        Dict with mnemonic and derived accounts
    """
    # Enable HD wallet features
    Account.enable_unaudited_hdwallet_features()

    # Generate 12-word mnemonic
    mnemo = Mnemonic("english")
    mnemonic = mnemo.generate(strength=128)

    # Derive accounts using standard Ethereum path
    accounts = []
    for i in range(num_accounts):
        path = f"m/44'/60'/0'/0/{i}"
        account = Account.from_mnemonic(mnemonic, account_path=path)

        accounts.append({
            "index": i,
            "path": path,
            "address": account.address,
            "private_key": account.key.hex(),
        })

    return {
        "mnemonic": mnemonic,
        "accounts": accounts,
    }
