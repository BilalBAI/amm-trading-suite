"""Main CLI entry point"""

import sys
import os
import json
import argparse
from pathlib import Path

from ..operations.pools import PoolQuery
from ..operations.positions import PositionQuery
from ..operations.liquidity import LiquidityManager
from ..operations.wallet import generate_wallet
from ..operations.swap import SwapManager
from ..operations.balances import BalanceQuery


def get_results_dir():
    """Get results directory, create if needed"""
    # Look for results dir relative to config location
    results_dir = Path.cwd() / "results"
    results_dir.mkdir(exist_ok=True)
    return results_dir


def save_result(filename, data):
    """Save result to JSON file in results directory"""
    results_dir = get_results_dir()
    filepath = results_dir / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return filepath


def cmd_query_pools(args):
    """Query pool information"""
    query = PoolQuery()

    # Refresh cache if requested
    if args.refresh_cache:
        query.refresh_cache(args.address)
        print("Cache refreshed.", file=sys.stderr)

    if args.address:
        result = query.get_pool_info(args.address)
        filename = f"pool_{args.address[:10]}.json"
    else:
        result = query.get_all_configured_pools()
        filename = "univ3_pools.json"

    print(json.dumps(result, indent=2, default=str))
    filepath = save_result(filename, result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_query_position(args):
    """Query position information"""
    query = PositionQuery()
    result = query.get_position(args.token_id)

    print(json.dumps(result, indent=2, default=str))
    filepath = save_result(f"univ3_position_{args.token_id}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_query_positions(args):
    """Query all positions for address"""
    query = PositionQuery()
    address = args.address or query.manager.address
    result = query.get_positions_for_address(address)

    print(json.dumps(result, indent=2, default=str))
    short_addr = address[:10] if address else "unknown"
    filepath = save_result(f"positions_{short_addr}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_query_balances(args):
    """Query token balances for address"""
    query = BalanceQuery()
    result = query.get_all_balances(args.address)

    # Print formatted output
    print(f"Balances for {result['address']}")
    print("-" * 60)
    for bal in result["balances"]:
        if "error" in bal:
            print(f"  {bal['symbol']}: ERROR - {bal['error']}")
        elif bal["balance"] > 0:
            print(f"  {bal['symbol']}: {bal['balance']:.6f}")
        else:
            print(f"  {bal['symbol']}: 0")
    print("-" * 60)

    # Also output JSON
    print("\n" + json.dumps(result, indent=2, default=str))
    short_addr = result["address"][:10]
    filepath = save_result(f"balances_{short_addr}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_lp_quote(args):
    """Get quote for liquidity position - how much of each token is needed"""
    from ..core.connection import Web3Manager
    web3_manager = Web3Manager(require_signer=False)
    manager = LiquidityManager(manager=web3_manager)

    # Determine which amount was provided
    amount0 = getattr(args, 'amount0', None)
    amount1 = getattr(args, 'amount1', None)

    result = manager.calculate_optimal_amounts_range(
        token0=args.token0,
        token1=args.token1,
        fee=args.fee,
        percent_lower=args.range_lower,
        percent_upper=args.range_upper,
        amount0_desired=amount0,
        amount1_desired=amount1,
    )

    # Compact trader-friendly output
    t0 = result['token0']['symbol']
    t1 = result['token1']['symbol']
    range_str = f"{args.range_lower*100:+.1f}% to {args.range_upper*100:+.1f}%"

    print("=" * 60)
    print(f"LP QUOTE: {t0}/{t1} pool ({args.fee/10000:.2f}% fee)")
    print("=" * 60)

    print(f"\n  Range: {range_str} around current price")
    print(f"  Current price: {result['current_price']:.2f} {t1}/{t0}")
    print(f"  Price range: {result['price_lower']:.2f} - {result['price_upper']:.2f} {t1}/{t0}")

    print(f"\n  YOU NEED:")
    print(f"    {result['token0']['amount']:.6f} {t0}")
    print(f"    {result['token1']['amount']:.6f} {t1}")

    # Calculate total value
    total_value = result['token0']['amount'] * result['current_price'] + result['token1']['amount']
    print(f"\n  Total value: ~{total_value:.2f} {t1}")

    if result['position_type'] == 'in_range':
        print(f"\n  Status: IN RANGE (will earn fees immediately)")
    elif result['position_type'] == 'below_range':
        print(f"\n  WARNING: Price is BELOW your range")
        print(f"  Only {t0} needed. Position inactive until price drops.")
    else:
        print(f"\n  WARNING: Price is ABOVE your range")
        print(f"  Only {t1} needed. Position inactive until price rises.")

    print("\n" + "=" * 60)

    # Save result
    result['range_percent'] = {'lower': args.range_lower, 'upper': args.range_upper}
    result['total_value_in_token1'] = total_value
    filepath = save_result(f"lp_quote_{t0}_{t1}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_calculate_amounts(args):
    """Calculate optimal token amounts for a position (legacy command)"""
    manager = LiquidityManager()

    # Use either ticks or percentage range
    if hasattr(args, 'percent_lower'):
        # Percentage-based
        result = manager.calculate_optimal_amounts_range(
            token0=args.token0,
            token1=args.token1,
            fee=args.fee,
            percent_lower=args.percent_lower,
            percent_upper=args.percent_upper,
            amount0_desired=args.amount0 if args.amount0 else None,
            amount1_desired=args.amount1 if args.amount1 else None,
        )
        print(f"Calculating amounts for {args.percent_lower*100:.1f}% to {args.percent_upper*100:.1f}% range")
    else:
        # Tick-based
        result = manager.calculate_optimal_amounts(
            token0=args.token0,
            token1=args.token1,
            fee=args.fee,
            tick_lower=args.tick_lower,
            tick_upper=args.tick_upper,
            amount0_desired=args.amount0 if args.amount0 else None,
            amount1_desired=args.amount1 if args.amount1 else None,
        )
        print(f"Calculating amounts for tick range {args.tick_lower} to {args.tick_upper}")

    print("=" * 70)
    print(f"\nPOSITION DETAILS")
    print(f"  Pool: {result['token0']['symbol']}/{result['token1']['symbol']} ({args.fee/10000:.2f}% fee)")
    print(f"  Current Price: {result['current_price']:.6f} {result['token1']['symbol']}/{result['token0']['symbol']}")
    print(f"  Price Range: {result['price_lower']:.6f} to {result['price_upper']:.6f}")
    print(f"  Position Status: {result['position_type'].replace('_', ' ').title()}")

    print(f"\nOPTIMAL AMOUNTS")
    print(f"  {result['token0']['symbol']}: {result['token0']['amount']:.6f}")
    print(f"  {result['token1']['symbol']}: {result['token1']['amount']:.6f}")

    if result['position_type'] == 'in_range':
        print(f"\nRATIO")
        print(f"  {result['ratio']}")
        print(f"\nTIP: Both tokens are needed since current price is in range")
    elif result['position_type'] == 'below_range':
        print(f"\nWARNING: Current price is BELOW your range")
        print(f"  Only {result['token0']['symbol']} is needed")
        print(f"  Position will be inactive until price drops into range")
    else:  # above_range
        print(f"\nWARNING: Current price is ABOVE your range")
        print(f"  Only {result['token1']['symbol']} is needed")
        print(f"  Position will be inactive until price rises into range")

    print("\n" + "=" * 70)

    # Save to JSON
    print("\n" + json.dumps(result, indent=2, default=str))
    filename = f"calculate_amounts_{result['token0']['symbol']}_{result['token1']['symbol']}.json"
    filepath = save_result(filename, result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_add_liquidity(args):
    """Add liquidity to pool"""
    manager = LiquidityManager()

    print(f"Adding liquidity: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
    print(f"Fee: {args.fee}, Ticks: {args.tick_lower} to {args.tick_upper}")

    result = manager.add_liquidity(
        token0=args.token0,
        token1=args.token1,
        fee=args.fee,
        tick_lower=args.tick_lower,
        tick_upper=args.tick_upper,
        amount0=args.amount0,
        amount1=args.amount1,
        slippage_bps=int(args.slippage * 100),
    )

    print(f"\nSuccess! Token ID: {result['token_id']}")
    print(f"Tx: {result['receipt'].transactionHash.hex()}")

    # Save result
    save_data = {
        "token_id": result["token_id"],
        "tx_hash": result["receipt"].transactionHash.hex(),
        "block": result["receipt"].blockNumber,
        "token0": result["token0"],
        "token1": result["token1"],
        "tick_lower": result["tick_lower"],
        "tick_upper": result["tick_upper"],
    }
    filepath = save_result(f"add_liquidity_{result['token_id']}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_add_liquidity_range(args):
    """Add liquidity using percentage range"""
    manager = LiquidityManager()

    print(f"Adding liquidity: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
    print(f"Fee: {args.fee}, Range: {args.percent_lower*100:.1f}% to {args.percent_upper*100:.1f}%")

    result = manager.add_liquidity_range(
        token0=args.token0,
        token1=args.token1,
        fee=args.fee,
        percent_lower=args.percent_lower,
        percent_upper=args.percent_upper,
        amount0=args.amount0,
        amount1=args.amount1,
        slippage_bps=int(args.slippage * 100),
    )

    print(f"\nSuccess! Token ID: {result['token_id']}")
    print(f"Tx: {result['receipt'].transactionHash.hex()}")

    # Save result
    save_data = {
        "token_id": result["token_id"],
        "tx_hash": result["receipt"].transactionHash.hex(),
        "block": result["receipt"].blockNumber,
        "token0": result["token0"],
        "token1": result["token1"],
        "tick_lower": result["tick_lower"],
        "tick_upper": result["tick_upper"],
        "current_price": result["current_price"],
        "price_lower": result["price_lower"],
        "price_upper": result["price_upper"],
        "percent_lower": result["percent_lower"],
        "percent_upper": result["percent_upper"],
    }
    filepath = save_result(f"add_liquidity_{result['token_id']}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_remove_liquidity(args):
    """Remove liquidity from position"""
    manager = LiquidityManager()

    print(f"Removing {args.percentage}% liquidity from position {args.token_id}")

    result = manager.remove_liquidity(
        token_id=args.token_id,
        percentage=args.percentage,
        collect_fees=args.collect_fees,
        burn=args.burn,
    )

    print(f"\nSuccess!")
    print(f"Decrease tx: {result['decrease_receipt'].transactionHash.hex()}")
    if "collect_receipt" in result:
        print(f"Collect tx: {result['collect_receipt'].transactionHash.hex()}")
    if "burn_receipt" in result:
        print(f"Burn tx: {result['burn_receipt'].transactionHash.hex()}")

    # Save result
    save_data = {
        "token_id": result["token_id"],
        "percentage": args.percentage,
        "decrease_tx": result["decrease_receipt"].transactionHash.hex(),
        "collect_tx": result.get("collect_receipt", {}).transactionHash.hex() if "collect_receipt" in result else None,
        "burn_tx": result.get("burn_receipt", {}).transactionHash.hex() if "burn_receipt" in result else None,
    }
    filepath = save_result(f"remove_liquidity_{args.token_id}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_migrate_liquidity(args):
    """Migrate liquidity to new tick range"""
    manager = LiquidityManager()

    print(f"Migrating {args.percentage}% of position {args.token_id}")
    print(f"New range: {args.tick_lower} to {args.tick_upper}")

    result = manager.migrate_liquidity(
        token_id=args.token_id,
        new_tick_lower=args.tick_lower,
        new_tick_upper=args.tick_upper,
        percentage=args.percentage,
        collect_fees=not args.no_collect_fees,
        burn_old=args.burn_old,
        slippage_bps=int(args.slippage * 100),
    )

    print(f"\nSuccess!")
    print(f"Old position: {result['old_token_id']}")
    print(f"New position: {result['new_token_id']}")

    # Save result
    save_data = {
        "old_token_id": result["old_token_id"],
        "new_token_id": result["new_token_id"],
        "old_range": result["old_range"],
        "new_range": result["new_range"],
        "percentage_migrated": result["percentage_migrated"],
    }
    filepath = save_result(f"migrate_{result['old_token_id']}_to_{result['new_token_id']}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_wallet_generate(args):
    """Generate a new wallet"""
    result = generate_wallet(num_accounts=args.accounts)

    print("=" * 60)
    print("WALLET GENERATED")
    print("=" * 60)
    print(f"\nRecovery Phrase (12 words):")
    print(f"  {result['mnemonic']}\n")
    print("WARNING: Store this phrase securely and NEVER share it!")
    print("=" * 60)

    for acc in result["accounts"]:
        print(f"\nAccount {acc['index'] + 1}:")
        print(f"  Path:        {acc['path']}")
        print(f"  Address:     {acc['address']}")
        print(f"  Private Key: {acc['private_key']}")

    print("\n" + "=" * 60)

    # Save to file
    save_data = {
        "mnemonic": result["mnemonic"],
        "accounts": result["accounts"],
        "warning": "NEVER share your mnemonic or private keys!",
    }
    filepath = save_result("wallet.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)
    print("\nSECURITY: Keep this file safe and never share it!")


def cmd_quote(args):
    """Get swap quote without executing"""
    manager = SwapManager(require_signer=False)

    result = manager.quote(
        token_in=args.token_in,
        token_out=args.token_out,
        pool_name=args.pool,
        amount_in=args.amount,
    )

    # Compact output for traders
    print("=" * 60)
    print(f"QUOTE: {args.amount} {result['token_in']['symbol']} -> {result['token_out']['symbol']}")
    print("=" * 60)
    print(f"\n  Expected output: {result['token_out']['expected_amount']:.6f} {result['token_out']['symbol']}")
    print(f"  Price: {result['price']['rate_formatted']}")
    print(f"  Pool: {result['pool']} ({result['fee_percent']} fee)")
    print(f"\n  Gas estimate: {result['gas']['estimate']} units")
    print(f"  Gas price: {result['gas']['price_gwei']:.2f} gwei")
    print(f"  Gas cost: {result['gas']['cost_eth']:.6f} ETH")

    if result['token_in']['sufficient_balance'] is False:
        print(f"\n  WARNING: Insufficient balance!")
        print(f"  Have: {result['token_in']['balance']:.6f} {result['token_in']['symbol']}")
        print(f"  Need: {args.amount} {result['token_in']['symbol']}")
    elif result['token_in']['sufficient_balance'] is None:
        print(f"\n  Note: Balance check skipped (no wallet configured)")

    print("\n" + "=" * 60)

    # Also output JSON
    print("\n" + json.dumps(result, indent=2, default=str))
    filepath = save_result(f"quote_{result['token_in']['symbol']}_{result['token_out']['symbol']}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_swap(args):
    """Execute token swap"""
    manager = SwapManager()

    dry_run = getattr(args, 'dry_run', False)

    if dry_run:
        print(f"[DRY RUN] Simulating swap: {args.amount} {args.token_in} -> {args.token_out}")
    else:
        print(f"Swapping {args.amount} {args.token_in} -> {args.token_out}")
    print(f"Pool: {args.pool}, Slippage: {args.slippage} bps")
    if args.max_gas_price:
        print(f"Max gas price: {args.max_gas_price} gwei")

    result = manager.swap(
        token_in=args.token_in,
        token_out=args.token_out,
        pool_name=args.pool,
        amount_in=args.amount,
        slippage_bps=args.slippage,
        max_gas_price_gwei=args.max_gas_price,
        deadline_minutes=args.deadline,
        dry_run=dry_run,
    )

    if dry_run:
        # Compact dry-run output
        print("\n" + "=" * 60)
        print("DRY RUN RESULT - No transaction sent")
        print("=" * 60)
        print(f"\n  Would swap: {result['token_in']['amount']} {result['token_in']['symbol']}")
        print(f"  Would receive: ~{result['token_out']['expected_amount']:.6f} {result['token_out']['symbol']}")
        print(f"  Minimum output: {result['token_out']['min_amount']:.6f} {result['token_out']['symbol']} (after {result['slippage_bps']/100}% slippage)")
        print(f"  Price: {result['price']['formatted']}")
        print(f"\n  Gas estimate: {result['gas']['estimate']} units")
        print(f"  Gas cost: ~{result['gas']['cost_eth']:.6f} ETH")

        if not result['token_in'].get('sufficient_balance', True):
            print(f"\n  WARNING: Insufficient balance!")
            print(f"  Have: {result['token_in']['balance']:.6f} {result['token_in']['symbol']}")
            print(f"  Need: {result['token_in']['amount']} {result['token_in']['symbol']}")

        print("\n" + "=" * 60)
        print("\nTo execute this swap, run without --dry-run")
    else:
        print(f"\nSuccess!")
        print(f"Tx: {result['tx_hash']}")
        print(f"Block: {result['block']}")
        print(f"In:  {result['token_in']['amount']} {result['token_in']['symbol']}")
        if result['token_out']['expected_amount']:
            print(f"Out: ~{result['token_out']['expected_amount']:.6f} {result['token_out']['symbol']}")
        print(f"Gas used: {result['gas_used']}")

    # Save result
    if dry_run:
        filepath = save_result(f"swap_dryrun_{result['token_in']['symbol']}_{result['token_out']['symbol']}.json", result)
    else:
        filepath = save_result(f"swap_{result['tx_hash'][:10]}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="amm-trading",
        description="Uniswap V3 liquidity management toolkit",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Query commands
    query_parser = subparsers.add_parser("query", help="Query operations")
    query_sub = query_parser.add_subparsers(dest="query_type")

    # query pools
    pools_parser = query_sub.add_parser("pools", help="Query pool info")
    pools_parser.add_argument("--address", help="Specific pool address")
    pools_parser.add_argument("--refresh-cache", action="store_true", help="Force refresh static pool data cache")
    pools_parser.set_defaults(func=cmd_query_pools)

    # query position
    pos_parser = query_sub.add_parser("position", help="Query position info")
    pos_parser.add_argument("token_id", type=int, help="Position token ID")
    pos_parser.set_defaults(func=cmd_query_position)

    # query positions (for address)
    positions_parser = query_sub.add_parser("positions", help="Query all positions for address")
    positions_parser.add_argument("--address", help="Address to query")
    positions_parser.set_defaults(func=cmd_query_positions)

    # query balances
    balances_parser = query_sub.add_parser("balances", help="Query ETH and token balances")
    balances_parser.add_argument("--address", help="Address to query")
    balances_parser.set_defaults(func=cmd_query_balances)

    # Calculate optimal amounts command
    calc_parser = subparsers.add_parser("calculate", help="Calculate optimal token amounts")
    calc_sub = calc_parser.add_subparsers(dest="calc_type")
    
    # calculate amounts (tick-based)
    calc_ticks_parser = calc_sub.add_parser("amounts", help="Calculate amounts for tick range")
    calc_ticks_parser.add_argument("token0", help="Token0 symbol or address")
    calc_ticks_parser.add_argument("token1", help="Token1 symbol or address")
    calc_ticks_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    calc_ticks_parser.add_argument("tick_lower", type=int, help="Lower tick")
    calc_ticks_parser.add_argument("tick_upper", type=int, help="Upper tick")
    calc_ticks_parser.add_argument("--amount0", type=float, help="Desired amount of token0 (specify this OR amount1)")
    calc_ticks_parser.add_argument("--amount1", type=float, help="Desired amount of token1 (specify this OR amount0)")
    calc_ticks_parser.set_defaults(func=cmd_calculate_amounts)
    
    # calculate amounts (percentage-based)
    calc_range_parser = calc_sub.add_parser("amounts-range", help="Calculate amounts for percentage range")
    calc_range_parser.add_argument("token0", help="Token0 symbol or address")
    calc_range_parser.add_argument("token1", help="Token1 symbol or address")
    calc_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    calc_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05)")
    calc_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05)")
    calc_range_parser.add_argument("--amount0", type=float, help="Desired amount of token0 (specify this OR amount1)")
    calc_range_parser.add_argument("--amount1", type=float, help="Desired amount of token1 (specify this OR amount0)")
    calc_range_parser.set_defaults(func=cmd_calculate_amounts)

    # Add liquidity command
    add_parser = subparsers.add_parser("add", help="Add liquidity")
    add_parser.add_argument("token0", help="Token0 symbol or address")
    add_parser.add_argument("token1", help="Token1 symbol or address")
    add_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    add_parser.add_argument("tick_lower", type=int, help="Lower tick")
    add_parser.add_argument("tick_upper", type=int, help="Upper tick")
    add_parser.add_argument("amount0", type=float, help="Amount of token0")
    add_parser.add_argument("amount1", type=float, help="Amount of token1")
    add_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage %")
    add_parser.set_defaults(func=cmd_add_liquidity)

    # Add liquidity with percentage range command
    add_range_parser = subparsers.add_parser("add-range", help="Add liquidity using percentage range")
    add_range_parser.add_argument("token0", help="Token0 symbol or address")
    add_range_parser.add_argument("token1", help="Token1 symbol or address")
    add_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    add_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05 for -5%%)")
    add_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05 for +5%%)")
    add_range_parser.add_argument("amount0", type=float, help="Amount of token0")
    add_range_parser.add_argument("amount1", type=float, help="Amount of token1")
    add_range_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage %")
    add_range_parser.set_defaults(func=cmd_add_liquidity_range)

    # Remove liquidity command
    remove_parser = subparsers.add_parser("remove", help="Remove liquidity")
    remove_parser.add_argument("token_id", type=int, help="Position token ID")
    remove_parser.add_argument("percentage", type=float, help="Percentage to remove")
    remove_parser.add_argument("--collect-fees", action="store_true", help="Collect fees")
    remove_parser.add_argument("--burn", action="store_true", help="Burn position NFT")
    remove_parser.set_defaults(func=cmd_remove_liquidity)

    # Migrate liquidity command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate liquidity")
    migrate_parser.add_argument("token_id", type=int, help="Position token ID")
    migrate_parser.add_argument("tick_lower", type=int, help="New lower tick")
    migrate_parser.add_argument("tick_upper", type=int, help="New upper tick")
    migrate_parser.add_argument("--percentage", type=float, default=100, help="Percentage to migrate")
    migrate_parser.add_argument("--no-collect-fees", action="store_true", help="Skip fee collection")
    migrate_parser.add_argument("--burn-old", action="store_true", help="Burn old position")
    migrate_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage %")
    migrate_parser.set_defaults(func=cmd_migrate_liquidity)

    # Wallet command
    wallet_parser = subparsers.add_parser("wallet", help="Wallet operations")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_type")

    wallet_gen_parser = wallet_sub.add_parser("generate", help="Generate new wallet")
    wallet_gen_parser.add_argument("--accounts", type=int, default=3, help="Number of accounts to derive")
    wallet_gen_parser.set_defaults(func=cmd_wallet_generate)

    # Quote command for SWAPS (check price without executing)
    quote_parser = subparsers.add_parser("quote", help="Get SWAP quote - check price before trading")
    quote_parser.add_argument("token_in", help="Token to send (symbol like ETH, WETH, USDT or address)")
    quote_parser.add_argument("token_out", help="Token to receive (symbol or address)")
    quote_parser.add_argument("pool", help="Pool name (e.g., WETH_USDT_30)")
    quote_parser.add_argument("amount", type=float, help="Amount of token_in to quote")
    quote_parser.set_defaults(func=cmd_quote)

    # LP Quote command for LIQUIDITY (calculate token amounts needed)
    lp_quote_parser = subparsers.add_parser("lp-quote", help="Get LP quote - calculate tokens needed for liquidity position")
    lp_quote_parser.add_argument("token0", help="First token (e.g., WETH)")
    lp_quote_parser.add_argument("token1", help="Second token (e.g., USDT)")
    lp_quote_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    lp_quote_parser.add_argument("range_lower", type=float, help="Lower bound as decimal (e.g., -0.05 for -5%%)")
    lp_quote_parser.add_argument("range_upper", type=float, help="Upper bound as decimal (e.g., 0.05 for +5%%)")
    lp_quote_parser.add_argument("--amount0", type=float, help="Amount of token0 you have")
    lp_quote_parser.add_argument("--amount1", type=float, help="Amount of token1 you have")
    lp_quote_parser.set_defaults(func=cmd_lp_quote)

    # Swap command
    swap_parser = subparsers.add_parser("swap", help="Swap tokens")
    swap_parser.add_argument("token_in", help="Token to send (symbol like ETH, WETH, USDT or address)")
    swap_parser.add_argument("token_out", help="Token to receive (symbol or address)")
    swap_parser.add_argument("pool", help="Pool name (e.g., WETH_USDT_30)")
    swap_parser.add_argument("amount", type=float, help="Amount of token_in to swap")
    swap_parser.add_argument("--slippage", type=int, default=50, help="Slippage in basis points (default: 50 = 0.5%%)")
    swap_parser.add_argument("--max-gas-price", type=float, help="Maximum gas price in gwei")
    swap_parser.add_argument("--deadline", type=int, default=30, help="Transaction deadline in minutes (default: 30)")
    swap_parser.add_argument("--dry-run", action="store_true", help="Simulate swap without executing")
    swap_parser.set_defaults(func=cmd_swap)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "query" and not args.query_type:
        query_parser.print_help()
        sys.exit(1)

    if args.command == "wallet" and not args.wallet_type:
        wallet_parser.print_help()
        sys.exit(1)

    if args.command == "calculate" and not args.calc_type:
        calc_parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
