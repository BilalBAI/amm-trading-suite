# Archived Scripts

These are the original standalone scripts that have been refactored into the `amm_trading` package.

## Archived Files

| Old Script | New Location |
|------------|--------------|
| `exe_univ3_add_liq.py` | `amm_trading.operations.LiquidityManager.add_liquidity()` |
| `exe_univ3_remove_liq.py` | `amm_trading.operations.LiquidityManager.remove_liquidity()` |
| `exe_univ3_migrate_liq.py` | `amm_trading.operations.LiquidityManager.migrate_liquidity()` |
| `query_univ3_position.py` | `amm_trading.operations.PositionQuery.get_position()` |
| `query_univ3_pools.py` | `amm_trading.operations.PoolQuery` |
| `query_positions.py` | `amm_trading.operations.PositionQuery.get_positions_for_address()` |
| `generate_wallet.py` | `amm_trading.operations.generate_wallet()` |

## Migration Guide

### Old way (standalone scripts)
```bash
python exe_univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300
python query_univ3_position.py 1157630
python generate_wallet.py
```

### New way (package CLI)
```bash
amm-trading add WETH USDT 3000 -887220 887220 0.1 300
amm-trading query position 1157630
amm-trading wallet generate
```

### New way (Python API)
```python
from amm_trading.operations import LiquidityManager, PositionQuery

# Add liquidity
manager = LiquidityManager()
result = manager.add_liquidity("WETH", "USDT", 3000, -887220, 887220, 0.1, 300)

# Query position
query = PositionQuery()
position = query.get_position(1157630)
```

## Why archived?

These scripts contained significant code duplication (~40%) and lacked:
- Proper package structure
- Reusable components
- Type hints
- Testability

The new `amm_trading` package addresses these issues with:
- Centralized configuration (`Config` singleton)
- Shared Web3 connection management (`Web3Manager`)
- Reusable contract wrappers (`ERC20`, `NFPM`, `Pool`)
- Clean separation of concerns
- Both CLI and programmatic API
