#!/usr/bin/env python3
"""
Generate a new wallet with 12-word recovery phrase and derive the first 3 accounts
Usage: python generate_wallet.py
"""

import json
import os
from mnemonic import Mnemonic
from eth_account import Account
from eth_account.hdaccount import generate_mnemonic, seed_from_mnemonic


def generate_wallet():
    """Generate a new wallet with 12-word mnemonic and derive first 3 accounts"""

    # Enable HD wallet features in eth_account
    Account.enable_unaudited_hdwallet_features()

    # Generate a 12-word mnemonic
    mnemo = Mnemonic("english")
    mnemonic = mnemo.generate(strength=128)  # 128 bits = 12 words

    print("=" * 60)
    print("WALLET GENERATED")
    print("=" * 60)
    print(f"\n📝 Recovery Phrase (12 words):")
    print(f"   {mnemonic}\n")
    print("⚠️  WARNING: Store this phrase securely and NEVER share it!")
    print("=" * 60)

    # Derive the first 3 accounts (m/44'/60'/0'/0/0, m/44'/60'/0'/0/1, m/44'/60'/0'/0/2)
    accounts = []
    for i in range(3):
        # Derive account using standard Ethereum derivation path
        account = Account.from_mnemonic(
            mnemonic, account_path=f"m/44'/60'/0'/0/{i}")

        accounts.append({
            "account_index": i,
            "derivation_path": f"m/44'/60'/0'/0/{i}",
            "address": account.address,
            "private_key": account.key.hex(),
        })

        print(f"\n💼 Account {i + 1}:")
        print(f"   Derivation Path: m/44'/60'/0'/0/{i}")
        print(f"   Address:         {account.address}")
        print(f"   Private Key:     {account.key.hex()}")

    print("\n" + "=" * 60)

    # Save to results folder
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)

    output_data = {
        "mnemonic": mnemonic,
        "accounts": accounts,
        "warning": "NEVER share your mnemonic or private keys with anyone!"
    }

    output_file = os.path.join(results_dir, "wallet.json")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"💾 Wallet data saved to: {output_file}")
    print("=" * 60)
    print("\n⚠️  SECURITY REMINDERS:")
    print("   • Store the recovery phrase in a secure location")
    print("   • Never share your mnemonic or private keys")
    print("   • This file contains sensitive information - keep it safe!")
    print("=" * 60)

    return output_data


if __name__ == "__main__":
    try:
        generate_wallet()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
