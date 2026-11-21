I’ll inspect the repository structure and existing files, then add a polished README based on the project itself.I found a competition-focused Python repository with a primary implementation in `marketmaker.py`, a local validation harness, and several experimental/result artifacts. I’ll write the README to explain the project and usage without overstating results.# Akuna

A Python implementation of a quantitative market-making bot for the 2026 Akuna Capital Virtual Quant Trading Challenge.

The bot prices binary options, estimates market parameters, manages inventory and collateral, and produces two-sided quotes for the exchange.

## Underlyings

The simulated market tracks:

- **FED** — Fed funds rate
- **AJR** — AjarAI valuation
- **THR** — Theriodic valuation

Binary options settle at $1 if their condition is true at expiry and $0 otherwise.

## Features

- Exact and estimated binary-option pricing
- Online estimation of drifts, rate sensitivities, and covariance
- Delta, gamma, and volatility-risk adjustments
- Inventory-aware bid and offer skew
- Per-counterparty fill-rate and adverse-selection tracking
- Expected-loss-based quote sizing
- Cash and collateral management
- Settlement handling for multiple expiry conventions
- Defensive handling for malformed or unexpected market state
- Fill-or-kill (FOK) order evaluation
- Validation against Monte Carlo simulations and toxic-flow scenarios

## Repository Structure

| File | Purpose |
|---|---|
| `marketmaker.py` | Primary market-making implementation |
| `test_marketmaker.py` | Pricer, estimator, solvency, continuity, and robustness tests |
| `hackerrank.py` | Alternative or near-final implementation version |
| `test_*hackerrank.py` | Experimental implementation and test variants |
| `Context.md` | Competition context and requirements |
| `Strategy_ideas.md` | Notes and strategy concepts |
| `*.md` | Recorded experiment results and parameter variants |

## Requirements

- Python 3.10 or newer
- Standard library only

## Running the Validation Harness

From the repository root:

```bash
python3 test_marketmaker.py
```

The harness checks:

1. Theoretical prices against Monte Carlo simulation
2. Continuity and Greek behavior
3. Parameter-estimation accuracy
4. Solvency under toxic trading flow
5. Both supported settlement conventions
6. Robustness against malformed inputs and edge cases

## Core API

### `MarketMaker`

The main entry point is `MarketMaker`:

```python
from marketmaker import MarketMaker

maker = MarketMaker(
    underlying_initial_state,
    option_initial_state,
    cash_balance,
)
```

Important methods include:

- `warm_up(market_history)` — estimate parameters from historical observations
- `on_step_advance(...)` — update market and option state
- `price_option(option)` — return the estimated theoretical value
- `quote(option, counterparty_id)` — generate a bid and offer
- `respond_to_fok(option, fok_order)` — accept or reject an FOK order
- `on_trade(...)` — update positions, collateral, and counterparty data
- `portfolio_delta()` — report current factor exposure
- `portfolio_gamma()` — report portfolio convexity
- `portfolio_vega()` — report covariance sensitivity

## Example

```python
from marketmaker import (
    MarketMaker,
    Underlying,
    FED_FUNDS_RATE_UNDERLYING_ID,
    AJARAI_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
)

underlyings = [
    Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 3.0),
    Underlying("AJR", AJARAI_UNDERLYING_ID, 500.0),
    Underlying("THR", THERIODIC_UNDERLYING_ID, 420.0),
]

maker = MarketMaker(underlyings, [], cash_balance=100.0)
```

## Strategy Overview

The implementation combines:

- Markov-chain pricing for the Fed funds rate
- Log-normal company value distributions
- Closed-form and quadrature-based payoff probabilities
- Dynamic inventory skew
- Convexity and volatility uncertainty spreads
- Collateral-aware quote sizing
- Conservative cash buffers
- Online model re-estimation

Quotes are adjusted to avoid oversizing positions that increase portfolio risk while preserving size on trades that reduce inventory.

## Notes

- Prices are represented as probabilities from `0.0` to `1.0`.
- Quantities are option contracts.
- Maximum-loss collateral is charged at trade time.
- This repository was developed for a market-making simulation and is not intended for live trading.

## License

No license is currently specified for this repository.
