#!/usr/bin/env python3
"""
Add liquidity to a Uniswap V3 pool
Usage: python univ3_add_liq.py <token0> <token1> <fee> <tick_lower> <tick_upper> <amount0> <amount1> [slippage]
Example: python univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300 0.5
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


class UniswapV3LiquidityAdder:
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

    def get_token_address(self, token_input):
        """Get token address from symbol or address"""
        token_input = token_input.upper()
        if token_input in COMMON_TOKENS:
            return Web3.to_checksum_address(COMMON_TOKENS[token_input])
        elif token_input.startswith('0x'):
            return Web3.to_checksum_address(token_input)
        else:
            raise ValueError(
                f"Token '{token_input}' not found in common tokens and not a valid address")

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
        # For negative ticks, we need to round down (floor)
        # For positive ticks, we round down as well
        # Formula: valid_tick = floor(tick / spacing) * spacing
        if tick >= 0:
            return (tick // spacing) * spacing
        else:
            # For negative ticks, need to round towards -infinity
            return math.floor(tick / spacing) * spacing

    def validate_and_adjust_ticks(self, tick_lower, tick_upper, fee):
        """Validate and adjust ticks to be valid for the fee tier"""
        spacing = self.get_tick_spacing(fee)

        adjusted_lower = self.round_tick_to_spacing(tick_lower, spacing)
        adjusted_upper = self.round_tick_to_spacing(tick_upper, spacing)

        adjusted = False
        if adjusted_lower != tick_lower or adjusted_upper != tick_upper:
            adjusted = True
            print(f"⚠️  Tick spacing adjustment:")
            if adjusted_lower != tick_lower:
                print(
                    f"   tick_lower: {tick_lower} → {adjusted_lower} (spacing: {spacing})")
            if adjusted_upper != tick_upper:
                print(
                    f"   tick_upper: {tick_upper} → {adjusted_upper} (spacing: {spacing})")
            print()

        if adjusted_lower >= adjusted_upper:
            raise ValueError(
                f"Invalid tick range: lower ({adjusted_lower}) must be < upper ({adjusted_upper})")

        return adjusted_lower, adjusted_upper, spacing

    def check_balance(self, token_address, amount_wei):
        """Check if account has sufficient token balance"""
        if token_address.lower() == 'eth':
            balance = self.w3.eth.get_balance(self.address)
        else:
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ABIS['erc20']
            )
            balance = token.functions.balanceOf(self.address).call()

        if balance < amount_wei:
            raise ValueError(
                f"Insufficient balance. Required: {amount_wei}, Available: {balance}")
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

    def add_liquidity(self, token0_addr, token1_addr, fee, tick_lower, tick_upper,
                      amount0_human, amount1_human, slippage_bps=50):
        """Add liquidity to Uniswap V3 pool"""

        # Validate and adjust ticks to match tick spacing for fee tier
        tick_lower, tick_upper, spacing = self.validate_and_adjust_ticks(
            tick_lower, tick_upper, fee)

        # Ensure token0 < token1 (Uniswap requirement)
        if int(token0_addr, 16) > int(token1_addr, 16):
            token0_addr, token1_addr = token1_addr, token0_addr
            amount0_human, amount1_human = amount1_human, amount0_human
            print("🔄 Swapped token order to satisfy token0 < token1 requirement\n")

        # Get token info
        token0_info = self.get_token_info(token0_addr)
        token1_info = self.get_token_info(token1_addr)

        print(f"📊 Token 0: {token0_info['symbol']} ({token0_addr})")
        print(f"📊 Token 1: {token1_info['symbol']} ({token1_addr})")
        print(f"💰 Fee Tier: {fee / 10000}% ({fee})")
        print(f"📏 Tick Spacing: {spacing}\n")

        # Convert amounts to wei
        amount0_wei = int(amount0_human * (10 ** token0_info['decimals']))
        amount1_wei = int(amount1_human * (10 ** token1_info['decimals']))

        # Calculate min amounts with slippage protection
        slippage_multiplier = (10000 - slippage_bps) / 10000
        amount0_min = int(amount0_wei * slippage_multiplier)
        amount1_min = int(amount1_wei * slippage_multiplier)

        print(
            f"💵 Amount 0: {amount0_human} {token0_info['symbol']} ({amount0_wei} wei)")
        print(
            f"💵 Amount 1: {amount1_human} {token1_info['symbol']} ({amount1_wei} wei)")
        print(f"🛡️  Slippage: {slippage_bps / 100}%")
        print(f"📉 Min Amount 0: {amount0_min} wei")
        print(f"📉 Min Amount 1: {amount1_min} wei\n")

        # Check balances
        print("🔍 Checking balances...")
        self.check_balance(token0_addr, amount0_wei)
        self.check_balance(token1_addr, amount1_wei)
        print("✅ Sufficient balances\n")

        # Approve tokens
        approve_token0 = self.approve_token(
            token0_info['contract'], NFPM_ADDRESS, amount0_wei, token0_info['symbol']
        )
        approve_token1 = self.approve_token(
            token1_info['contract'], NFPM_ADDRESS, amount1_wei, token1_info['symbol']
        )

        # Prepare mint parameters
        deadline = int(time.time()) + 1800  # 30 minutes from now

        mint_params = {
            'token0': Web3.to_checksum_address(token0_addr),
            'token1': Web3.to_checksum_address(token1_addr),
            'fee': fee,
            'tickLower': tick_lower,
            'tickUpper': tick_upper,
            'amount0Desired': amount0_wei,
            'amount1Desired': amount1_wei,
            'amount0Min': amount0_min,
            'amount1Min': amount1_min,
            'recipient': self.address,
            'deadline': deadline
        }

        print("🚀 Creating liquidity position...")
        print(f"   Tick Range: {tick_lower} to {tick_upper}")
        print(f"   Deadline: {deadline} ({time.ctime(deadline)})\n")

        # Estimate gas
        try:
            gas_estimate = self.nfpm.functions.mint(mint_params).estimate_gas({
                'from': self.address
            })
            print(f"⛽ Estimated gas: {gas_estimate:,}")
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            gas_estimate = 1000000  # Fallback

        # Build and send transaction
        nonce = self.w3.eth.get_transaction_count(self.address)

        tx = self.nfpm.functions.mint(mint_params).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),  # Add 20% buffer
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        print(
            f"💰 Gas price: {self.w3.from_wei(self.w3.eth.gas_price, 'gwei'):.2f} Gwei")
        print(
            f"💵 Estimated cost: {self.w3.from_wei(tx['gas'] * tx['gasPrice'], 'ether'):.6f} ETH\n")

        # Ask for confirmation (in production, you might want to add this)
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"⏳ Transaction sent: {tx_hash.hex()}")
        print(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash.hex()}\n")

        # Wait for confirmation
        print("⏳ Waiting for confirmation...")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ Transaction confirmed in block {receipt.blockNumber}")

            # Parse Mint event to get tokenId
            mint_event = self.nfpm.events.Mint().process_receipt(receipt)
            if mint_event:
                token_id = mint_event[0]['args']['tokenId']
                actual_amount0 = mint_event[0]['args']['amount0']
                actual_amount1 = mint_event[0]['args']['amount1']

                print(f"\n🎉 Liquidity position created successfully!")
                print(f"📍 Token ID: {token_id}")
                print(
                    f"💰 Amount 0 used: {actual_amount0 / (10 ** token0_info['decimals']):.6f} {token0_info['symbol']}")
                print(
                    f"💰 Amount 1 used: {actual_amount1 / (10 ** token1_info['decimals']):.6f} {token1_info['symbol']}")
                print(
                    f"\n📊 View position: python query_univ3_position.py {token_id}")
            else:
                print("⚠️  Warning: Could not parse Mint event from receipt")

            return receipt
        else:
            raise Exception("Transaction failed")


def main():
    parser = argparse.ArgumentParser(
        description='Add liquidity to a Uniswap V3 pool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add liquidity to WETH/USDT pool
  python univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300
  
  # Add with custom slippage (1%)
  python univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300 1.0
  
  # Use token addresses directly
  python univ3_add_liq.py 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 0xdAC17F958D2ee523a2206206994597C13D831ec7 3000 -887220 887220 0.1 300

Fee tiers:
  - 500 = 0.05%
  - 3000 = 0.3%
  - 10000 = 1%
        """
    )

    parser.add_argument(
        'token0', help='Token 0 symbol (e.g., WETH) or address')
    parser.add_argument(
        'token1', help='Token 1 symbol (e.g., USDT) or address')
    parser.add_argument('fee', type=int, help='Fee tier (500, 3000, or 10000)')
    parser.add_argument('tick_lower', type=int, help='Lower tick bound')
    parser.add_argument('tick_upper', type=int, help='Upper tick bound')
    parser.add_argument('amount0', type=float,
                        help='Amount of token 0 to deposit')
    parser.add_argument('amount1', type=float,
                        help='Amount of token 1 to deposit')
    parser.add_argument('slippage', type=float, nargs='?', default=0.5,
                        help='Slippage tolerance in percentage (default: 0.5%%)')

    args = parser.parse_args()

    try:
        adder = UniswapV3LiquidityAdder()

        token0_addr = adder.get_token_address(args.token0)
        token1_addr = adder.get_token_address(args.token1)

        adder.add_liquidity(
            token0_addr=token0_addr,
            token1_addr=token1_addr,
            fee=args.fee,
            tick_lower=args.tick_lower,
            tick_upper=args.tick_upper,
            amount0_human=args.amount0,
            amount1_human=args.amount1,
            # Convert percentage to basis points
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
