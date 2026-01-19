#!/usr/bin/env python3
"""
Migrate liquidity from one tick range to another within the same pool
Usage: python exe_univ3_migrate_liq.py <token_id> <tick_lower> <tick_upper> [--percentage] [--collect-fees] [--burn-old]
Example: python exe_univ3_migrate_liq.py 1157630 -887220 887220
         python exe_univ3_migrate_liq.py 1157630 -887220 887220 --percentage 50
"""

import sys
import json
import os
import time
import argparse
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv('wallet.env')  # Also load from wallet.env


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

# Contract addresses
NFPM_ADDRESS = Web3.to_checksum_address(CONFIG['contracts']['uniswap_v3_nfpm'])
COMMON_TOKENS = CONFIG['common_tokens']


class UniswapV3LiquidityMigrator:
    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        private_key = os.getenv('PRIVATE_KEY')

        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")
        if not private_key:
            raise ValueError("PRIVATE_KEY not found in wallet.env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

        self.account = self.w3.eth.account.from_key(private_key)
        self.address = self.account.address

        self.nfpm = self.w3.eth.contract(
            address=NFPM_ADDRESS,
            abi=ABIS['uniswap_v3_nfpm']
        )

        self.factory = self.w3.eth.contract(
            address=Web3.to_checksum_address(
                CONFIG['contracts']['uniswap_v3_factory']),
            abi=ABIS['uniswap_v3_factory']
        )

        print(f"📝 Using account: {self.address}")
        print(
            f"💰 ETH Balance: {self.w3.from_wei(self.w3.eth.get_balance(self.address), 'ether'):.6f} ETH\n")

    def get_position_info(self, token_id):
        """Get position information"""
        try:
            position = self.nfpm.functions.positions(token_id).call()
            return {
                'nonce': position[0],
                'operator': position[1],
                'token0': position[2],
                'token1': position[3],
                'fee': position[4],
                'tickLower': position[5],
                'tickUpper': position[6],
                'liquidity': position[7],
                'feeGrowthInside0LastX128': position[8],
                'feeGrowthInside1LastX128': position[9],
                'tokensOwed0': position[10],
                'tokensOwed1': position[11]
            }
        except Exception as e:
            raise ValueError(
                f"Failed to get position info for token_id {token_id}: {e}")

    def get_token_info(self, token_address):
        """Get token decimals and symbol"""
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ABIS['erc20']
        )
        return {
            'decimals': token.functions.decimals().call(),
            'symbol': token.functions.symbol().call(),
            'contract': token
        }

    def get_tick_spacing(self, fee):
        """Get tick spacing for a given fee tier"""
        tick_spacing_map = {
            100: 1,
            500: 10,
            3000: 60,
            10000: 200
        }
        if fee not in tick_spacing_map:
            raise ValueError(
                f"Unsupported fee tier: {fee}. Supported fees: 100, 500, 3000, 10000")
        return tick_spacing_map[fee]

    def round_tick_to_spacing(self, tick, spacing):
        """Round tick to nearest valid tick based on spacing"""
        import math
        if tick >= 0:
            return (tick // spacing) * spacing
        else:
            return math.floor(tick / spacing) * spacing

    def validate_and_adjust_ticks(self, tick_lower, tick_upper, fee):
        """Validate and adjust ticks to be valid for the fee tier"""
        spacing = self.get_tick_spacing(fee)

        adjusted_lower = self.round_tick_to_spacing(tick_lower, spacing)
        adjusted_upper = self.round_tick_to_spacing(tick_upper, spacing)

        if adjusted_lower >= adjusted_upper:
            raise ValueError(
                f"Invalid tick range: lower ({adjusted_lower}) must be < upper ({adjusted_upper})")

        if adjusted_lower != tick_lower or adjusted_upper != tick_upper:
            print(f"⚠️  Tick spacing adjustment:")
            if adjusted_lower != tick_lower:
                print(
                    f"   tick_lower: {tick_lower} → {adjusted_lower} (spacing: {spacing})")
            if adjusted_upper != tick_upper:
                print(
                    f"   tick_upper: {tick_upper} → {adjusted_upper} (spacing: {spacing})")
            print()

        return adjusted_lower, adjusted_upper, spacing

    def check_balance(self, token_contract, amount_wei, token_symbol):
        """Check if account has sufficient token balance"""
        balance = token_contract.functions.balanceOf(self.address).call()

        if balance < amount_wei:
            raise ValueError(
                f"Insufficient {token_symbol} balance. Required: {amount_wei}, Available: {balance}")
        return True

    def approve_token(self, token_contract, spender, amount, token_symbol):
        """Approve token spending if needed"""
        allowance = token_contract.functions.allowance(
            self.address, spender).call()

        if allowance >= amount:
            print(f"✅ {token_symbol} already approved (allowance: {allowance})")
            return None

        print(f"📝 Approving {token_symbol}...")
        nonce = self.w3.eth.get_transaction_count(self.address)

        tx = token_contract.functions.approve(spender, amount).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"⏳ Approval transaction sent: {tx_hash.hex()}")

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            print(f"✅ Approval confirmed in block {receipt.blockNumber}\n")
        else:
            raise Exception("Approval transaction failed")

        return receipt

    def collect_from_position(self, token_id, token0_info, token1_info):
        """Collect fees and tokens from a position"""
        max_amount = 2**128 - 1

        collect_params = {
            'tokenId': token_id,
            'recipient': self.address,
            'amount0Max': max_amount,
            'amount1Max': max_amount
        }

        try:
            nonce = self.w3.eth.get_transaction_count(self.address)

            tx = self.nfpm.functions.collect(collect_params).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })

            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(
                signed_tx.rawTransaction)

            print(f"⏳ Collect transaction sent: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                try:
                    collect_event = self.nfpm.events.Collect().process_receipt(receipt)
                    if collect_event and len(collect_event) > 0:
                        amount0 = collect_event[0]['args'].get('amount0', 0)
                        amount1 = collect_event[0]['args'].get('amount1', 0)
                        print(f"✅ Collected: {amount0 / (10 ** token0_info['decimals']):.6f} {token0_info['symbol']}, "
                              f"{amount1 / (10 ** token1_info['decimals']):.6f} {token1_info['symbol']}\n")
                    else:
                        print("✅ Collect completed\n")
                except:
                    print("✅ Collect completed\n")
            else:
                raise Exception("Collect transaction failed")
            return receipt
        except Exception as e:
            raise Exception(f"Error collecting fees: {e}")

    def decrease_liquidity(self, token_id, liquidity_to_remove):
        """Decrease liquidity from a position"""
        deadline = int(time.time()) + 1800

        decrease_params = {
            'tokenId': token_id,
            'liquidity': liquidity_to_remove,
            'amount0Min': 0,
            'amount1Min': 0,
            'deadline': deadline
        }

        nonce = self.w3.eth.get_transaction_count(self.address)

        try:
            gas_estimate = self.nfpm.functions.decreaseLiquidity(decrease_params).estimate_gas({
                'from': self.address
            })
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            gas_estimate = 500000

        tx = self.nfpm.functions.decreaseLiquidity(decrease_params).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"⏳ Decrease liquidity transaction sent: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ Liquidity decreased in block {receipt.blockNumber}\n")
            return receipt
        else:
            raise Exception("Decrease liquidity transaction failed")

    def add_liquidity_to_new_range(self, position, token0_info, token1_info,
                                   new_tick_lower, new_tick_upper, amount0_wei, amount1_wei, slippage_bps=50):
        """Add liquidity to a new tick range"""
        slippage_multiplier = (10000 - slippage_bps) / 10000
        amount0_min = int(amount0_wei * slippage_multiplier)
        amount1_min = int(amount1_wei * slippage_multiplier)

        deadline = int(time.time()) + 1800

        mint_params = {
            'token0': Web3.to_checksum_address(position['token0']),
            'token1': Web3.to_checksum_address(position['token1']),
            'fee': position['fee'],
            'tickLower': new_tick_lower,
            'tickUpper': new_tick_upper,
            'amount0Desired': amount0_wei,
            'amount1Desired': amount1_wei,
            'amount0Min': amount0_min,
            'amount1Min': amount1_min,
            'recipient': self.address,
            'deadline': deadline
        }

        # Approve tokens
        self.approve_token(
            token0_info['contract'], NFPM_ADDRESS, amount0_wei, token0_info['symbol'])
        self.approve_token(
            token1_info['contract'], NFPM_ADDRESS, amount1_wei, token1_info['symbol'])

        print("🚀 Adding liquidity to new range...")
        print(f"   Tick Range: {new_tick_lower} to {new_tick_upper}\n")

        nonce = self.w3.eth.get_transaction_count(self.address)

        try:
            gas_estimate = self.nfpm.functions.mint(mint_params).estimate_gas({
                'from': self.address
            })
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            gas_estimate = 1000000

        tx = self.nfpm.functions.mint(mint_params).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"⏳ Add liquidity transaction sent: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ Liquidity added in block {receipt.blockNumber}")

            # Parse Mint event to get new token ID
            mint_event = self.nfpm.events.Mint().process_receipt(receipt)
            if mint_event:
                new_token_id = mint_event[0]['args']['tokenId']
                actual_amount0 = mint_event[0]['args']['amount0']
                actual_amount1 = mint_event[0]['args']['amount1']

                print(f"🎉 New position created!")
                print(f"📍 New Token ID: {new_token_id}")
                print(
                    f"💰 Amount 0 used: {actual_amount0 / (10 ** token0_info['decimals']):.6f} {token0_info['symbol']}")
                print(
                    f"💰 Amount 1 used: {actual_amount1 / (10 ** token1_info['decimals']):.6f} {token1_info['symbol']}\n")
                return new_token_id, receipt
            else:
                print("⚠️  Warning: Could not parse Mint event from receipt\n")
                return None, receipt
        else:
            raise Exception("Add liquidity transaction failed")

    def burn_position(self, token_id):
        """Burn the position NFT"""
        try:
            nonce = self.w3.eth.get_transaction_count(self.address)

            tx = self.nfpm.functions.burn(token_id).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })

            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(
                signed_tx.rawTransaction)

            print(f"⏳ Burn transaction sent: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print(
                    f"✅ Position burned successfully in block {receipt.blockNumber}\n")
            else:
                print("⚠️  Burn transaction failed\n")
        except Exception as e:
            print(f"⚠️  Error burning position: {e}\n")

    def migrate_liquidity(self, token_id, new_tick_lower, new_tick_upper,
                          percentage=100, collect_fees=True, burn_old=False, slippage_bps=50):
        """Migrate liquidity from one tick range to another"""

        print(f"🔄 Migrating liquidity from position {token_id}...\n")

        # Get current position info
        print("🔍 Fetching current position information...")
        position = self.get_position_info(token_id)

        # Verify ownership
        try:
            owner = self.nfpm.functions.ownerOf(token_id).call()
            if owner.lower() != self.address.lower():
                raise ValueError(
                    f"Position token_id {token_id} is not owned by {self.address} (owner: {owner})")
        except Exception as e:
            raise ValueError(f"Failed to verify ownership: {e}")

        print("✅ Ownership verified\n")

        # Get token info
        token0_info = self.get_token_info(position['token0'])
        token1_info = self.get_token_info(position['token1'])

        print(f"📊 Current Position:")
        print(
            f"   Token Pair: {token0_info['symbol']}/{token1_info['symbol']}")
        print(f"   Fee Tier: {position['fee'] / 10000}% ({position['fee']})")
        print(
            f"   Current Tick Range: {position['tickLower']} to {position['tickUpper']}")
        print(f"   Current Liquidity: {position['liquidity']}")
        print(f"   Tokens Owed (fees): {position['tokensOwed0'] / (10**token0_info['decimals']):.6f} {token0_info['symbol']}, "
              f"{position['tokensOwed1'] / (10**token1_info['decimals']):.6f} {token1_info['symbol']}\n")

        # Validate and adjust new ticks
        new_tick_lower, new_tick_upper, spacing = self.validate_and_adjust_ticks(
            new_tick_lower, new_tick_upper, position['fee'])

        print(f"📊 New Position:")
        print(f"   New Tick Range: {new_tick_lower} to {new_tick_upper}")
        print(f"   Tick Spacing: {spacing}\n")

        # Calculate liquidity to remove
        current_liquidity = position['liquidity']
        liquidity_to_remove = int(current_liquidity * percentage / 100)

        if liquidity_to_remove == 0:
            raise ValueError("Cannot migrate 0 liquidity")

        if liquidity_to_remove > current_liquidity:
            raise ValueError(
                f"Cannot migrate more liquidity ({liquidity_to_remove}) than current ({current_liquidity})")

        print(f"📦 Migration Plan:")
        print(
            f"   Migrating {percentage}% of liquidity ({liquidity_to_remove} / {current_liquidity})")
        print(
            f"   From range: {position['tickLower']} to {position['tickUpper']}")
        print(f"   To range: {new_tick_lower} to {new_tick_upper}\n")

        # Step 1: Collect fees (optional but recommended)
        if collect_fees:
            print("💰 Step 1: Collecting fees from old position...")
            self.collect_from_position(token_id, token0_info, token1_info)

        # Step 2: Decrease liquidity from old position
        print(
            f"🗑️  Step 2: Removing {percentage}% of liquidity from old position...")
        self.decrease_liquidity(token_id, liquidity_to_remove)

        # Step 3: Collect the tokens from the decrease
        print("💰 Step 3: Collecting tokens from removed liquidity...")
        collect_receipt = self.collect_from_position(
            token_id, token0_info, token1_info)

        # Step 4: Get token balances after collection
        print("🔍 Step 4: Checking token balances for new position...")
        balance0 = token0_info['contract'].functions.balanceOf(
            self.address).call()
        balance1 = token1_info['contract'].functions.balanceOf(
            self.address).call()

        print(
            f"   Available {token0_info['symbol']}: {balance0 / (10**token0_info['decimals']):.6f}")
        print(
            f"   Available {token1_info['symbol']}: {balance1 / (10**token1_info['decimals']):.6f}\n")

        # Step 5: Add liquidity to new range
        print("➕ Step 5: Adding liquidity to new tick range...")
        new_token_id, mint_receipt = self.add_liquidity_to_new_range(
            position, token0_info, token1_info,
            new_tick_lower, new_tick_upper,
            balance0, balance1, slippage_bps
        )

        # Step 6: Burn old position if requested and all liquidity was migrated
        if burn_old and percentage == 100:
            print("🔥 Step 6: Burning old position NFT...")
            self.burn_position(token_id)
        elif burn_old and percentage < 100:
            print(
                "⚠️  Warning: --burn-old flag ignored (only burns when migrating 100% liquidity)")

        print("=" * 80)
        print("✅ Migration completed successfully!")
        print(
            f"📍 Old Position: Token ID {token_id} ({100 - percentage}% liquidity remaining)")
        if new_token_id:
            print(
                f"📍 New Position: Token ID {new_token_id} (in new tick range)")
        print("=" * 80)

        return new_token_id


def main():
    parser = argparse.ArgumentParser(
        description='Migrate liquidity from one tick range to another within the same pool'
    )

    parser.add_argument('token_id', type=int,
                        help='Current position NFT token ID')
    parser.add_argument('tick_lower', type=int, help='New lower tick bound')
    parser.add_argument('tick_upper', type=int, help='New upper tick bound')
    parser.add_argument('--percentage', type=float, default=100,
                        help='Percentage of liquidity to migrate (default: 100)')
    parser.add_argument('--no-collect-fees', action='store_true',
                        help='Skip fee collection before migration (default: collect fees)')
    parser.add_argument('--burn-old', action='store_true',
                        help='Burn old position NFT after migration (only when migrating 100%)')
    parser.add_argument('--slippage', type=float, default=0.5,
                        help='Slippage tolerance in percentage (default: 0.5)')

    args = parser.parse_args()

    if args.percentage <= 0 or args.percentage > 100:
        print("❌ Error: percentage must be between 0 and 100")
        sys.exit(1)

    try:
        migrator = UniswapV3LiquidityMigrator()

        new_token_id = migrator.migrate_liquidity(
            token_id=args.token_id,
            new_tick_lower=args.tick_lower,
            new_tick_upper=args.tick_upper,
            percentage=args.percentage,
            collect_fees=not args.no_collect_fees,
            burn_old=args.burn_old,
            slippage_bps=int(args.slippage * 100)
        )

        if new_token_id:
            print(
                f"\n📊 View new position: python query_univ3_position.py {new_token_id}")

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
