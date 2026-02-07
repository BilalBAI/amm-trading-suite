# Uniswap V4 Architecture Guide

This guide explains Uniswap V4's architecture and key differences from V3 for traders and developers.

## Overview

Uniswap V4 represents a significant architectural evolution from V3:

- **Singleton PoolManager**: All pools live in one contract (vs separate contracts per pool in V3)
- **Native ETH Support**: Use ETH directly without wrapping to WETH
- **Hooks System**: Customizable pool behavior via hook contracts
- **Flash Accounting**: Batched token settlements for gas efficiency
- **~99% Cheaper Pool Creation**: Pools are state updates, not contract deployments

## V4 vs V3 Comparison

| Aspect | V3 | V4 |
|--------|----|----|
| Pool Creation | Factory deploys new contract | State update in singleton PoolManager |
| Pool ID | Contract address | PoolKey hash |
| ETH Handling | Must wrap to WETH | Native ETH (ADDRESS_ZERO) |
| Position Manager | Direct function calls | Encoded action commands |
| Fee Collection | Explicit collect() | DECREASE_LIQUIDITY with 0 liquidity |
| Hooks | N/A | Customizable per pool |
| Settlement | Per-operation transfers | Flash accounting (batched) |
| Gas | Higher (contract deployments) | ~99% cheaper pool creation |

## Key Concepts

### PoolKey

In V4, pools are identified by a `PoolKey` struct rather than a contract address:

```python
PoolKey(
    currency0="0x0000...",    # Lower address token (ADDRESS_ZERO for ETH)
    currency1="0xA0b8...",    # Higher address token
    fee=3000,                  # Fee in hundredths of a bip (0.30%)
    tick_spacing=60,           # Tick spacing for the pool
    hooks="0x0000..."          # Hooks contract (zero for no hooks)
)
```

**Important**: `currency0` must always be the lower address. Use `sort_currencies()` or `create_pool_key()` helpers to ensure correct ordering.

### Native ETH

V4 uses `ADDRESS_ZERO` (`0x0000000000000000000000000000000000000000`) to represent native ETH. This eliminates the need for WETH wrapping, saving gas.

```bash
# V3: Must wrap ETH first
amm-trading wrap 1.0
amm-trading univ3 swap WETH USDC WETH_USDC_30 1.0

# V4: Use ETH directly
amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0
```

### Flash Accounting

V4 uses flash accounting where:
1. Operations are batched together
2. Token balances are tracked in memory
3. Actual transfers happen only at the end
4. Net positions are settled once

This reduces gas costs for complex operations.

### Hooks

Hooks are optional contracts that can modify pool behavior:
- Before/after swap logic
- Before/after liquidity changes
- Dynamic fees
- Custom oracles

Most pools use no hooks (`hooks = ADDRESS_ZERO`).

## CLI Commands

### Queries (Read-Only)

```bash
# List all configured V4 pools
amm-trading univ4 query pools

# Query specific pool
amm-trading univ4 query pools --name ETH_USDC_30

# Query position by token ID
amm-trading univ4 query position 12345

# Query all positions for address
amm-trading univ4 query positions
amm-trading univ4 query positions --address 0x...
```

### Swap Quotes

```bash
# Get quote (no transaction)
amm-trading univ4 quote ETH USDC ETH_USDC_30 1.0

# Dry-run swap simulation
amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0 --dry-run
```

### Swaps

```bash
# Swap native ETH for USDC
amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0

# With custom slippage (basis points)
amm-trading univ4 swap ETH USDC ETH_USDC_30 1.0 --slippage 100  # 1% slippage
```

### Liquidity Management

```bash
# Calculate amounts needed for position
amm-trading univ4 calculate amounts-range ETH USDC 3000 -0.05 0.05 --amount0 1.0

# Add liquidity with ticks
amm-trading univ4 add ETH USDC 3000 -1000 1000 1.0 2000.0

# Add liquidity with percentage range
amm-trading univ4 add-range ETH USDC 3000 -0.05 0.05 1.0 2000.0

# Remove liquidity
amm-trading univ4 remove 12345 100 --collect-fees --burn
```

## Configuration

### Pool Configuration

Configure pools in `config/uniswap_v4/pools.json`:

```json
{
    "ETH_USDC_30": {
        "currency0": "0x0000000000000000000000000000000000000000",
        "currency1": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "fee": 3000,
        "tickSpacing": 60,
        "hooks": "0x0000000000000000000000000000000000000000"
    }
}
```

Key points:
- `currency0` should be ADDRESS_ZERO for native ETH pools
- `currency0` must be lower address than `currency1`
- Pool name format: `TOKEN0_TOKEN1_FEE` (fee in hundredths, e.g., 30 = 0.30%)

### Contract Addresses

V4 contracts are located in `amm_trading/protocols/uniswap_v4/addresses.json`. These are the same across most chains:

- **PoolManager**: `0x000000000004444c5dc75cB358380D2e3dE08A90`
- **PositionManager**: `0xbD216513d74C8cf14cf4747E6AaA6420FF64ee9e`
- **StateView**: `0x7fFe42C4a5DEeA5b0fEC41C94C136Cf115597227`
- **Quoter**: `0x52f0E24D1C21c8A0CB1e5a5dD6198556BD86E8203`
- **UniversalRouter**: `0x66a9893cC07D91D95644Aedd05D03f95e1dba8Af`

## What This Means for Traders

### Gas Savings

1. **Native ETH**: No WETH wrapping = ~46,000 gas saved per swap
2. **Singleton**: Fewer contract calls = lower base costs
3. **Flash Accounting**: Complex operations are cheaper

### Same Math as V3

V4 uses the same concentrated liquidity math as V3:
- Same tick system
- Same price ranges
- Same impermanent loss considerations
- Same fee tiers (100, 500, 3000, 10000)

### Position NFTs

Like V3, positions are represented as NFTs. The Position Manager mints NFTs for each position, which you can:
- Transfer to other addresses
- Use as collateral in DeFi
- Query for status and earnings

## Programmatic Usage

```python
from amm_trading.protocols.uniswap_v4 import (
    UniswapV4Config,
    PoolKey,
    LiquidityManager,
    SwapManager,
    PositionQuery,
    PoolQuery,
    ADDRESS_ZERO,
    create_pool_key,
)

# Create a pool key for ETH/USDC
pool_key = create_pool_key(
    token_a=ADDRESS_ZERO,  # Native ETH
    token_b="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
    fee=3000,
)

# Get a swap quote
swap_manager = SwapManager(require_signer=False)
quote = swap_manager.quote(
    token_in="ETH",
    token_out="USDC",
    amount_in=1.0,
    pool_name="ETH_USDC_30",
)
print(f"Expected output: {quote['token_out']['expected_amount']} USDC")

# Query position
position_query = PositionQuery()
position = position_query.get_position(token_id=12345)
print(f"Status: {position['status']}")
```

## Resources

- [Uniswap V4 Docs](https://docs.uniswap.org/contracts/v4/overview)
- [V4 vs V3 Comparison](https://docs.uniswap.org/contracts/v4/concepts/v4-vs-v3)
- [Position Manager Guide](https://docs.uniswap.org/contracts/v4/guides/position-manager)
- [V4 Deployments](https://docs.uniswap.org/contracts/v4/deployments)
