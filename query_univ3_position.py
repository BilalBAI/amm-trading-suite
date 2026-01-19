#!/usr/bin/env python3
"""
Query detailed information about a Uniswap V3 position by token ID
Usage: python query_univ3_position.py <token_id>
"""

import sys
import json
import math
from web3 import Web3
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load shared config and ABIs


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


class UniswapV3PositionQuery:
    def __init__(self):
        rpc_url = os.getenv('RPC_URL')
        if not rpc_url:
            raise ValueError("RPC_URL not found in .env file")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum node")

        self.nfpm_address = Web3.to_checksum_address(
            CONFIG['contracts']['uniswap_v3_nfpm'])
        self.factory_address = Web3.to_checksum_address(
            CONFIG['contracts']['uniswap_v3_factory'])

        self.nfpm = self.w3.eth.contract(
            address=self.nfpm_address,
            abi=ABIS['uniswap_v3_nfpm']
        )
        self.factory = self.w3.eth.contract(
            address=self.factory_address,
            abi=ABIS['uniswap_v3_factory']
        )

        self.token_cache = {}
        self.pool_cache = {}

    def _get_token_info(self, address):
        """Get token decimals and symbol (cached)"""
        address = Web3.to_checksum_address(address)
        if address not in self.token_cache:
            contract = self.w3.eth.contract(
                address, abi=ABIS['erc20'])
            self.token_cache[address] = {
                'decimals': contract.functions.decimals().call(),
                'symbol': contract.functions.symbol().call()
            }
        return self.token_cache[address]

    def _get_pool_address(self, token0, token1, fee):
        """Get pool address (cached)"""
        token0 = Web3.to_checksum_address(token0)
        token1 = Web3.to_checksum_address(token1)
        key = (token0, token1, fee)
        if key not in self.pool_cache:
            self.pool_cache[key] = self.factory.functions.getPool(
                token0, token1, fee).call()
        return self.pool_cache[key]

    @staticmethod
    def tick_to_price(tick, dec0, dec1):
        """Convert tick to human-readable price"""
        return (1.0001 ** tick) * (10 ** dec0) / (10 ** dec1)

    @staticmethod
    def tick_to_sqrt_price(tick):
        """Convert tick to sqrt price"""
        return 1.0001 ** (tick / 2)

    def _get_amounts_from_liquidity(self, L, sqrt_price_x96, tick, tickL, tickU, dec0, dec1):
        """Calculate token amounts from liquidity"""
        sqrt_pl = self.tick_to_sqrt_price(tickL)
        sqrt_pu = self.tick_to_sqrt_price(tickU)
        sqrt_pc = sqrt_pl if tick < tickL else (
            sqrt_pu if tick > tickU else sqrt_price_x96 / Q96)

        if tick < tickL:
            return L * (1/sqrt_pl - 1/sqrt_pu) / (10**dec0), 0
        elif tick > tickU:
            return 0, L * (sqrt_pu - sqrt_pl) / (10**dec1)
        else:
            return (L * (1/sqrt_pc - 1/sqrt_pu) / (10**dec0),
                    L * (sqrt_pc - sqrt_pl) / (10**dec1))

    def _calculate_fee_growth_inside(self, pool, tick_lower, tick_upper, current_tick):
        """Calculate fee growth inside the tick range"""
        try:
            fee_growth_global_0 = pool.functions.feeGrowthGlobal0X128().call()
            fee_growth_global_1 = pool.functions.feeGrowthGlobal1X128().call()

            tick_lower_data = pool.functions.ticks(tick_lower).call()
            fee_growth_outside_0_lower = tick_lower_data[2]
            fee_growth_outside_1_lower = tick_lower_data[3]

            tick_upper_data = pool.functions.ticks(tick_upper).call()
            fee_growth_outside_0_upper = tick_upper_data[2]
            fee_growth_outside_1_upper = tick_upper_data[3]

            if current_tick >= tick_lower:
                fee_growth_below_0 = fee_growth_outside_0_lower
                fee_growth_below_1 = fee_growth_outside_1_lower
            else:
                fee_growth_below_0 = fee_growth_global_0 - fee_growth_outside_0_lower
                fee_growth_below_1 = fee_growth_global_1 - fee_growth_outside_1_lower

            if current_tick < tick_upper:
                fee_growth_above_0 = fee_growth_outside_0_upper
                fee_growth_above_1 = fee_growth_outside_1_upper
            else:
                fee_growth_above_0 = fee_growth_global_0 - fee_growth_outside_0_upper
                fee_growth_above_1 = fee_growth_global_1 - fee_growth_outside_1_upper

            fee_growth_inside_0 = fee_growth_global_0 - \
                fee_growth_below_0 - fee_growth_above_0
            fee_growth_inside_1 = fee_growth_global_1 - \
                fee_growth_below_1 - fee_growth_above_1

            return fee_growth_inside_0, fee_growth_inside_1
        except Exception:
            return None, None

    def _calculate_accumulated_fees(self, pool, liquidity, tick_lower, tick_upper, current_tick,
                                    fee_growth_inside_0_last, fee_growth_inside_1_last,
                                    tokens_owed_0, tokens_owed_1, dec0, dec1):
        """Calculate total accumulated fees"""
        try:
            fee_growth_inside_0, fee_growth_inside_1 = self._calculate_fee_growth_inside(
                pool, tick_lower, tick_upper, current_tick)

            if fee_growth_inside_0 is None or fee_growth_inside_1 is None:
                return None, None

            Q128 = 2 ** 128
            fee_growth_delta_0 = fee_growth_inside_0 - fee_growth_inside_0_last
            fee_growth_delta_1 = fee_growth_inside_1 - fee_growth_inside_1_last

            fees_from_growth_0 = (liquidity * fee_growth_delta_0) // Q128
            fees_from_growth_1 = (liquidity * fee_growth_delta_1) // Q128

            total_fees_0 = fees_from_growth_0 + tokens_owed_0
            total_fees_1 = fees_from_growth_1 + tokens_owed_1

            return (total_fees_0 / (10**dec0), total_fees_1 / (10**dec1))
        except Exception:
            return None, None

    def _get_historical_price(self, pool_addr, block_num, dec0, dec1):
        """Get pool price at historical block"""
        if not pool_addr:
            return None
        try:
            pool = self.w3.eth.contract(
                pool_addr, abi=ABIS['uniswap_v3_pool'])
            slot0 = pool.functions.slot0().call(block_identifier=block_num)
            if not slot0 or not slot0[0]:
                return None
            sqrt_price_x96 = slot0[0]
            price = (sqrt_price_x96 / Q96) ** 2
            return price * (10**dec0) / (10**dec1)
        except Exception:
            return None

    def _get_all_deposits(self, token_id, dec0, dec1, pool_addr=None):
        """Get all Mint and IncreaseLiquidity events for a position"""
        deposits = []
        token_topic = "0x" + hex(token_id)[2:].zfill(64)
        cb = self.w3.eth.block_number
        from_block = max(12369621, cb - 10000000)  # NFPM deploy block

        # Query Mint events (initial creation)
        try:
            mint_sig = self.w3.keccak(
                text="Mint(uint256,uint256,uint256)").hex()
            mint_contract = self.w3.eth.contract(
                self.nfpm_address, abi=[ABIS['mintEvent']]
            )
            mint_logs = self.w3.eth.get_logs({
                "fromBlock": from_block, "toBlock": "latest",
                "address": self.nfpm_address,
                "topics": [mint_sig, token_topic]
            })

            for log in mint_logs:
                try:
                    decoded = mint_contract.events.Mint().processLog(log)
                    if decoded['args']['tokenId'] == token_id:
                        a0 = decoded['args']['amount0'] / (10**dec0)
                        a1 = decoded['args']['amount1'] / (10**dec1)
                        block = log['blockNumber']
                        tx = log['transactionHash'].hex()
                        try:
                            ts = datetime.fromtimestamp(
                                self.w3.eth.get_block(block)['timestamp'])
                        except:
                            ts = None
                        price = None
                        if pool_addr:
                            price = self._get_historical_price(
                                pool_addr, block, dec0, dec1)
                        deposits.append({
                            'amount0': float(a0),
                            'amount1': float(a1),
                            'block': block,
                            'transaction': tx,
                            'price_at_deposit': float(price) if price else None,
                            'timestamp': ts.isoformat() if ts else None,
                            'timestamp_formatted': ts.strftime("%Y-%m-%d %H:%M:%S") if ts else f"Block {block}"
                        })
                except:
                    continue
        except:
            pass

        # Query IncreaseLiquidity events (subsequent additions)
        try:
            inc_sig = self.w3.keccak(
                text="IncreaseLiquidity(uint256,uint128,uint256,uint256)").hex()
            inc_contract = self.w3.eth.contract(
                self.nfpm_address, abi=[ABIS['increaseLiquidityEvent']]
            )
            inc_logs = self.w3.eth.get_logs({
                "fromBlock": from_block, "toBlock": "latest",
                "address": self.nfpm_address,
                "topics": [inc_sig, token_topic]
            })

            for log in inc_logs:
                try:
                    decoded = inc_contract.events.IncreaseLiquidity().processLog(log)
                    if decoded['args']['tokenId'] == token_id:
                        a0 = decoded['args']['amount0'] / (10**dec0)
                        a1 = decoded['args']['amount1'] / (10**dec1)
                        block = log['blockNumber']
                        tx = log['transactionHash'].hex()
                        try:
                            ts = datetime.fromtimestamp(
                                self.w3.eth.get_block(block)['timestamp'])
                        except:
                            ts = None
                        price = None
                        if pool_addr:
                            price = self._get_historical_price(
                                pool_addr, block, dec0, dec1)
                        deposits.append({
                            'amount0': float(a0),
                            'amount1': float(a1),
                            'block': block,
                            'transaction': tx,
                            'price_at_deposit': float(price) if price else None,
                            'timestamp': ts.isoformat() if ts else None,
                            'timestamp_formatted': ts.strftime("%Y-%m-%d %H:%M:%S") if ts else f"Block {block}"
                        })
                except:
                    continue
        except:
            pass

        deposits.sort(key=lambda x: x['block'])
        return deposits

    def _calculate_impermanent_loss(self, deposits, current_price, current_position_value, current_amount0, current_amount1):
        """Calculate impermanent loss"""
        if not deposits or current_price is None:
            return None

        if current_position_value is None:
            if current_amount0 is not None and current_amount1 is not None:
                current_position_value = current_amount0 * current_price + current_amount1
            else:
                return None

        total_initial_amount0 = sum(dep['amount0'] for dep in deposits)
        total_initial_amount1 = sum(dep['amount1'] for dep in deposits)

        hold_value = total_initial_amount0 * current_price + total_initial_amount1

        if hold_value == 0:
            return None

        il = ((current_position_value - hold_value) / hold_value) * 100
        return float(il)

    def query_position(self, token_id):
        """Query all details for a specific position"""
        try:
            token_id = int(token_id)
        except ValueError:
            raise ValueError(f"Invalid token ID: {token_id}")

        query_time = datetime.now()

        # Get position data from NFT contract
        try:
            pos = self.nfpm.functions.positions(token_id).call()
        except Exception as e:
            raise ValueError(
                f"Position {token_id} not found or error querying: {e}")

        nonce, operator, t0, t1, fee, tickL, tickU, L, fee_growth_0_last, fee_growth_1_last, owed0, owed1 = pos

        t0_info = self._get_token_info(t0)
        t1_info = self._get_token_info(t1)
        dec0, dec1 = t0_info['decimals'], t1_info['decimals']
        sym0, sym1 = t0_info['symbol'], t1_info['symbol']

        pool_addr = self._get_pool_address(t0, t1, fee)

        result = {
            "token_id": token_id,
            "token0": {
                "address": t0,
                "symbol": sym0,
                "decimals": dec0
            },
            "token1": {
                "address": t1,
                "symbol": sym1,
                "decimals": dec1
            },
            "pair": f"{sym0}/{sym1}",
            "fee_tier": fee,
            "fee_tier_percent": f"{fee/10000}%",
            "tick_lower": tickL,
            "tick_upper": tickU,
            "liquidity": str(L),
            "nonce": str(nonce),
            "operator": operator,
            "pool_address": pool_addr if pool_addr and pool_addr != "0x" + "0" * 40 else None,
            "fee_growth_inside_0_last": str(fee_growth_0_last),
            "fee_growth_inside_1_last": str(fee_growth_1_last),
            "tokens_owed_0": str(owed0),
            "tokens_owed_1": str(owed1),
            "tokens_owed_0_human": f"{owed0/(10**dec0):.6f}",
            "tokens_owed_1_human": f"{owed1/(10**dec1):.6f}"
        }

        if not pool_addr or pool_addr == "0x" + "0" * 40:
            result["status"] = "Pool not found"
            result["query_time"] = query_time.isoformat()
            return result

        try:
            pool = self.w3.eth.contract(
                pool_addr, abi=ABIS['uniswap_v3_pool'])
            slot0 = pool.functions.slot0().call()
            current_tick, sqrt_price_x96 = slot0[1], slot0[0]

            price = ((sqrt_price_x96 / Q96) ** 2) * \
                (10**dec0) / (10**dec1)

            status = ("ACTIVE (earning fees)" if tickL <= current_tick <= tickU else
                      "OUT OF RANGE (below)" if current_tick < tickL else "OUT OF RANGE (above)")

            a0, a1 = self._get_amounts_from_liquidity(
                L, sqrt_price_x96, current_tick, tickL, tickU, dec0, dec1)
            value = a0 * price + a1

            price_lower = self.tick_to_price(tickL, dec0, dec1)
            price_upper = self.tick_to_price(tickU, dec0, dec1)

            # Calculate accumulated fees
            acc_fees_0, acc_fees_1 = self._calculate_accumulated_fees(
                pool, int(L), tickL, tickU, current_tick,
                fee_growth_0_last, fee_growth_1_last,
                owed0, owed1, dec0, dec1
            )

            # Get deposits
            deposits = self._get_all_deposits(token_id, dec0, dec1, pool_addr)

            # Calculate IL
            il = self._calculate_impermanent_loss(
                deposits, price, value, a0, a1)

            result.update({
                "current_price": float(price),
                "current_price_formatted": f"{price:.6f} {sym1}/{sym0}",
                "current_tick": current_tick,
                "sqrt_price_x96": str(sqrt_price_x96),
                "status": status,
                "current_amounts": {
                    "amount0": float(a0),
                    "amount1": float(a1),
                    "amount0_formatted": f"{a0:.4f} {sym0}",
                    "amount1_formatted": f"{a1:.4f} {sym1}"
                },
                "current_value": {
                    "value": float(value),
                    "value_formatted": f"{value:.2f} {sym1}"
                },
                "price_range": {
                    "lower": float(price_lower),
                    "upper": float(price_upper),
                    "formatted": f"{price_lower:.2f}-{price_upper:.2f}"
                },
                "fees": {
                    "uncollected": {
                        "token0": float(owed0/(10**dec0)),
                        "token1": float(owed1/(10**dec1)),
                        "formatted": f"{owed0/(10**dec0):.6f} {sym0}, {owed1/(10**dec1):.6f} {sym1}"
                    },
                    "accumulated": {
                        "token0": float(acc_fees_0) if acc_fees_0 else None,
                        "token1": float(acc_fees_1) if acc_fees_1 else None,
                        "formatted": f"{acc_fees_0:.6f} {sym0}, {acc_fees_1:.6f} {sym1}" if acc_fees_0 and acc_fees_1 else "N/A"
                    },
                    "value": float(acc_fees_0 * price + acc_fees_1) if acc_fees_0 and acc_fees_1 and price else None,
                    "value_formatted": f"{acc_fees_0 * price + acc_fees_1:.2f} {sym1}" if acc_fees_0 and acc_fees_1 and price else "N/A"
                },
                "impermanent_loss": {
                    "percentage": float(il) if il else None,
                    "formatted": f"{il:.4f}%" if il else "N/A"
                },
                "deposits": deposits,
                "deposit_count": len(deposits)
            })
        except Exception as e:
            result["pool_error"] = str(e)

        result["query_time"] = query_time.isoformat()
        return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_univ3_position.py <token_id>")
        print("Example: python query_univ3_position.py 1157630")
        sys.exit(1)

    token_id = sys.argv[1]

    try:
        query = UniswapV3PositionQuery()
        result = query.query_position(token_id)

        # Save to file in results folder
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(results_dir, exist_ok=True)
        output_file = os.path.join(
            results_dir, f"univ3_position_{token_id}.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        # Output as formatted JSON to stdout
        print(json.dumps(result, indent=2))
        print(f"\n✓ Saved to {output_file}", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
