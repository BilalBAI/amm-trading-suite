#!/usr/bin/env python3
"""
Query current prices, ticks, and fee tiers for Uniswap V3 pools
Usage: python query_univ3_pools.py
"""

import json
import math
import os
from web3 import Web3
from datetime import datetime
from dotenv import load_dotenv
from collections import OrderedDict

# Load environment variables
load_dotenv()


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


CONFIG = load_config()
ABIS = load_abis()

Q96 = 2 ** 96


def tick_to_price(tick, dec0, dec1):
    """Convert tick to human-readable price (token1/token0)"""
    price_raw = 1.0001 ** tick
    # Adjust for token decimals
    price_adjusted = price_raw * (10 ** dec0) / (10 ** dec1)
    return price_adjusted


def sqrt_price_to_price(sqrt_price_x96, dec0, dec1):
    """Convert sqrtPriceX96 to human-readable price (token1/token0)"""
    # sqrtPriceX96 = sqrt(price) * 2^96
    # price = (sqrtPriceX96 / 2^96)^2
    price_raw = (sqrt_price_x96 / Q96) ** 2
    # Adjust for token decimals
    price_adjusted = price_raw * (10 ** dec0) / (10 ** dec1)
    return price_adjusted


class UniswapV3PriceQuery:
    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

        self.token_cache = {}

    def get_token_info(self, address):
        """Get token decimals and symbol (cached)"""
        address = Web3.to_checksum_address(address)
        if address not in self.token_cache:
            try:
                contract = self.w3.eth.contract(
                    address, abi=ABIS['erc20'])
                self.token_cache[address] = {
                    'decimals': contract.functions.decimals().call(),
                    'symbol': contract.functions.symbol().call()
                }
            except Exception as e:
                # Fallback for tokens that might not have symbol/decimals
                self.token_cache[address] = {
                    'decimals': 18,
                    'symbol': address[:10]
                }
        return self.token_cache[address]

    def get_pool_info(self, pool_address):
        """Get pool information including current price and tick"""
        pool_address = Web3.to_checksum_address(pool_address)
        pool = self.w3.eth.contract(
            address=pool_address,
            abi=ABIS['uniswap_v3_pool']
        )

        try:
            # Get slot0 (contains sqrtPriceX96 and current tick)
            slot0 = pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]

            # Get token addresses
            token0_addr = pool.functions.token0().call()
            token1_addr = pool.functions.token1().call()

            # Get fee tier by trying to get pool from factory with different fees
            # Or we can try to read it from the pool's immutable storage (not directly accessible)
            # For now, we'll try common fee tiers
            fee = None
            factory_address = Web3.to_checksum_address(
                CONFIG['contracts']['uniswap_v3_factory'])
            factory = self.w3.eth.contract(
                address=factory_address, abi=ABIS['uniswap_v3_factory'])
            for test_fee in [500, 3000, 10000]:
                try:
                    pool_addr = factory.functions.getPool(
                        token0_addr, token1_addr, test_fee).call()
                    if pool_addr and pool_addr.lower() == pool_address.lower():
                        fee = test_fee
                        break
                except:
                    continue

            # Get token info
            token0_info = self.get_token_info(token0_addr)
            token1_info = self.get_token_info(token1_addr)

            # Calculate prices
            # sqrtPriceX96 = sqrt(amount1/amount0) * 2^96
            # where amount1 and amount0 are in their raw units (wei)
            # price_raw = (sqrtPriceX96 / 2^96)^2 = amount1_wei/amount0_wei

            # To get human-readable price (token1/token0):
            # price = (amount1 / 10^dec1) / (amount0 / 10^dec0)
            # = (amount1_wei / 10^dec1) / (amount0_wei / 10^dec0)
            # = (amount1_wei / amount0_wei) * (10^dec0 / 10^dec1)
            # = price_raw * (10^dec0 / 10^dec1)

            price_raw = (sqrt_price_x96 / Q96) ** 2
            # price_raw = amount1_wei / amount0_wei
            # To get human-readable: price = (amount1 / 10^dec1) / (amount0 / 10^dec0)
            # = price_raw * (10^dec0 / 10^dec1)
            # This gives us: price of token1 in terms of token0
            price_token1_in_token0 = price_raw * \
                (10 ** token0_info['decimals']) / \
                (10 ** token1_info['decimals'])
            # Inverse: price of token0 in terms of token1
            price_token0_in_token1 = 1 / price_token1_in_token0

            return {
                'pool_address': pool_address,
                'token0': {
                    'address': token0_addr,
                    'symbol': token0_info['symbol'],
                    'decimals': token0_info['decimals']
                },
                'token1': {
                    'address': token1_addr,
                    'symbol': token1_info['symbol'],
                    'decimals': token1_info['decimals']
                },
                'current_tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'price_token1_in_token0': price_token1_in_token0,
                'price_token0_in_token1': price_token0_in_token1,
                'fee': fee,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'pool_address': pool_address,
                'error': str(e)
            }

    def query_all_pools(self):
        """Query all pools defined in config"""
        pools_config = CONFIG.get('univ3_pools', {})

        if not pools_config:
            print("⚠️  No pools defined in config.json 'univ3_pools' section")
            return {}

        results = OrderedDict()

        print("=" * 80)
        print("UNISWAP V3 POOL PRICES")
        print("=" * 80)
        print(f"Querying {len(pools_config)} pool(s)...\n")

        for pool_name, pool_address in pools_config.items():
            print(f"📊 Querying {pool_name}...")
            pool_info = self.get_pool_info(pool_address)
            results[pool_name] = pool_info

            if 'error' in pool_info:
                print(f"   ❌ Error: {pool_info['error']}\n")
            else:
                print(f"   ✅ Token 0: {pool_info['token0']['symbol']}")
                print(f"   ✅ Token 1: {pool_info['token1']['symbol']}")
                print(f"   📍 Current Tick: {pool_info['current_tick']}")
                if pool_info['fee']:
                    print(
                        f"   💵 Fee Tier: {pool_info['fee'] / 10000}% ({pool_info['fee']})")
                # price_token1_in_token0 = price of token1 in terms of token0 (e.g., USDT per WETH)
                # price_token0_in_token1 = price of token0 in terms of token1 (e.g., WETH per USDT)
                # So: 1 token0 = price_token1_in_token0 token1
                # And: 1 token1 = price_token0_in_token1 token0
                print(
                    f"   💰 Price: 1 {pool_info['token0']['symbol']} = {pool_info['price_token1_in_token0']:.6f} {pool_info['token1']['symbol']}")
                print(
                    f"   💰 Price: 1 {pool_info['token1']['symbol']} = {pool_info['price_token0_in_token1']:.6f} {pool_info['token0']['symbol']}")
                print()

        return results

    def print_results_table(self, results):
        """Print results in a formatted table"""
        print("=" * 80)
        print("SUMMARY TABLE")
        print("=" * 80)
        print(f"{'Pool':<20} {'Token Pair':<25} {'Tick':<12} {'Price':<30}")
        print("-" * 80)

        for pool_name, pool_info in results.items():
            if 'error' in pool_info:
                print(
                    f"{pool_name:<20} {'ERROR':<25} {'-':<12} {pool_info['error']:<30}")
                continue

            token_pair = f"{pool_info['token0']['symbol']}/{pool_info['token1']['symbol']}"
            tick = str(pool_info['current_tick'])
            price = f"1 {pool_info['token0']['symbol']} = {pool_info['price_token1_in_token0']:.4f} {pool_info['token1']['symbol']}"

            print(f"{pool_name:<20} {token_pair:<25} {tick:<12} {price:<30}")

        print("=" * 80)

    def save_results(self, results):
        """Save results to JSON file"""
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(results_dir, exist_ok=True)
        
        output_file = os.path.join(results_dir, 'univ3_pools.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")


def main():
    try:
        query = UniswapV3PriceQuery()
        results = query.query_all_pools()

        if results:
            query.print_results_table(results)
            query.save_results(results)

            # Also output JSON to stdout
            print("\n" + "=" * 80)
            print("JSON OUTPUT")
            print("=" * 80)
            print(json.dumps(results, indent=2))
        else:
            print("No results to display.")

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
