"""Validation harness for the market maker.

Three checks, in increasing order of what they prove:

1. `check_pricer`      -- prices from `price_option_from_parameters` against a Monte Carlo of
                          the real `MarketParameters.advance_step`. This is ground truth.
2. `check_estimator`   -- parameters recovered from a warm-up history, priced against the
                          truth, so estimation error shows up in price units.
3. `check_solvency`    -- a full session against maximally toxic counterparties, asserting
                          cash never goes negative and that our own ledger matches the
                          grader's collateral rule exactly.

Run: python3 test_marketmaker.py
"""

import math
import random
import sys

from marketmaker import (
    AJARAI_NAME,
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_NAME,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_NAME,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketMaker,
    MarketParameters,
    OptionLeg,
    OrderType,
    Underlying,
    fitted_from_market_parameters,
    price_binary_option,
)

INITIAL_VALUES: dict[int, float] = {
    FED_FUNDS_RATE_UNDERLYING_ID: 3.0,
    AJARAI_UNDERLYING_ID: 500.0,
    THERIODIC_UNDERLYING_ID: 420.0,
}


def make_parameters(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.01, 0.02),
        ajarai_idio_std_dev=rng.uniform(0.02, 0.06),
        ajarai_rate_beta=rng.uniform(-0.45, -0.10),
        ajarai_sector_beta=rng.uniform(0.5, 1.4),
        rate_down_probability=rng.uniform(0.15, 0.35),
        rate_reversion_strength=rng.uniform(0.0, 0.25),
        rate_up_probability=rng.uniform(0.15, 0.35),
        sector_std_dev=rng.uniform(0.02, 0.05),
        theriodic_drift=rng.uniform(-0.01, 0.02),
        theriodic_idio_std_dev=rng.uniform(0.02, 0.06),
        theriodic_rate_beta=rng.uniform(-0.45, -0.10),
        theriodic_sector_beta=rng.uniform(-0.4, 1.4),
        rate_target=rng.choice([1.5, 2.0, 2.5, 3.0]),
    )


def underlying_state(values: dict[int, float]) -> list[Underlying]:
    return [
        Underlying(name=FED_FUNDS_RATE_NAME, underlying_id=FED_FUNDS_RATE_UNDERLYING_ID, value=values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying(name=AJARAI_NAME, underlying_id=AJARAI_UNDERLYING_ID, value=values[AJARAI_UNDERLYING_ID]),
        Underlying(name=THERIODIC_NAME, underlying_id=THERIODIC_UNDERLYING_ID, value=values[THERIODIC_UNDERLYING_ID]),
    ]


def make_option_suite(values: dict[int, float], next_id: int) -> tuple[list[BinaryOption], int]:
    """One option of each structural family, struck near the money."""
    rate: float = values[FED_FUNDS_RATE_UNDERLYING_ID]
    ajarai: float = values[AJARAI_UNDERLYING_ID]
    theriodic: float = values[THERIODIC_UNDERLYING_ID]
    specifications: list[tuple[tuple[OptionLeg, ...], float, int]] = [
        ((OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), rate + 0.25, 4),
        ((OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), rate - 0.25, 6),
        ((OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), ajarai * 1.10, 5),
        ((OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), ajarai * 0.90, 3),
        ((OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),), theriodic * 1.05, 7),
        ((OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)), 0.0, 4),
        ((OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, 1.0)), (ajarai + theriodic) * 1.04, 5),
        ((OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -0.5)), ajarai * 0.7, 3),
        ((OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 100.0), OptionLeg(AJARAI_UNDERLYING_ID, 1.0)), ajarai + 100.0 * rate, 4),
        ((OptionLeg(AJARAI_UNDERLYING_ID, -1.0),), -ajarai * 1.10, 5),
    ]
    options: list[BinaryOption] = []
    for legs, strike, steps in specifications:
        options.append(BinaryOption(legs=legs, option_id=next_id, steps_until_expiry=steps, strike=strike))
        next_id += 1
    return options, next_id


def simulate_history(parameters: MarketParameters, values: dict[int, float], num_days: int) -> tuple[MarketHistory, dict[int, float]]:
    paths: dict[int, list[float]] = {key: [value] for key, value in values.items()}
    current: dict[int, float] = dict(values)
    for _ in range(num_days):
        current = parameters.advance_step(current)
        for key, value in current.items():
            paths[key].append(value)
    return MarketHistory(values_by_underlying_id={key: tuple(path) for key, path in paths.items()}), current


# ---------------------------------------------------------------------------------------------
# 1. Pricer against the real simulator
# ---------------------------------------------------------------------------------------------


def check_pricer(num_paths: int = 20000, seed: int = 7) -> bool:
    rng = random.Random(seed)
    random.seed(seed)
    parameters: MarketParameters = make_parameters(rng)
    options, _ = make_option_suite(INITIAL_VALUES, 1)
    maker = MarketMaker(underlying_state(INITIAL_VALUES), options, 1000.0)

    horizon: int = max(option.steps_until_expiry for option in options)
    hits: dict[int, int] = {option.option_id: 0 for option in options}
    for _ in range(num_paths):
        current: dict[int, float] = dict(INITIAL_VALUES)
        snapshots: list[dict[int, float]] = [dict(current)]
        for _ in range(horizon):
            current = parameters.advance_step(current)
            snapshots.append(dict(current))
        for option in options:
            hits[option.option_id] += int(option.expiry_valuation(snapshots[option.steps_until_expiry]))

    print("\n[1] pricer vs simulator Monte Carlo")
    print(f"    {'option':<44} {'theo':>8} {'empirical':>10} {'z':>7}")
    passed: bool = True
    for option in options:
        theoretical: float = maker.price_option_from_parameters(parameters, option)
        empirical: float = hits[option.option_id] / num_paths
        standard_error: float = math.sqrt(max(empirical * (1.0 - empirical), 1e-6) / num_paths)
        z_score: float = (empirical - theoretical) / standard_error
        flag: str = "" if abs(z_score) < 4.0 else "   <-- FAIL"
        passed = passed and abs(z_score) < 4.0
        print(f"    {str(option):<44} {theoretical:>8.4f} {empirical:>10.4f} {z_score:>7.2f}{flag}")
    return passed


# ---------------------------------------------------------------------------------------------
# 2. Estimator quality, measured in price units
# ---------------------------------------------------------------------------------------------


def check_estimator(num_trials: int = 12, warm_up_days: int = 400, seed: int = 11) -> bool:
    rng = random.Random(seed)
    random.seed(seed)
    worst: float = 0.0
    total: float = 0.0
    count: int = 0

    for _ in range(num_trials):
        parameters: MarketParameters = make_parameters(rng)
        history, final_values = simulate_history(parameters, INITIAL_VALUES, warm_up_days)
        options, _ = make_option_suite(final_values, 1)
        maker = MarketMaker(underlying_state(final_values), options, 1000.0)
        maker.warm_up(history)

        truth = fitted_from_market_parameters(parameters)
        for option in options:
            estimated: float = maker.price_option(option)
            actual: float = price_binary_option(truth, option, final_values)
            error: float = abs(estimated - actual)
            worst = max(worst, error)
            total += error
            count += 1

    mean_error: float = total / count
    print("\n[2] estimator (warm-up history -> price error vs truth)")
    print(f"    mean abs error {mean_error:.4f}   worst {worst:.4f}   ({count} prices)")
    return mean_error < 0.030 and worst < 0.20


# ---------------------------------------------------------------------------------------------
# 3. Solvency under maximally toxic flow
# ---------------------------------------------------------------------------------------------


class Exchange:
    """Replicates the grader's cash rule: every trade costs its own maximum loss up front,
    and nothing comes back until the option expires."""

    def __init__(self, parameters: MarketParameters, values: dict[int, float], cash: float, rng: random.Random) -> None:
        self.parameters = parameters
        self.values = dict(values)
        self.cash = cash
        self.rng = rng
        self.quantity_by_option_id: dict[int, int] = {}
        self.gross_long_by_option_id: dict[int, int] = {}
        self.gross_short_by_option_id: dict[int, int] = {}
        self.contract_by_option_id: dict[int, BinaryOption] = {}
        self.min_cash = cash
        self.trade_count = 0
        self.max_ledger_gap = 0.0

    def _apply(self, option: BinaryOption, price: float, quantity: int) -> None:
        self.cash -= quantity * price if quantity > 0 else -quantity * (1.0 - price)
        self.quantity_by_option_id[option.option_id] = self.quantity_by_option_id.get(option.option_id, 0) + quantity
        # Gross, not net: collateral was charged per trade, so each leg is credited separately.
        if quantity > 0:
            self.gross_long_by_option_id[option.option_id] = self.gross_long_by_option_id.get(option.option_id, 0) + quantity
        else:
            self.gross_short_by_option_id[option.option_id] = self.gross_short_by_option_id.get(option.option_id, 0) - quantity
        self.contract_by_option_id[option.option_id] = option
        self.trade_count += 1
        self.min_cash = min(self.min_cash, self.cash)

    def settle(self, option_ids: set[int], values: dict[int, float]) -> None:
        # An option sitting at steps_until_expiry == 0 settles on *that* day's values, which are
        # the ones live while it was still quotable -- not the next day's.
        for option_id in option_ids:
            self.quantity_by_option_id.pop(option_id, None)
            long_quantity: int = self.gross_long_by_option_id.pop(option_id, 0)
            short_quantity: int = self.gross_short_by_option_id.pop(option_id, 0)
            option = self.contract_by_option_id.pop(option_id, None)
            if option is None or (long_quantity == 0 and short_quantity == 0):
                continue
            payoff: float = option.expiry_valuation(values)
            self.cash += long_quantity * payoff + short_quantity * (1.0 - payoff)

    def run(self, maker: MarketMaker, num_days: int, toxicity: float, verbose: bool = False) -> tuple[bool, float]:
        """`toxicity` in [0, 1]: the fraction of counterparties that know the true value and
        only ever trade when our quote is wrong. 1.0 is the worst case the grader can throw."""
        truth = fitted_from_market_parameters(self.parameters)
        options, next_id = make_option_suite(self.values, 1)
        maker.on_step_advance(underlying_state(self.values), options)

        for _ in range(num_days):
            settlement_values: dict[int, float] = dict(self.values)
            self.values = self.parameters.advance_step(self.values)
            advanced: list[BinaryOption] = [option.advance_step() for option in options if option.steps_until_expiry > 0]
            expired: set[int] = {option.option_id for option in options} - {option.option_id for option in advanced}
            fresh, next_id = make_option_suite(self.values, next_id)
            options = advanced + fresh[: self.rng.randint(1, 4)]
            self.settle(expired, settlement_values)
            maker.on_step_advance(underlying_state(self.values), options)
            # Both sides have now booked the same expiries; the ledgers must agree exactly.
            self.max_ledger_gap = max(self.max_ledger_gap, abs(maker.cash_balance - self.cash))

            for option in options:
                fair: float = price_binary_option(truth, option, self.values)
                counterparty_id: int = self.rng.randint(1, 6)
                informed: bool = self.rng.random() < toxicity

                quote = maker.quote(option, counterparty_id)
                if informed:
                    # Take whichever side of the quote is a gift, at the full displayed size.
                    if quote.offer_price < fair:
                        self._apply(option, quote.offer_price, -quote.offer_quantity)
                        maker.on_trade(option, quote.offer_price, -quote.offer_quantity, counterparty_id)
                    elif quote.bid_price > fair:
                        self._apply(option, quote.bid_price, quote.bid_quantity)
                        maker.on_trade(option, quote.bid_price, quote.bid_quantity, counterparty_id)
                elif self.rng.random() < 0.5:
                    side: int = self.rng.choice([1, -1])
                    price: float = quote.bid_price if side > 0 else quote.offer_price
                    size: int = quote.bid_quantity if side > 0 else quote.offer_quantity
                    size = max(1, self.rng.randint(1, size))
                    self._apply(option, price, side * size)
                    maker.on_trade(option, price, side * size, counterparty_id)

                # A toxic fill-or-kill: priced so that taking it is a loss.
                if self.rng.random() < 0.35:
                    counterparty_buys: bool = self.rng.random() < 0.5
                    edge: float = self.rng.uniform(-0.05, 0.05) if not informed else -0.04
                    price = min(max(fair + (edge if counterparty_buys else -edge), 0.0), 1.0)
                    order = FokOrder(
                        counterparty_id=counterparty_id,
                        option_id=option.option_id,
                        order_type=OrderType.BUY if counterparty_buys else OrderType.SELL,
                        price=price,
                        quantity=self.rng.randint(1, 15),
                    )
                    if maker.respond_to_fok(option, order):
                        signed: int = -order.quantity if counterparty_buys else order.quantity
                        self._apply(option, price, signed)
                        maker.on_trade(option, price, signed, counterparty_id)

            self.min_cash = min(self.min_cash, self.cash)
            if self.cash < 0.0:
                if verbose:
                    print(f"    BANKRUPT: cash {self.cash:.2f}")
                return False, self.cash

        # Flush anything still open so the final number is a real PnL.
        self.settle(set(self.gross_long_by_option_id) | set(self.gross_short_by_option_id), self.values)
        return True, self.cash


def check_solvency(num_scenarios: int = 8, num_days: int = 60, seed: int = 23) -> bool:
    rng = random.Random(seed)
    random.seed(seed)
    print("\n[3] solvency under toxic flow (start cash 100.00)")
    print(f"    {'toxicity':>9} {'scenario':>9} {'min cash':>10} {'end cash':>10} {'trades':>7} {'ledger':>9}")
    passed: bool = True

    for toxicity in (0.0, 0.5, 1.0):
        for scenario in range(num_scenarios):
            parameters: MarketParameters = make_parameters(rng)
            history, values = simulate_history(parameters, INITIAL_VALUES, 300)
            maker = MarketMaker(underlying_state(values), [], 100.0)
            maker.warm_up(history)
            exchange = Exchange(parameters, values, 100.0, random.Random(rng.random()))
            solvent, final_cash = exchange.run(maker, num_days, toxicity)

            ledger_ok: bool = exchange.max_ledger_gap < 1e-6
            status: str = "ok" if ledger_ok else f"OFF {exchange.max_ledger_gap:.3f}"
            flag: str = "" if solvent else "   <-- BANKRUPT"
            print(
                f"    {toxicity:>9.1f} {scenario:>9} {exchange.min_cash:>10.2f} {final_cash:>10.2f}"
                f" {exchange.trade_count:>7} {status:>9}{flag}"
            )
            passed = passed and solvent and ledger_ok

    return passed


if __name__ == "__main__":
    results: list[tuple[str, bool]] = [
        ("pricer", check_pricer()),
        ("estimator", check_estimator()),
        ("solvency", check_solvency()),
    ]
    print("\n" + "=" * 60)
    for label, ok in results:
        print(f"  {label:<12} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if all(ok for _, ok in results) else 1)
