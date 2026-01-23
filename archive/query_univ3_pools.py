#!/usr/bin/env python3
"""
Query current prices, ticks, and fee tiers for Uniswap V3 pools
Usage: python query_univ3_pools.py
"""

import json
import os
from web3 import Web3
from datetime import datetime
from dotenv import load_dotenv
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

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


class UniswapV3StaticQuery:
    """Simple class to fetch and cache static pool data (token0, token1, fee)"""

    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

        self.factory_address = Web3.to_checksum_address(
            CONFIG['contracts']['uniswap_v3_factory'])
        self.factory = self.w3.eth.contract(
            address=self.factory_address, abi=ABIS['uniswap_v3_factory'])

        self.pool_cache_file = os.path.join(
            os.path.dirname(__file__), 'pool_info_univ3.json')
        self.cache = self._load_cache()

    def _load_cache(self):
        """Load static pool cache from file"""
        if os.path.exists(self.pool_cache_file):
            try:
                with open(self.pool_cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Warning: Could not load pool cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save static pool cache to file"""
        try:
            with open(self.pool_cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save pool cache: {e}")

    def _get_token_info(self, address):
        """Get token decimals and symbol"""
        address = Web3.to_checksum_address(address)
        try:
            contract = self.w3.eth.contract(address, abi=ABIS['erc20'])
            decimals = contract.functions.decimals().call()
            symbol = contract.functions.symbol().call()
            return {'decimals': decimals, 'symbol': symbol}
        except Exception:
            # Fallback for tokens that might not have symbol/decimals
            return {'decimals': 18, 'symbol': address[:10]}

    def _get_fee_tier(self, token0_addr, token1_addr, pool_address):
        """Detect fee tier by trying common fees"""
        fee_candidates = [500, 3000, 10000]
        zero_address = '0x0000000000000000000000000000000000000000'
        pool_address_lower = pool_address.lower()

        for fee in fee_candidates:
            try:
                pool_addr = self.factory.functions.getPool(
                    token0_addr, token1_addr, fee).call()
                if (pool_addr and
                    pool_addr.lower() != zero_address and
                        pool_addr.lower() == pool_address_lower):
                    return fee
            except Exception:
                continue

        return None

    def fetch_pool_static_info(self, pool_address):
        """Fetch static pool information (token0, token1, fee)"""
        pool_address = Web3.to_checksum_address(pool_address)

        pool = self.w3.eth.contract(
            address=pool_address,
            abi=ABIS['uniswap_v3_pool']
        )

        # Get token addresses
        token0_addr = pool.functions.token0().call()
        token1_addr = pool.functions.token1().call()

        # Get fee tier
        fee = self._get_fee_tier(token0_addr, token1_addr, pool_address)

        # Retry fee detection if it failed
        if fee is None:
            import time
            time.sleep(0.5)
            fee = self._get_fee_tier(token0_addr, token1_addr, pool_address)

        # Get token info
        token0_info = self._get_token_info(token0_addr)
        token1_info = self._get_token_info(token1_addr)

        static_info = {
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
            'fee': fee
        }

        return static_info

    def fetch_missing_pools(self, pool_addresses):
        """Fetch static info for pools that are not in cache"""
        pool_addresses = [Web3.to_checksum_address(
            addr) for addr in pool_addresses]
        missing = [addr for addr in pool_addresses if addr not in self.cache]

        if not missing:
            return

        print(f"📥 Fetching static info for {len(missing)} pool(s)...")

        for i, pool_address in enumerate(missing, 1):
            try:
                print(f"   [{i}/{len(missing)}] Fetching {pool_address}...")
                static_info = self.fetch_pool_static_info(pool_address)
                self.cache[pool_address] = static_info
                print(f"      ✅ Token0: {static_info['token0']['symbol']}, "
                      f"Token1: {static_info['token1']['symbol']}, "
                      f"Fee: {static_info['fee']}")
            except Exception as e:
                print(f"      ❌ Error: {e}")

        self._save_cache()
        print("✅ Static pool info cached.\n")


class UniswapV3LiveQuery:
    """Class to query live/dynamic pool data (prices, ticks) using parallel processing"""

    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

        self.pool_cache_file = os.path.join(
            os.path.dirname(__file__), 'pool_info_univ3.json')
        self.static_cache = self._load_static_cache()

    def _load_static_cache(self):
        """Load static pool cache from file"""
        if os.path.exists(self.pool_cache_file):
            try:
                with open(self.pool_cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                raise ValueError(f"Could not load pool cache: {e}")
        raise ValueError(
            "pool_info_univ3.json not found. Run static query first.")

    def _get_static_info(self, pool_address):
        """Get static info from cache"""
        pool_address = Web3.to_checksum_address(pool_address)
        if pool_address not in self.static_cache:
            raise ValueError(f"Pool {pool_address} not found in cache")
        return self.static_cache[pool_address]

    def get_pool_live_info(self, pool_address):
        """Get live pool information (current price, tick)"""
        pool_address = Web3.to_checksum_address(pool_address)

        try:
            # Get static info from cache
            static_info = self._get_static_info(pool_address)

            # Query dynamic data (slot0)
            pool = self.w3.eth.contract(
                address=pool_address,
                abi=ABIS['uniswap_v3_pool']
            )

            slot0 = pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]

            # Calculate prices using cached token decimals
            price_raw = (sqrt_price_x96 / Q96) ** 2
            price_token1_in_token0 = price_raw * \
                (10 ** static_info['token0']['decimals']) / \
                (10 ** static_info['token1']['decimals'])
            price_token0_in_token1 = 1 / price_token1_in_token0

            return {
                'pool_address': pool_address,
                'token0': static_info['token0'],
                'token1': static_info['token1'],
                'current_tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'price_token1_in_token0': price_token1_in_token0,
                'price_token0_in_token1': price_token0_in_token1,
                'fee': static_info['fee'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'pool_address': pool_address,
                'error': str(e)
            }

    def query_all_pools(self, pool_config):
        """Query all pools in parallel for live data"""
        pool_items = list(pool_config.items())
        results = OrderedDict()

        print(
            f"📊 Querying live data for {len(pool_items)} pool(s) in parallel...\n")

        def query_single_pool(pool_name, pool_address):
            try:
                pool_info = self.get_pool_live_info(pool_address)
                return pool_name, pool_info
            except Exception as e:
                return pool_name, {
                    'pool_address': Web3.to_checksum_address(pool_address),
                    'error': str(e)
                }

        with ThreadPoolExecutor(max_workers=len(pool_items)) as executor:
            futures = {
                executor.submit(query_single_pool, name, addr): name
                for name, addr in pool_items
            }

            for future in as_completed(futures):
                pool_name, pool_info = future.result()
                results[pool_name] = pool_info

                print(f"📊 {pool_name}")
                if 'error' in pool_info:
                    print(f"   ❌ Error: {pool_info['error']}\n")
                else:
                    print(f"   ✅ Token 0: {pool_info['token0']['symbol']}")
                    print(f"   ✅ Token 1: {pool_info['token1']['symbol']}")
                    print(f"   📍 Current Tick: {pool_info['current_tick']}")
                    if pool_info['fee']:
                        print(
                            f"   💵 Fee Tier: {pool_info['fee'] / 10000}% ({pool_info['fee']})")
                    print(
                        f"   💰 Price: 1 {pool_info['token0']['symbol']} = {pool_info['price_token1_in_token0']:.6f} {pool_info['token1']['symbol']}")
                    print(
                        f"   💰 Price: 1 {pool_info['token1']['symbol']} = {pool_info['price_token0_in_token1']:.6f} {pool_info['token0']['symbol']}")
                    print()

        # Sort results to maintain original order
        sorted_results = OrderedDict(
            (name, results[name]) for name in pool_config.keys()
            if name in results
        )
        return sorted_results

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
        pools_config = CONFIG.get('univ3_pools', {})

        if not pools_config:
            print("⚠️  No pools defined in config.json 'univ3_pools' section")
            return

        print("=" * 80)
        print("UNISWAP V3 POOL PRICES")
        print("=" * 80)
        print()

        # Step 1: Check cache and fetch missing static data
        static_query = UniswapV3StaticQuery()
        pool_addresses = list(pools_config.values())
        static_query.fetch_missing_pools(pool_addresses)

        # Step 2: Query live data in parallel
        live_query = UniswapV3LiveQuery()
        results = live_query.query_all_pools(pools_config)

        if results:
            live_query.print_results_table(results)
            live_query.save_results(results)

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
