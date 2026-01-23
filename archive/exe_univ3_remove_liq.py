#!/usr/bin/env python3
"""
Remove liquidity from a Uniswap V3 position
Usage: python exe_univ3_remove_liq.py <token_id> <liquidity_percentage> [--collect-fees] [--burn]
Example: python exe_univ3_remove_liq.py 1157630 50 --collect-fees
         python exe_univ3_remove_liq.py 1157630 100 --collect-fees --burn
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


class UniswapV3LiquidityRemover:
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
            'symbol': token.functions.symbol().call()
        }

    def decrease_liquidity(self, token_id, liquidity_percentage, collect_fees=True, burn=False, slippage_bps=50):
        """Decrease liquidity from a position"""

        print(f"🔍 Fetching position information for token_id {token_id}...")
        position = self.get_position_info(token_id)

        # Get token info
        token0_info = self.get_token_info(position['token0'])
        token1_info = self.get_token_info(position['token1'])

        current_liquidity = position['liquidity']
        tokens_owed0 = position['tokensOwed0']
        tokens_owed1 = position['tokensOwed1']

        print(f"📊 Position Information:")
        print(f"   Token 0: {token0_info['symbol']} ({position['token0']})")
        print(f"   Token 1: {token1_info['symbol']} ({position['token1']})")
        print(f"   Fee Tier: {position['fee'] / 10000}% ({position['fee']})")
        print(
            f"   Tick Range: {position['tickLower']} to {position['tickUpper']}")
        print(f"   Current Liquidity: {current_liquidity}")
        print(f"   Tokens Owed (fees): {tokens_owed0 / (10**token0_info['decimals']):.6f} {token0_info['symbol']}, "
              f"{tokens_owed1 / (10**token1_info['decimals']):.6f} {token1_info['symbol']}\n")

        # Calculate liquidity to remove
        if liquidity_percentage == 100:
            liquidity_to_remove = current_liquidity
            print(f"🗑️  Removing 100% of liquidity ({current_liquidity})")
        else:
            liquidity_to_remove = int(
                current_liquidity * liquidity_percentage / 100)
            print(
                f"🗑️  Removing {liquidity_percentage}% of liquidity ({liquidity_to_remove} / {current_liquidity})")

        if liquidity_to_remove == 0:
            raise ValueError("Cannot remove 0 liquidity")

        if liquidity_to_remove > current_liquidity:
            raise ValueError(
                f"Cannot remove more liquidity ({liquidity_to_remove}) than current ({current_liquidity})")

        # Check if owner
        try:
            owner = self.nfpm.functions.ownerOf(token_id).call()
            if owner.lower() != self.address.lower():
                raise ValueError(
                    f"Position token_id {token_id} is not owned by {self.address} (owner: {owner})")
        except Exception as e:
            raise ValueError(f"Failed to verify ownership: {e}")

        print("✅ Ownership verified\n")

        # Prepare decreaseLiquidity params
        deadline = int(time.time()) + 1800  # 30 minutes

        # For slippage, we'll set minimum amounts to 0 for now (you can calculate expected amounts)
        # In production, you might want to calculate expected amounts based on current price
        amount0_min = 0
        amount1_min = 0

        decrease_params = {
            'tokenId': token_id,
            'liquidity': liquidity_to_remove,
            'amount0Min': amount0_min,
            'amount1Min': amount1_min,
            'deadline': deadline
        }

        print("🚀 Decreasing liquidity...")
        print(f"   Liquidity to remove: {liquidity_to_remove}")
        print(f"   Deadline: {deadline} ({time.ctime(deadline)})\n")

        # Estimate gas
        try:
            gas_estimate = self.nfpm.functions.decreaseLiquidity(decrease_params).estimate_gas({
                'from': self.address
            })
            print(f"⛽ Estimated gas: {gas_estimate:,}")
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            gas_estimate = 500000  # Fallback

        # Build and send decreaseLiquidity transaction
        nonce = self.w3.eth.get_transaction_count(self.address)

        tx = self.nfpm.functions.decreaseLiquidity(decrease_params).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        print(
            f"💰 Gas price: {self.w3.from_wei(self.w3.eth.gas_price, 'gwei'):.2f} Gwei")
        print(
            f"💵 Estimated cost: {self.w3.from_wei(tx['gas'] * tx['gasPrice'], 'ether'):.6f} ETH\n")

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"⏳ Transaction sent: {tx_hash.hex()}")
        print(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash.hex()}\n")

        # Wait for confirmation
        print("⏳ Waiting for confirmation...")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(
                f"✅ Liquidity decreased successfully in block {receipt.blockNumber}\n")

            # Parse DecreaseLiquidity event
            decrease_event = self.nfpm.events.DecreaseLiquidity().process_receipt(receipt)
            if decrease_event:
                amount0 = decrease_event[0]['args']['amount0']
                amount1 = decrease_event[0]['args']['amount1']
                print(
                    f"💰 Amount 0 received: {amount0 / (10 ** token0_info['decimals']):.6f} {token0_info['symbol']}")
                print(
                    f"💰 Amount 1 received: {amount1 / (10 ** token1_info['decimals']):.6f} {token1_info['symbol']}\n")
        else:
            raise Exception("Decrease liquidity transaction failed")

        # Collect fees and tokens if requested
        if collect_fees:
            print("💰 Collecting fees and tokens...")
            self.collect(position, token_id, token0_info, token1_info)

        # Burn position if removing all liquidity and burn flag is set
        if burn and liquidity_percentage == 100:
            print("🔥 Burning position (removing NFT)...")
            self.burn_position(token_id)
        elif burn and liquidity_percentage < 100:
            print(
                "⚠️  Warning: --burn flag ignored (only burns when removing 100% liquidity)")

        return receipt

    def collect(self, position, token_id, token0_info, token1_info):
        """Collect fees and tokens from position"""
        # Collect all available tokens (set max to type(uint128).max equivalent)
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
                # Collect event may not always be emitted, try to parse it
                try:
                    collect_event = self.nfpm.events.Collect().process_receipt(receipt)
                    if collect_event and len(collect_event) > 0:
                        amount0 = collect_event[0]['args'].get('amount0', 0)
                        amount1 = collect_event[0]['args'].get('amount1', 0)
                        print(f"✅ Collected: {amount0 / (10 ** token0_info['decimals']):.6f} {token0_info['symbol']}, "
                              f"{amount1 / (10 ** token1_info['decimals']):.6f} {token1_info['symbol']}\n")
                    else:
                        print("✅ Collect completed (check transaction for details)\n")
                except:
                    print(
                        "✅ Collect completed (event parsing failed, check transaction for details)\n")
            else:
                print("⚠️  Collect transaction failed")
        except Exception as e:
            print(f"⚠️  Error collecting fees: {e}\n")

    def burn_position(self, token_id):
        """Burn the position NFT (only after removing all liquidity)"""
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
                print("⚠️  Burn transaction failed")
        except Exception as e:
            print(f"⚠️  Error burning position: {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Remove liquidity from a Uniswap V3 position'
    )

    parser.add_argument('token_id', type=int, help='Position NFT token ID')
    parser.add_argument('liquidity_percentage', type=float,
                        help='Percentage of liquidity to remove (0-100)')
    parser.add_argument('--collect-fees', action='store_true',
                        help='Collect fees and tokens after decreasing liquidity')
    parser.add_argument('--burn', action='store_true',
                        help='Burn the position NFT (only when removing 100% liquidity)')
    parser.add_argument('--slippage', type=float, default=0.5,
                        help='Slippage tolerance in percentage (default: 0.5)')

    args = parser.parse_args()

    if args.liquidity_percentage <= 0 or args.liquidity_percentage > 100:
        print("❌ Error: liquidity_percentage must be between 0 and 100")
        sys.exit(1)

    try:
        remover = UniswapV3LiquidityRemover()

        remover.decrease_liquidity(
            token_id=args.token_id,
            liquidity_percentage=args.liquidity_percentage,
            collect_fees=args.collect_fees,
            burn=args.burn,
            slippage_bps=int(args.slippage * 100)
        )

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
