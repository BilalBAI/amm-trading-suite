#!/usr/bin/env python3
"""
Query all assets (ETH, tokens, NFTs) held by an Ethereum address
Usage: python query_positions.py 0xYourAddress
"""

import sys
import json
from web3 import Web3
from datetime import datetime
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Load config and ABIs from shared files


def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)


def load_abis():
    """Load ABIs from abis.json"""
    abis_path = os.path.join(os.path.dirname(__file__), 'abis.json')
    with open(abis_path, 'r') as f:
        return json.load(f)


# Load shared config and ABIs
CONFIG = load_config()
ABIS = load_abis()

# Extract values from config
UNISWAP_V3_NFPM = CONFIG['contracts']['uniswap_v3_nfpm']
COMMON_TOKENS = CONFIG['common_tokens']

# Extract ABIs
ERC20_ABI = ABIS['erc20']
ERC721_ABI = ABIS['erc721']
UNISWAP_NFPM_ABI = ABIS['uniswap_v3_nfpm']

# Transfer event signature for finding NFTs
TRANSFER_EVENT_SIG = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class AddressAssetQuery:
    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

    def get_eth_balance(self, address):
        """Get ETH balance"""
        address = Web3.to_checksum_address(address)
        balance_wei = self.w3.eth.get_balance(address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')
        return balance_eth

    def get_token_balance(self, token_address, owner_address):
        """Get ERC20 token balance"""
        try:
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )

            balance = token.functions.balanceOf(
                Web3.to_checksum_address(owner_address)).call()
            decimals = token.functions.decimals().call()
            symbol = token.functions.symbol().call()

            balance_human = balance / (10 ** decimals)

            if balance_human > 0:
                return {
                    'symbol': symbol,
                    'balance': balance_human,
                    'balance_raw': balance,
                    'decimals': decimals,
                    'address': token_address
                }
        except Exception as e:
            pass
        return None

    def get_common_tokens(self, address):
        """Get balances of common tokens"""
        tokens = []
        address = Web3.to_checksum_address(address)

        for symbol, token_addr in COMMON_TOKENS.items():
            token_info = self.get_token_balance(token_addr, address)
            if token_info:
                tokens.append(token_info)

        return tokens

    def find_nft_contracts(self, address):
        """Find NFT contracts by querying Transfer events"""
        address = Web3.to_checksum_address(address)
        address_topic = "0x" + "0" * 24 + address[2:].lower()

        # Get recent blocks (last 10000 blocks ~ 1.4 days)
        current_block = self.w3.eth.block_number
        from_block = max(0, current_block - 10000)

        nft_contracts = set()

        try:
            logs = self.w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": "latest",
                # Transfer to this address
                "topics": [TRANSFER_EVENT_SIG, None, address_topic]
            })

            for log in logs:
                nft_contracts.add(log['address'])
        except Exception as e:
            print(f"Warning: Could not query all Transfer events: {e}")

        return list(nft_contracts)

    def get_uniswap_v3_positions(self, owner_address):
        """Get Uniswap V3 position NFTs directly from NFPM contract"""
        try:
            nfpm = self.w3.eth.contract(
                address=Web3.to_checksum_address(UNISWAP_V3_NFPM),
                abi=UNISWAP_NFPM_ABI
            )

            owner_address = Web3.to_checksum_address(owner_address)
            balance = nfpm.functions.balanceOf(owner_address).call()

            if balance == 0:
                return None

            # Get all token IDs
            token_ids = []
            for i in range(balance):
                try:
                    token_id = nfpm.functions.tokenOfOwnerByIndex(
                        owner_address, i).call()
                    token_ids.append(token_id)
                except Exception as e:
                    continue

            if not token_ids:
                return None

            # Get position details for each token
            positions = []
            for token_id in token_ids:
                try:
                    pos_data = nfpm.functions.positions(token_id).call()
                    _, _, token0, token1, fee, tick_lower, tick_upper, liquidity, _, _, _, _ = pos_data

                    positions.append({
                        'token_id': token_id,
                        'token0': token0,
                        'token1': token1,
                        'fee_tier': fee,
                        'tick_lower': tick_lower,
                        'tick_upper': tick_upper,
                        'liquidity': str(liquidity)
                    })
                except:
                    positions.append({'token_id': token_id})

            return {
                'contract': UNISWAP_V3_NFPM,
                'name': 'Uniswap V3 Positions',
                'symbol': 'UNI-V3-POS',
                'balance': balance,
                'token_ids': token_ids,
                'total_tokens': balance,
                'positions': positions
            }
        except Exception as e:
            return None

    def get_nft_balance(self, nft_address, owner_address):
        """Get NFT balance and owned token IDs"""
        try:
            nft = self.w3.eth.contract(
                address=Web3.to_checksum_address(nft_address),
                abi=ERC721_ABI
            )

            balance = nft.functions.balanceOf(
                Web3.to_checksum_address(owner_address)).call()

            if balance == 0:
                return None

            # Get token IDs
            token_ids = []
            for i in range(balance):
                try:
                    token_id = nft.functions.tokenOfOwnerByIndex(
                        owner_address, i).call()
                    token_ids.append(token_id)
                except:
                    # Some NFTs don't support enumerable, try to get from events
                    pass

            # Try to get name and symbol
            try:
                name = nft.functions.name().call()
            except:
                name = "Unknown"

            try:
                symbol = nft.functions.symbol().call()
            except:
                symbol = "NFT"

            return {
                'contract': nft_address,
                'name': name,
                'symbol': symbol,
                'balance': balance,
                # Limit to first 10
                'token_ids': token_ids[:10] if token_ids else [],
                'total_tokens': balance if not token_ids else len(token_ids)
            }
        except Exception as e:
            return None

    def query_all_assets(self, address):
        """Query all assets for an address"""
        address = Web3.to_checksum_address(address)

        print(f"\n{'='*70}")
        print(f"Querying assets for: {address}")
        print(f"{'='*70}\n")

        results = {
            'address': address,
            'query_time': datetime.now().isoformat(),
            'eth_balance': None,
            'tokens': [],
            'nfts': []
        }

        # Query ETH balance
        print("Querying ETH balance...")
        eth_balance = self.get_eth_balance(address)
        results['eth_balance'] = float(eth_balance)
        print(f"✓ ETH: {eth_balance:.6f} ETH\n")

        # Query common tokens
        print("Querying common tokens...")
        tokens = self.get_common_tokens(address)
        results['tokens'] = tokens
        if tokens:
            for token in tokens:
                print(
                    f"✓ {token['symbol']}: {token['balance']:.6f} ({token['address']})")
        else:
            print("  No common tokens found")
        print()

        # Query Uniswap V3 positions first (direct query)
        print("Querying Uniswap V3 positions...")
        uniswap_nfts = self.get_uniswap_v3_positions(address)
        if uniswap_nfts:
            results['nfts'].append(uniswap_nfts)
            print(
                f"✓ {uniswap_nfts['name']}: {uniswap_nfts['balance']} position(s)")
            if uniswap_nfts['token_ids']:
                token_ids_str = ", ".join(
                    [str(tid) for tid in uniswap_nfts['token_ids']])
                print(f"  Position IDs: {token_ids_str}")
            print(f"  Contract: {uniswap_nfts['contract']}")
        else:
            print("  No Uniswap V3 positions found")
        print()

        # Query other NFTs via Transfer events
        print("Finding other NFT contracts (this may take a moment)...")
        nft_contracts = self.find_nft_contracts(address)

        if nft_contracts:
            print(f"Found {len(nft_contracts)} potential NFT contract(s)")
            for nft_addr in nft_contracts[:20]:  # Limit to first 20 contracts
                # Skip Uniswap V3 NFPM as we already queried it
                if Web3.to_checksum_address(nft_addr) == Web3.to_checksum_address(UNISWAP_V3_NFPM):
                    continue

                nft_info = self.get_nft_balance(nft_addr, address)
                if nft_info:
                    results['nfts'].append(nft_info)
                    token_ids_str = ", ".join(
                        [str(tid) for tid in nft_info['token_ids']])
                    if nft_info['total_tokens'] > len(nft_info['token_ids']):
                        token_ids_str += f", ... (+{nft_info['total_tokens'] - len(nft_info['token_ids'])} more)"
                    print(
                        f"✓ {nft_info['name']} ({nft_info['symbol']}): {nft_info['balance']} tokens")
                    if nft_info['token_ids']:
                        print(f"  Token IDs: {token_ids_str}")
                    print(f"  Contract: {nft_addr}")
        else:
            print("  No other NFTs found in recent transactions")

        return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_positions.py <ethereum_address>")
        print(
            "Example: python query_positions.py 0x5bd19Ea9E14205Bce413994D2640E4e9fb204DD3")
        sys.exit(1)

    address = sys.argv[1]

    # Validate address
    if not Web3.is_address(address):
        print(f"Error: Invalid Ethereum address: {address}")
        sys.exit(1)

    try:
        query = AddressAssetQuery()
        results = query.query_all_assets(address)

        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"ETH Balance: {results['eth_balance']:.6f} ETH")
        print(f"Tokens: {len(results['tokens'])} token(s)")
        print(f"NFTs: {len(results['nfts'])} collection(s)")

        # Save to JSON in results folder
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(results_dir, exist_ok=True)
        output_file = os.path.join(results_dir, f"assets_{address[:10]}.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
