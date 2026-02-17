"""Main CLI entry point"""

import sys
import os
import json
import argparse
from pathlib import Path

from ..protocols.uniswap_v3 import PoolQuery, PositionQuery, LiquidityManager, SwapManager
from ..protocols.uniswap_v4 import (
    PoolQuery as V4PoolQuery,
    PositionQuery as V4PositionQuery,
    LiquidityManager as V4LiquidityManager,
    SwapManager as V4SwapManager,
)
from ..core.wallet import generate_wallet
from ..core.balances import BalanceQuery
from ..core.connection import Web3Manager
from ..contracts.weth import WETH


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


def cmd_wrap(args):
    """Wrap ETH to WETH"""
    manager = Web3Manager(require_signer=True)
    weth = WETH(manager)

    print(f"Wrapping {args.amount} ETH to WETH")

    # Show balances before
    balances_before = weth.get_balances()
    print(f"\nBefore:")
    print(f"  ETH:  {balances_before['eth']['balance']:.6f}")
    print(f"  WETH: {balances_before['weth']['balance']:.6f}")

    receipt = weth.deposit(args.amount)

    # Show balances after
    balances_after = weth.get_balances()
    print(f"\nAfter:")
    print(f"  ETH:  {balances_after['eth']['balance']:.6f}")
    print(f"  WETH: {balances_after['weth']['balance']:.6f}")

    print(f"\nSuccess!")
    print(f"Tx: {receipt.transactionHash.hex()}")
    print(f"Gas used: {receipt.gasUsed}")

    # Save result
    save_data = {
        "action": "wrap",
        "amount": args.amount,
        "tx_hash": receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "balances_before": balances_before,
        "balances_after": balances_after,
    }
    filepath = save_result(f"wrap_{receipt.transactionHash.hex()[:10]}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_unwrap(args):
    """Unwrap WETH to ETH"""
    manager = Web3Manager(require_signer=True)
    weth = WETH(manager)

    print(f"Unwrapping {args.amount} WETH to ETH")

    # Show balances before
    balances_before = weth.get_balances()
    print(f"\nBefore:")
    print(f"  ETH:  {balances_before['eth']['balance']:.6f}")
    print(f"  WETH: {balances_before['weth']['balance']:.6f}")

    receipt = weth.withdraw(args.amount)

    # Show balances after
    balances_after = weth.get_balances()
    print(f"\nAfter:")
    print(f"  ETH:  {balances_after['eth']['balance']:.6f}")
    print(f"  WETH: {balances_after['weth']['balance']:.6f}")

    print(f"\nSuccess!")
    print(f"Tx: {receipt.transactionHash.hex()}")
    print(f"Gas used: {receipt.gasUsed}")

    # Save result
    save_data = {
        "action": "unwrap",
        "amount": args.amount,
        "tx_hash": receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "balances_before": balances_before,
        "balances_after": balances_after,
    }
    filepath = save_result(f"unwrap_{receipt.transactionHash.hex()[:10]}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_swap(args):
    """Execute token swap"""
    manager = SwapManager()

    dry_run = getattr(args, 'dry_run', False)

    if dry_run:
        print(f"[DRY RUN] Simulating swap: {args.amount} {args.token_in} -> {args.token_out}")
    else:
        print(f"Swapping {args.amount} {args.token_in} -> {args.token_out}")
    print(f"Pool: {args.pool}, Slippage: {args.slippage} bps")
    result = manager.swap(
        token_in=args.token_in,
        token_out=args.token_out,
        pool_name=args.pool,
        amount_in=args.amount,
        slippage_bps=args.slippage,
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


# ══════════════════════════════════════════════════════════════════════════════
# UNISWAP V4 COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_v4_query_pools(args):
    """Query V4 pool information"""
    query = V4PoolQuery()

    if args.refresh_cache:
        query.refresh_cache(args.name if hasattr(args, 'name') else None)
        print("Cache refreshed.", file=sys.stderr)

    if hasattr(args, 'name') and args.name:
        result = query.get_pool_info(args.name)
        filename = f"univ4_pool_{args.name}.json"
    else:
        result = query.get_all_configured_pools()
        filename = "univ4_pools.json"

    print(json.dumps(result, indent=2, default=str))
    filepath = save_result(filename, result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_v4_query_position(args):
    """Query V4 position information"""
    query = V4PositionQuery()
    result = query.get_position(args.token_id)

    print(json.dumps(result, indent=2, default=str))
    filepath = save_result(f"univ4_position_{args.token_id}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_v4_query_positions(args):
    """Query all V4 positions for address"""
    query = V4PositionQuery()
    address = args.address or query.manager.address
    result = query.get_positions_for_address(address)

    print(json.dumps(result, indent=2, default=str))
    short_addr = address[:10] if address else "unknown"
    filepath = save_result(f"univ4_positions_{short_addr}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_v4_quote(args):
    """Get V4 swap quote without executing"""
    manager = V4SwapManager(require_signer=False)

    result = manager.quote(
        token_in=args.token_in,
        token_out=args.token_out,
        pool_name=args.pool,
        amount_in=args.amount,
    )

    # Compact output for traders
    print("=" * 60)
    print(f"V4 QUOTE: {args.amount} {result['token_in']['symbol']} -> {result['token_out']['symbol']}")
    print("=" * 60)
    print(f"\n  Expected output: {result['token_out']['expected_amount']:.6f} {result['token_out']['symbol']}")
    print(f"  Price: {result['price']['rate_formatted']}")
    print(f"  Pool: {result['pool']} ({result['fee_percent']} fee)")

    if result['token_in'].get('is_native_eth') or result['token_out'].get('is_native_eth'):
        print(f"\n  Native ETH: Yes (no WETH wrapping needed)")

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

    print("\n" + json.dumps(result, indent=2, default=str))
    filepath = save_result(f"univ4_quote_{result['token_in']['symbol']}_{result['token_out']['symbol']}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_v4_swap(args):
    """Execute V4 token swap"""
    manager = V4SwapManager()

    dry_run = getattr(args, 'dry_run', False)

    if dry_run:
        print(f"[DRY RUN] Simulating V4 swap: {args.amount} {args.token_in} -> {args.token_out}")
    else:
        print(f"V4 Swapping {args.amount} {args.token_in} -> {args.token_out}")
    print(f"Pool: {args.pool}, Slippage: {args.slippage} bps")

    result = manager.swap(
        token_in=args.token_in,
        token_out=args.token_out,
        pool_name=args.pool,
        amount_in=args.amount,
        slippage_bps=args.slippage,
        deadline_minutes=args.deadline,
        dry_run=dry_run,
    )

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN RESULT - No transaction sent")
        print("=" * 60)
        print(f"\n  Would swap: {result['token_in']['amount']} {result['token_in']['symbol']}")
        print(f"  Would receive: ~{result['token_out']['expected_amount']:.6f} {result['token_out']['symbol']}")
        print(f"  Minimum output: {result['token_out']['min_amount']:.6f} {result['token_out']['symbol']}")
        print(f"  Price: {result['price']['formatted']}")

        if result['token_in'].get('is_native_eth'):
            print(f"\n  Using native ETH (no WETH wrapping)")

        print(f"\n  Gas estimate: {result['gas']['estimate']} units")
        print(f"  Gas cost: ~{result['gas']['cost_eth']:.6f} ETH")

        if not result['token_in'].get('sufficient_balance', True):
            print(f"\n  WARNING: Insufficient balance!")

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

    if dry_run:
        filepath = save_result(f"univ4_swap_dryrun_{result['token_in']['symbol']}_{result['token_out']['symbol']}.json", result)
    else:
        filepath = save_result(f"univ4_swap_{result['tx_hash'][:10]}.json", result)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def cmd_v4_add_liquidity(args):
    """Add liquidity to V4 pool"""
    manager = V4LiquidityManager()

    print(f"V4 Adding liquidity: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
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
    if result.get('uses_native_eth'):
        print(f"Used native ETH (no WETH wrapping)")

    save_data = {
        "token_id": result["token_id"],
        "tx_hash": result["receipt"].transactionHash.hex(),
        "block": result["receipt"].blockNumber,
        "token0": result["token0"],
        "token1": result["token1"],
        "tick_lower": result["tick_lower"],
        "tick_upper": result["tick_upper"],
        "uses_native_eth": result.get("uses_native_eth", False),
    }
    filepath = save_result(f"univ4_add_liquidity_{result['token_id']}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_v4_add_liquidity_range(args):
    """Add V4 liquidity using percentage range"""
    manager = V4LiquidityManager()

    print(f"V4 Adding liquidity: {args.amount0} {args.token0} + {args.amount1} {args.token1}")
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
        "uses_native_eth": result.get("uses_native_eth", False),
    }
    filepath = save_result(f"univ4_add_liquidity_{result['token_id']}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_v4_remove_liquidity(args):
    """Remove liquidity from V4 position"""
    manager = V4LiquidityManager()

    print(f"Removing {args.percentage}% liquidity from V4 position {args.token_id}")

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

    save_data = {
        "token_id": result["token_id"],
        "percentage": args.percentage,
        "decrease_tx": result["decrease_receipt"].transactionHash.hex(),
        "collect_tx": result.get("collect_receipt", {}).transactionHash.hex() if "collect_receipt" in result else None,
        "burn_tx": result.get("burn_receipt", {}).transactionHash.hex() if "burn_receipt" in result else None,
    }
    filepath = save_result(f"univ4_remove_liquidity_{args.token_id}.json", save_data)
    print(f"Saved to {filepath}", file=sys.stderr)


def cmd_v4_calculate_amounts(args):
    """Calculate optimal token amounts for V4 position"""
    from ..core.connection import Web3Manager
    web3_manager = Web3Manager(require_signer=False)
    manager = V4LiquidityManager(manager=web3_manager)

    if hasattr(args, 'percent_lower'):
        result = manager.calculate_optimal_amounts_range(
            token0=args.token0,
            token1=args.token1,
            fee=args.fee,
            percent_lower=args.percent_lower,
            percent_upper=args.percent_upper,
            amount0_desired=args.amount0 if args.amount0 else None,
            amount1_desired=args.amount1 if args.amount1 else None,
        )
        print(f"V4 calculating amounts for {args.percent_lower*100:.1f}% to {args.percent_upper*100:.1f}% range")
    else:
        result = manager.calculate_optimal_amounts(
            token0=args.token0,
            token1=args.token1,
            fee=args.fee,
            tick_lower=args.tick_lower,
            tick_upper=args.tick_upper,
            amount0_desired=args.amount0 if args.amount0 else None,
            amount1_desired=args.amount1 if args.amount1 else None,
        )
        print(f"V4 calculating amounts for tick range {args.tick_lower} to {args.tick_upper}")

    print("=" * 70)
    print(f"\nV4 POSITION DETAILS")
    print(f"  Pool: {result['token0']['symbol']}/{result['token1']['symbol']} ({args.fee/10000:.2f}% fee)")
    print(f"  Current Price: {result['current_price']:.6f}")
    print(f"  Price Range: {result['price_lower']:.6f} to {result['price_upper']:.6f}")
    print(f"  Position Status: {result['position_type'].replace('_', ' ').title()}")

    if result['token0'].get('is_native_eth') or result['token1'].get('is_native_eth'):
        print(f"\n  Native ETH: Yes (no WETH wrapping needed)")

    print(f"\nOPTIMAL AMOUNTS")
    print(f"  {result['token0']['symbol']}: {result['token0']['amount']:.6f}")
    print(f"  {result['token1']['symbol']}: {result['token1']['amount']:.6f}")

    print("\n" + "=" * 70)

    # Remove pool_key from result for JSON serialization (it's a dataclass)
    result_json = {k: v for k, v in result.items() if k != 'pool_key'}
    print("\n" + json.dumps(result_json, indent=2, default=str))
    filename = f"univ4_calculate_{result['token0']['symbol']}_{result['token1']['symbol']}.json"
    filepath = save_result(filename, result_json)
    print(f"\nSaved to {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="amm-trading",
        description="AMM Trading Toolkit - Interact with Uniswap V3 & V4 on Ethereum",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""commands overview:
  query       Query ETH/token balances
  wrap/unwrap Convert between ETH and WETH
  wallet      Generate new wallets
  univ3       Uniswap V3 operations (query, quote, add/remove liquidity, swap)
  univ4       Uniswap V4 operations (native ETH support, no WETH wrapping)

examples:
  amm-trading query balances                                          # Check wallet balances
  amm-trading univ3 quote WETH USDT WETH_USDT_30 0.1                 # Get swap quote
  amm-trading univ3 lp-quote WETH USDT 3000 -0.05 0.05 --amount0 1   # LP position quote
  amm-trading univ3 swap WETH USDT WETH_USDT_30 0.1 --dry-run        # Simulate a swap
  amm-trading univ3 add-range WETH USDT 3000 -0.05 0.05 0.1 300      # Add liquidity (-5% to +5%)
  amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0                    # V4 swap with native ETH
  amm-trading univ4 query pools                                       # List V4 pools

configuration:
  RPC_URL      Set in .env file
  wallet       Set PUBLIC_KEY and PRIVATE_KEY in wallet.env
  tokens       config/tokens.json
  gas          config/gas.json
  pools        config/uniswap_v3/pools.json, config/uniswap_v4/pools.json
""",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # ── Top-level: query (shared/general) ──────────────────────────────
    query_parser = subparsers.add_parser("query", help="General query operations")
    query_sub = query_parser.add_subparsers(dest="query_type")

    # query balances
    balances_parser = query_sub.add_parser("balances", help="Query ETH and token balances")
    balances_parser.add_argument("--address", help="Address to query")
    balances_parser.set_defaults(func=cmd_query_balances)

    # ── Top-level: wrap / unwrap ───────────────────────────────────────
    wrap_parser = subparsers.add_parser("wrap", help="Wrap ETH to WETH")
    wrap_parser.add_argument("amount", type=float, help="Amount of ETH to wrap")
    wrap_parser.set_defaults(func=cmd_wrap)

    unwrap_parser = subparsers.add_parser("unwrap", help="Unwrap WETH to ETH")
    unwrap_parser.add_argument("amount", type=float, help="Amount of WETH to unwrap")
    unwrap_parser.set_defaults(func=cmd_unwrap)

    # ── Top-level: wallet ──────────────────────────────────────────────
    wallet_parser = subparsers.add_parser("wallet", help="Wallet operations")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_type")

    wallet_gen_parser = wallet_sub.add_parser("generate", help="Generate new wallet")
    wallet_gen_parser.add_argument("--accounts", type=int, default=3, help="Number of accounts to derive")
    wallet_gen_parser.set_defaults(func=cmd_wallet_generate)

    # ── Top-level: univ3 (Uniswap V3 operations) ──────────────────────
    univ3_parser = subparsers.add_parser(
        "univ3",
        help="Uniswap V3 operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Uniswap V3 operations - query pools/positions, add/remove liquidity, swap tokens",
        epilog="""subcommands:
  query       Query pools, positions
  calculate   Calculate optimal token amounts for LP
  quote       Get swap quote (read-only, no wallet needed)
  lp-quote    Get LP position quote (read-only, no wallet needed)
  add         Add liquidity using tick range
  add-range   Add liquidity using percentage range (e.g., -5% to +5%)
  remove      Remove liquidity from a position
  migrate     Migrate liquidity to a new tick range
  swap        Execute a token swap

examples:
  amm-trading univ3 query pools
  amm-trading univ3 quote WETH USDT WETH_USDT_30 0.1
  amm-trading univ3 lp-quote WETH USDT 3000 -0.05 0.05 --amount0 0.1
  amm-trading univ3 swap WETH USDT WETH_USDT_30 0.1 --dry-run
  amm-trading univ3 add-range WETH USDT 3000 -0.05 0.05 0.1 300
""",
    )
    univ3_sub = univ3_parser.add_subparsers(dest="univ3_command")

    # ── univ3 query ────────────────────────────────────────────────────
    univ3_query_parser = univ3_sub.add_parser("query", help="Query Uniswap V3 data")
    univ3_query_sub = univ3_query_parser.add_subparsers(dest="univ3_query_type")

    # univ3 query pools
    pools_parser = univ3_query_sub.add_parser("pools", help="Query pool info")
    pools_parser.add_argument("--address", help="Specific pool address")
    pools_parser.add_argument("--refresh-cache", action="store_true", help="Force refresh static pool data cache")
    pools_parser.set_defaults(func=cmd_query_pools)

    # univ3 query position
    pos_parser = univ3_query_sub.add_parser("position", help="Query position by NFT token ID")
    pos_parser.add_argument("token_id", type=int, help="Position NFT token ID")
    pos_parser.set_defaults(func=cmd_query_position)

    # univ3 query positions
    positions_parser = univ3_query_sub.add_parser("positions", help="Query all positions for address")
    positions_parser.add_argument("--address", help="Address to query (default: wallet.env)")
    positions_parser.set_defaults(func=cmd_query_positions)

    # ── univ3 calculate ────────────────────────────────────────────────
    univ3_calc_parser = univ3_sub.add_parser("calculate", help="Calculate optimal token amounts")
    univ3_calc_sub = univ3_calc_parser.add_subparsers(dest="calc_type")

    # univ3 calculate amounts (tick-based)
    calc_ticks_parser = univ3_calc_sub.add_parser("amounts", help="Calculate amounts for tick range")
    calc_ticks_parser.add_argument("token0", help="Token0 symbol or address")
    calc_ticks_parser.add_argument("token1", help="Token1 symbol or address")
    calc_ticks_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    calc_ticks_parser.add_argument("tick_lower", type=int, help="Lower tick")
    calc_ticks_parser.add_argument("tick_upper", type=int, help="Upper tick")
    calc_ticks_parser.add_argument("--amount0", type=float, help="Desired amount of token0 (specify this OR amount1)")
    calc_ticks_parser.add_argument("--amount1", type=float, help="Desired amount of token1 (specify this OR amount0)")
    calc_ticks_parser.set_defaults(func=cmd_calculate_amounts)

    # univ3 calculate amounts-range (percentage-based)
    calc_range_parser = univ3_calc_sub.add_parser("amounts-range", help="Calculate amounts for percentage range")
    calc_range_parser.add_argument("token0", help="Token0 symbol or address")
    calc_range_parser.add_argument("token1", help="Token1 symbol or address")
    calc_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    calc_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05)")
    calc_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05)")
    calc_range_parser.add_argument("--amount0", type=float, help="Desired amount of token0 (specify this OR amount1)")
    calc_range_parser.add_argument("--amount1", type=float, help="Desired amount of token1 (specify this OR amount0)")
    calc_range_parser.set_defaults(func=cmd_calculate_amounts)

    # ── univ3 add ──────────────────────────────────────────────────────
    add_parser = univ3_sub.add_parser("add", help="Add liquidity")
    add_parser.add_argument("token0", help="Token0 symbol or address")
    add_parser.add_argument("token1", help="Token1 symbol or address")
    add_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    add_parser.add_argument("tick_lower", type=int, help="Lower tick")
    add_parser.add_argument("tick_upper", type=int, help="Upper tick")
    add_parser.add_argument("amount0", type=float, help="Amount of token0")
    add_parser.add_argument("amount1", type=float, help="Amount of token1")
    add_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage tolerance in percent")
    add_parser.set_defaults(func=cmd_add_liquidity)

    # ── univ3 add-range ────────────────────────────────────────────────
    add_range_parser = univ3_sub.add_parser("add-range", help="Add liquidity using percentage range")
    add_range_parser.add_argument("token0", help="Token0 symbol or address")
    add_range_parser.add_argument("token1", help="Token1 symbol or address")
    add_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    add_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05 for -5%%)")
    add_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05 for +5%%)")
    add_range_parser.add_argument("amount0", type=float, help="Amount of token0")
    add_range_parser.add_argument("amount1", type=float, help="Amount of token1")
    add_range_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage tolerance in percent")
    add_range_parser.set_defaults(func=cmd_add_liquidity_range)

    # ── univ3 remove ───────────────────────────────────────────────────
    remove_parser = univ3_sub.add_parser("remove", help="Remove liquidity")
    remove_parser.add_argument("token_id", type=int, help="Position token ID")
    remove_parser.add_argument("percentage", type=float, help="Percentage to remove")
    remove_parser.add_argument("--collect-fees", action="store_true", help="Collect fees")
    remove_parser.add_argument("--burn", action="store_true", help="Burn position NFT")
    remove_parser.set_defaults(func=cmd_remove_liquidity)

    # ── univ3 migrate ──────────────────────────────────────────────────
    migrate_parser = univ3_sub.add_parser("migrate", help="Migrate liquidity")
    migrate_parser.add_argument("token_id", type=int, help="Position token ID")
    migrate_parser.add_argument("tick_lower", type=int, help="New lower tick")
    migrate_parser.add_argument("tick_upper", type=int, help="New upper tick")
    migrate_parser.add_argument("--percentage", type=float, default=100, help="Percentage to migrate")
    migrate_parser.add_argument("--no-collect-fees", action="store_true", help="Skip fee collection")
    migrate_parser.add_argument("--burn-old", action="store_true", help="Burn old position")
    migrate_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage tolerance in percent")
    migrate_parser.set_defaults(func=cmd_migrate_liquidity)

    # ── univ3 swap ─────────────────────────────────────────────────────
    swap_parser = univ3_sub.add_parser("swap", help="Swap tokens")
    swap_parser.add_argument("token_in", help="Token to send (symbol like ETH, WETH, USDT or address)")
    swap_parser.add_argument("token_out", help="Token to receive (symbol or address)")
    swap_parser.add_argument("pool", help="Pool name (e.g., WETH_USDT_30)")
    swap_parser.add_argument("amount", type=float, help="Amount of token_in to swap")
    swap_parser.add_argument("--slippage", type=int, default=50, help="Slippage in basis points (default: 50 = 0.5%%)")
    swap_parser.add_argument("--deadline", type=int, default=30, help="Transaction deadline in minutes (default: 30)")
    swap_parser.add_argument("--dry-run", action="store_true", help="Simulate swap without executing")
    swap_parser.set_defaults(func=cmd_swap)

    # ── univ3 quote ────────────────────────────────────────────────────
    quote_parser = univ3_sub.add_parser("quote", help="Get swap quote - check price before trading")
    quote_parser.add_argument("token_in", help="Token to send (symbol like ETH, WETH, USDT or address)")
    quote_parser.add_argument("token_out", help="Token to receive (symbol or address)")
    quote_parser.add_argument("pool", help="Pool name (e.g., WETH_USDT_30)")
    quote_parser.add_argument("amount", type=float, help="Amount of token_in to quote")
    quote_parser.set_defaults(func=cmd_quote)

    # ── univ3 lp-quote ─────────────────────────────────────────────────
    lp_quote_parser = univ3_sub.add_parser("lp-quote", help="Get LP quote - calculate tokens needed for liquidity position")
    lp_quote_parser.add_argument("token0", help="First token (e.g., WETH)")
    lp_quote_parser.add_argument("token1", help="Second token (e.g., USDT)")
    lp_quote_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    lp_quote_parser.add_argument("range_lower", type=float, help="Lower bound as decimal (e.g., -0.05 for -5%%)")
    lp_quote_parser.add_argument("range_upper", type=float, help="Upper bound as decimal (e.g., 0.05 for +5%%)")
    lp_quote_parser.add_argument("--amount0", type=float, help="Amount of token0 you have")
    lp_quote_parser.add_argument("--amount1", type=float, help="Amount of token1 you have")
    lp_quote_parser.set_defaults(func=cmd_lp_quote)

    # ══════════════════════════════════════════════════════════════════
    # UNISWAP V4 COMMANDS
    # ══════════════════════════════════════════════════════════════════

    univ4_parser = subparsers.add_parser(
        "univ4",
        help="Uniswap V4 operations (native ETH support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Uniswap V4 operations - native ETH support, no WETH wrapping needed",
        epilog="""subcommands:
  query       Query pools, positions
  calculate   Calculate optimal token amounts for LP
  quote       Get swap quote (read-only, no wallet needed)
  add         Add liquidity using tick range (supports native ETH)
  add-range   Add liquidity using percentage range (supports native ETH)
  remove      Remove liquidity from a position
  swap        Execute a token swap (supports native ETH)

examples:
  amm-trading univ4 query pools
  amm-trading univ4 quote ETH USDC ETH_USDC_30 1.0
  amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0 --dry-run
  amm-trading univ4 add-range ETH USDC 3000 -0.05 0.05 1.0 2000
""",
    )
    univ4_sub = univ4_parser.add_subparsers(dest="univ4_command")

    # ── univ4 query ────────────────────────────────────────────────────
    univ4_query_parser = univ4_sub.add_parser("query", help="Query Uniswap V4 data")
    univ4_query_sub = univ4_query_parser.add_subparsers(dest="univ4_query_type")

    # univ4 query pools
    v4_pools_parser = univ4_query_sub.add_parser("pools", help="Query V4 pool info")
    v4_pools_parser.add_argument("--name", help="Specific pool name (e.g., ETH_USDC_30)")
    v4_pools_parser.add_argument("--refresh-cache", action="store_true", help="Force refresh cache")
    v4_pools_parser.set_defaults(func=cmd_v4_query_pools)

    # univ4 query position
    v4_pos_parser = univ4_query_sub.add_parser("position", help="Query position by NFT token ID")
    v4_pos_parser.add_argument("token_id", type=int, help="Position NFT token ID")
    v4_pos_parser.set_defaults(func=cmd_v4_query_position)

    # univ4 query positions
    v4_positions_parser = univ4_query_sub.add_parser("positions", help="Query all V4 positions for address")
    v4_positions_parser.add_argument("--address", help="Address to query (default: wallet.env)")
    v4_positions_parser.set_defaults(func=cmd_v4_query_positions)

    # ── univ4 calculate ────────────────────────────────────────────────
    univ4_calc_parser = univ4_sub.add_parser("calculate", help="Calculate optimal token amounts")
    univ4_calc_sub = univ4_calc_parser.add_subparsers(dest="v4_calc_type")

    # univ4 calculate amounts (tick-based)
    v4_calc_ticks_parser = univ4_calc_sub.add_parser("amounts", help="Calculate amounts for tick range")
    v4_calc_ticks_parser.add_argument("token0", help="Token0 symbol or address (use ETH for native)")
    v4_calc_ticks_parser.add_argument("token1", help="Token1 symbol or address")
    v4_calc_ticks_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    v4_calc_ticks_parser.add_argument("tick_lower", type=int, help="Lower tick")
    v4_calc_ticks_parser.add_argument("tick_upper", type=int, help="Upper tick")
    v4_calc_ticks_parser.add_argument("--amount0", type=float, help="Desired amount of token0")
    v4_calc_ticks_parser.add_argument("--amount1", type=float, help="Desired amount of token1")
    v4_calc_ticks_parser.set_defaults(func=cmd_v4_calculate_amounts)

    # univ4 calculate amounts-range (percentage-based)
    v4_calc_range_parser = univ4_calc_sub.add_parser("amounts-range", help="Calculate amounts for percentage range")
    v4_calc_range_parser.add_argument("token0", help="Token0 symbol or address (use ETH for native)")
    v4_calc_range_parser.add_argument("token1", help="Token1 symbol or address")
    v4_calc_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    v4_calc_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05)")
    v4_calc_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05)")
    v4_calc_range_parser.add_argument("--amount0", type=float, help="Desired amount of token0")
    v4_calc_range_parser.add_argument("--amount1", type=float, help="Desired amount of token1")
    v4_calc_range_parser.set_defaults(func=cmd_v4_calculate_amounts)

    # ── univ4 add ──────────────────────────────────────────────────────
    v4_add_parser = univ4_sub.add_parser("add", help="Add liquidity (supports native ETH)")
    v4_add_parser.add_argument("token0", help="Token0 symbol (use ETH for native)")
    v4_add_parser.add_argument("token1", help="Token1 symbol or address")
    v4_add_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    v4_add_parser.add_argument("tick_lower", type=int, help="Lower tick")
    v4_add_parser.add_argument("tick_upper", type=int, help="Upper tick")
    v4_add_parser.add_argument("amount0", type=float, help="Amount of token0")
    v4_add_parser.add_argument("amount1", type=float, help="Amount of token1")
    v4_add_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage tolerance in percent")
    v4_add_parser.set_defaults(func=cmd_v4_add_liquidity)

    # ── univ4 add-range ────────────────────────────────────────────────
    v4_add_range_parser = univ4_sub.add_parser("add-range", help="Add liquidity using percentage range")
    v4_add_range_parser.add_argument("token0", help="Token0 symbol (use ETH for native)")
    v4_add_range_parser.add_argument("token1", help="Token1 symbol or address")
    v4_add_range_parser.add_argument("fee", type=int, help="Fee tier (500, 3000, 10000)")
    v4_add_range_parser.add_argument("percent_lower", type=float, help="Lower percentage (e.g., -0.05)")
    v4_add_range_parser.add_argument("percent_upper", type=float, help="Upper percentage (e.g., 0.05)")
    v4_add_range_parser.add_argument("amount0", type=float, help="Amount of token0")
    v4_add_range_parser.add_argument("amount1", type=float, help="Amount of token1")
    v4_add_range_parser.add_argument("--slippage", type=float, default=0.5, help="Slippage tolerance in percent")
    v4_add_range_parser.set_defaults(func=cmd_v4_add_liquidity_range)

    # ── univ4 remove ───────────────────────────────────────────────────
    v4_remove_parser = univ4_sub.add_parser("remove", help="Remove liquidity")
    v4_remove_parser.add_argument("token_id", type=int, help="Position token ID")
    v4_remove_parser.add_argument("percentage", type=float, help="Percentage to remove")
    v4_remove_parser.add_argument("--collect-fees", action="store_true", help="Collect fees")
    v4_remove_parser.add_argument("--burn", action="store_true", help="Burn position NFT")
    v4_remove_parser.set_defaults(func=cmd_v4_remove_liquidity)

    # ── univ4 swap ─────────────────────────────────────────────────────
    v4_swap_parser = univ4_sub.add_parser("swap", help="Swap tokens (supports native ETH)")
    v4_swap_parser.add_argument("token_in", help="Token to send (use ETH for native)")
    v4_swap_parser.add_argument("token_out", help="Token to receive")
    v4_swap_parser.add_argument("pool", help="Pool name (e.g., ETH_USDC_30)")
    v4_swap_parser.add_argument("amount", type=float, help="Amount of token_in to swap")
    v4_swap_parser.add_argument("--slippage", type=int, default=50, help="Slippage in basis points")
    v4_swap_parser.add_argument("--deadline", type=int, default=30, help="Deadline in minutes")
    v4_swap_parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    v4_swap_parser.set_defaults(func=cmd_v4_swap)

    # ── univ4 quote ────────────────────────────────────────────────────
    v4_quote_parser = univ4_sub.add_parser("quote", help="Get swap quote")
    v4_quote_parser.add_argument("token_in", help="Token to send (use ETH for native)")
    v4_quote_parser.add_argument("token_out", help="Token to receive")
    v4_quote_parser.add_argument("pool", help="Pool name (e.g., ETH_USDC_30)")
    v4_quote_parser.add_argument("amount", type=float, help="Amount of token_in to quote")
    v4_quote_parser.set_defaults(func=cmd_v4_quote)

    # ── Parse and dispatch ─────────────────────────────────────────────
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

    if args.command == "univ3":
        if not args.univ3_command:
            univ3_parser.print_help()
            sys.exit(1)
        if args.univ3_command == "query" and not args.univ3_query_type:
            univ3_query_parser.print_help()
            sys.exit(1)
        if args.univ3_command == "calculate" and not args.calc_type:
            univ3_calc_parser.print_help()
            sys.exit(1)

    if args.command == "univ4":
        if not args.univ4_command:
            univ4_parser.print_help()
            sys.exit(1)
        if args.univ4_command == "query" and not args.univ4_query_type:
            univ4_query_parser.print_help()
            sys.exit(1)
        if args.univ4_command == "calculate" and not getattr(args, 'v4_calc_type', None):
            univ4_calc_parser.print_help()
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
