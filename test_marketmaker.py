"""Validation harness for the market maker.

Four checks, in increasing order of what they prove:

1. `check_pricer`      -- prices from `price_option_from_parameters` against a Monte Carlo of
                          the real `MarketParameters.advance_step`. This is ground truth.
2. `check_continuity`  -- the price surface has no jumps along the axes the greeks
                          differentiate, and the rate bump still matches the lattice spacing.
                          Gamma is a second difference, so a jump inside a bump window becomes
                          a spurious gamma of order (jump / bump^2) and slams the size caps.
3. `check_estimator`   -- parameters recovered from a warm-up history, priced against the
                          truth, so estimation error shows up in price units.
4. `check_solvency`    -- a full session against maximally toxic counterparties, asserting
                          cash never goes negative and that our own ledger matches the
                          grader's collateral rule exactly.

Run: python3 test_marketmaker.py
"""

import math
import random
import sys

from dataclasses import replace

from marketmaker import (
    AJARAI_NAME,
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_NAME,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_NAME,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    FittedParameters,
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
# 2. Continuity of the price surface along the axes the greeks differentiate
# ---------------------------------------------------------------------------------------------


CONTINUITY_PARAMETERS: FittedParameters = FittedParameters(
    rate_step=0.25,
    rate_intercept_up=0.50,
    rate_slope=-0.10,
    rate_intercept_down=0.10,
    drift_by_id={AJARAI_UNDERLYING_ID: 0.004, THERIODIC_UNDERLYING_ID: 0.002},
    rate_beta_by_id={AJARAI_UNDERLYING_ID: -0.30, THERIODIC_UNDERLYING_ID: -0.25},
    covariance={
        (AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID): 0.010,
        (THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.012,
        (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.004,
    },
)


def _largest_step(price_at, low: float, high: float, num_points: int) -> float:
    prices: list[float] = [price_at(low + (high - low) * i / num_points) for i in range(num_points + 1)]
    return max(abs(prices[i + 1] - prices[i]) for i in range(num_points))


def _halving_ratio(price_at, low: float, high: float, num_points: int = 300) -> float:
    """Largest successive price change at spacing h, divided by the same at h/2.

    A continuous function's largest step halves when the grid halves, giving ~2. Across a
    genuine discontinuity the step is the jump itself and does not shrink, giving ~1. This
    separates "discontinuous" from merely "steep" without needing a magnitude threshold.
    """
    coarse: float = _largest_step(price_at, low, high, num_points)
    fine: float = _largest_step(price_at, low, high, num_points * 2)
    return coarse / fine if fine > 1e-15 else float("inf")


def check_continuity() -> bool:
    values: dict[int, float] = dict(INITIAL_VALUES)
    ajarai_leg = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0),)
    spread_legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0))
    basket_legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, 1.0))

    def price(legs, steps: int, strike: float, overrides: dict[int, float] | None = None) -> float:
        merged: dict[int, float] = dict(values)
        if overrides:
            merged.update(overrides)
        return price_binary_option(
            CONTINUITY_PARAMETERS,
            BinaryOption(legs=legs, option_id=1, steps_until_expiry=steps, strike=strike),
            merged,
        )

    print("\n[2] price surface continuity (halving ratio ~2 continuous, ~1 discontinuous)")
    passed: bool = True

    # The rate axis is a discrete lattice and is *expected* to jump, so it is excluded here and
    # guarded separately below. These three axes must be smooth or the greeks are meaningless.
    cases: list[tuple[str, object]] = [
        ("AJR>=525 vs AJR", lambda x: price(ajarai_leg, 5, 525.0, {AJARAI_UNDERLYING_ID: x})),
        ("AJR-THR>=0 vs AJR", lambda x: price(spread_legs, 5, 0.0, {AJARAI_UNDERLYING_ID: x})),
        ("AJR+THR>=950 vs AJR", lambda x: price(basket_legs, 5, 950.0, {AJARAI_UNDERLYING_ID: x})),
    ]
    for label, function in cases:
        ratio: float = _halving_ratio(function, 400.0, 600.0)
        ok: bool = ratio > 1.6
        passed = passed and ok
        print(f"    {label:<34} ratio {ratio:>5.2f}   {'ok' if ok else 'JUMP'}")

    for label, legs, strike, low, high in (
        ("AJR vs strike", ajarai_leg, 0.0, 400.0, 600.0),
        ("AJR+THR vs strike", basket_legs, 0.0, 850.0, 1050.0),
    ):
        ratio = _halving_ratio(lambda k, l=legs: price(l, 5, k), low, high)
        ok = ratio > 1.6
        passed = passed and ok
        print(f"    {label:<34} ratio {ratio:>5.2f}   {'ok' if ok else 'JUMP'}")

    def scaled(legs, factor: float) -> float:
        parameters = replace(
            CONTINUITY_PARAMETERS,
            covariance={k: v * factor for k, v in CONTINUITY_PARAMETERS.covariance.items()},
        )
        return price_binary_option(
            parameters, BinaryOption(legs=legs, option_id=1, steps_until_expiry=5, strike=525.0), values
        )

    ratio = _halving_ratio(lambda f: scaled(ajarai_leg, f), 0.2, 3.0)
    ok = ratio > 1.6
    passed = passed and ok
    print(f"    {'AJR>=525 vs covariance scale':<34} ratio {ratio:>5.2f}   {'ok' if ok else 'JUMP'}")

    # `_conditional_company_probability` swaps to a closed-form ratio when an opposite-weight
    # pair meets |strike| < TOLERANCE. The two branches must meet, or every relative-value
    # contract is mispriced by the seam width.
    worst_seam: float = 0.0
    for steps in (1, 3, 10, 30):
        closed: float = price(spread_legs, steps, 0.0)
        for epsilon in (1e-12, 1e-9, 1e-8):
            worst_seam = max(worst_seam, abs(price(spread_legs, steps, epsilon) - closed))
    seam_ok: bool = worst_seam < 1e-9
    passed = passed and seam_ok
    print(f"    {'closed-form / quadrature seam':<34} gap   {worst_seam:.1e}   {'ok' if seam_ok else 'SEAM'}")

    # The rate lattice really is discontinuous, so rate gamma is only meaningful because
    # `_factor_risk` bumps by exactly `parameters.rate_step` and lands on adjacent nodes. Shrink
    # that bump and gamma explodes (or silently reads zero inside one cell). This guards the
    # invariant: measured rate gamma must stay bounded.
    worst_gamma: float = 0.0
    for steps in (1, 3, 10):
        for rate in (2.5, 2.75, 3.0, 3.25, 3.5):
            option = BinaryOption(
                legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),),
                option_id=1, steps_until_expiry=steps, strike=3.25,
            )
            local: dict[int, float] = dict(values)
            local[FED_FUNDS_RATE_UNDERLYING_ID] = rate
            maker = MarketMaker(underlying_state(local), [option], 1000.0)
            maker.parameters = CONTINUITY_PARAMETERS
            worst_gamma = max(worst_gamma, abs(maker._factor_risk(option).gamma[0]))
    gamma_ok: bool = worst_gamma < 50.0
    passed = passed and gamma_ok
    print(f"    {'rate gamma bounded (bump=lattice)':<34} max   {worst_gamma:>5.2f}   {'ok' if gamma_ok else 'BLOWN'}")

    return passed


# ---------------------------------------------------------------------------------------------
# 3. Estimator quality, measured in price units
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
    print("\n[3] estimator (warm-up history -> price error vs truth)")
    print(f"    mean abs error {mean_error:.4f}   worst {worst:.4f}   ({count} prices)")
    return mean_error < 0.030 and worst < 0.20


# ---------------------------------------------------------------------------------------------
# 4. Solvency under maximally toxic flow
# ---------------------------------------------------------------------------------------------


class Exchange:
    """Replicates the grader's cash rule: every trade costs its own maximum loss up front,
    and nothing comes back until the option expires.

    `linger_at_expiry` selects the board convention, which the grader's source is not visible
    for and which we must therefore survive either way:

      True  -- an option stays quotable for the step it shows `steps_until_expiry == 0`, and is
               settled afterwards against the values that were live during that step.
      False -- an option is dropped the moment its counter reaches zero, and is settled against
               the values produced by the advance that zeroed it.

    Both settle on the *same* day's underlyings; they differ only in which of the maker's own
    snapshots that day is, and in whether the maker ever sees a zero-step option at all. A maker
    that hard-codes one reading books the wrong payoff under the other -- see
    `check_settlement_conventions`.
    """

    def __init__(
        self,
        parameters: MarketParameters,
        values: dict[int, float],
        cash: float,
        rng: random.Random,
        linger_at_expiry: bool = True,
    ) -> None:
        self.linger_at_expiry = linger_at_expiry
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
        # Signed, and the one that matters: positive means the maker believes it is richer than
        # the grader says, which is the state that ends in a surprise bankruptcy.
        self.max_ledger_overstatement = 0.0

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
            previous_ids: set[int] = {option.option_id for option in options}
            if self.linger_at_expiry:
                survivors: list[BinaryOption] = advanced
                expiry_values: dict[int, float] = settlement_values
            else:
                survivors = [option for option in advanced if option.steps_until_expiry > 0]
                expiry_values = self.values
            expired: set[int] = previous_ids - {option.option_id for option in survivors}
            fresh, next_id = make_option_suite(self.values, next_id)
            options = survivors + fresh[: self.rng.randint(1, 4)]
            self.settle(expired, expiry_values)
            maker.on_step_advance(underlying_state(self.values), options)
            # Both sides have now booked the same expiries; the ledgers must agree exactly.
            self.max_ledger_gap = max(self.max_ledger_gap, abs(maker.cash_balance - self.cash))
            self.max_ledger_overstatement = max(
                self.max_ledger_overstatement, maker.cash_balance - self.cash
            )

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


def check_solvency(num_scenarios: int = 8, num_days: int = 60, seed: int = 23, linger: bool = True) -> bool:
    rng = random.Random(seed)
    random.seed(seed)
    print(f"\n[4] solvency under toxic flow (start cash 100.00, linger_at_expiry={linger})")
    print(f"    {'toxicity':>9} {'scenario':>9} {'min cash':>10} {'end cash':>10} {'trades':>7} {'ledger':>9}")
    passed: bool = True

    for toxicity in (0.0, 0.5, 1.0):
        for scenario in range(num_scenarios):
            parameters: MarketParameters = make_parameters(rng)
            history, values = simulate_history(parameters, INITIAL_VALUES, 300)
            maker = MarketMaker(underlying_state(values), [], 100.0)
            maker.warm_up(history)
            exchange = Exchange(parameters, values, 100.0, random.Random(rng.random()), linger_at_expiry=linger)
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


# ---------------------------------------------------------------------------------------------
# 5. Both settlement conventions, and no exception escapes a public method
# ---------------------------------------------------------------------------------------------


def check_settlement_conventions(num_scenarios: int = 6, num_days: int = 60, seed: int = 31) -> bool:
    """The maker must book expiries correctly under either board convention.

    `check_solvency` asserts the maker's own reading back at it, so it can never fail this way.
    Here the board is run both ways against the same maker code. What is being measured is the
    *signed* gap: a maker that overstates its cash is spending money the grader does not think
    it has, and the measured overstatement for a hard-coded reading was 31.00 on a 100 bankroll.
    """
    print("\n[5] settlement-convention agnosticism (ledger must match either board)")
    print(f"    {'convention':>26} {'toxicity':>9} {'max |gap|':>10} {'max overstated':>15}")
    passed: bool = True

    for linger in (True, False):
        label: str = "linger at 0 steps" if linger else "drop at 0 steps"
        for toxicity in (0.0, 1.0):
            rng = random.Random(seed)
            random.seed(seed)
            worst_gap: float = 0.0
            worst_over: float = 0.0
            for _ in range(num_scenarios):
                parameters: MarketParameters = make_parameters(rng)
                history, values = simulate_history(parameters, INITIAL_VALUES, 300)
                maker = MarketMaker(underlying_state(values), [], 100.0)
                maker.warm_up(history)
                exchange = Exchange(
                    parameters, values, 100.0, random.Random(rng.random()), linger_at_expiry=linger
                )
                solvent, _ = exchange.run(maker, num_days, toxicity)
                worst_gap = max(worst_gap, exchange.max_ledger_gap)
                worst_over = max(worst_over, exchange.max_ledger_overstatement)
                passed = passed and solvent
            ok: bool = worst_gap < 1e-6
            passed = passed and ok
            print(
                f"    {label:>26} {toxicity:>9.1f} {worst_gap:>10.4f} {worst_over:>15.4f}"
                f"   {'ok' if ok else 'DIVERGED'}"
            )

    return passed


def check_robustness() -> bool:
    """No exception may escape a public method, whatever the grader hands us.

    The VERBOSE scenarios award full marks purely for not erroring, so an escaped exception
    costs more than any spread could earn. Each case below crashed an unguarded build.
    """
    print("\n[6] no exception escapes a public method")
    values: dict[int, float] = dict(INITIAL_VALUES)
    state = underlying_state(values)
    normal = BinaryOption(
        legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1, steps_until_expiry=3, strike=500.0
    )
    unknown_leg = BinaryOption(
        legs=(OptionLeg(99, 1.0),), option_id=2, steps_until_expiry=3, strike=1.0
    )
    zero_step = BinaryOption(
        legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=3, steps_until_expiry=0, strike=400.0
    )
    spread = BinaryOption(
        legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)),
        option_id=4, steps_until_expiry=2, strike=0.0,
    )
    zero_value_state = [
        Underlying(name=FED_FUNDS_RATE_NAME, underlying_id=FED_FUNDS_RATE_UNDERLYING_ID, value=0.0),
        Underlying(name=AJARAI_NAME, underlying_id=AJARAI_UNDERLYING_ID, value=0.0),
        Underlying(name=THERIODIC_NAME, underlying_id=THERIODIC_UNDERLYING_ID, value=420.0),
    ]

    cases: list[tuple[str, object]] = []

    def add(label: str, function) -> None:
        cases.append((label, function))

    add("quote: leg on an unknown underlying", lambda: MarketMaker(state, [unknown_leg], 100.0).quote(unknown_leg, 1))
    add("quote: FED missing from state", lambda: MarketMaker(state[1:], [normal], 100.0).quote(normal, 1))
    add("quote: zero cash", lambda: MarketMaker(state, [normal], 0.0).quote(normal, 1))
    add("quote: negative cash", lambda: MarketMaker(state, [normal], -50.0).quote(normal, 1))
    add("quote: zero underlying values", lambda: MarketMaker(zero_value_state, [normal], 100.0).quote(normal, 1))
    add("quote: zero-step option", lambda: MarketMaker(state, [zero_step], 100.0).quote(zero_step, 1))
    add("quote: no warm-up at all", lambda: MarketMaker(state, [spread], 100.0).quote(spread, 7))
    add("price_option: unknown leg", lambda: MarketMaker(state, [unknown_leg], 100.0).price_option(unknown_leg))
    add("on_trade: unknown leg", lambda: MarketMaker(state, [], 100.0).on_trade(unknown_leg, 0.5, 3, 1))
    add("on_step_advance: empty state", lambda: MarketMaker(state, [normal], 100.0).on_step_advance([], []))
    add("warm_up: empty history", lambda: MarketMaker(state, [], 100.0).warm_up(MarketHistory(values_by_underlying_id={})))
    add(
        "warm_up: single-day history",
        lambda: MarketMaker(state, [], 100.0).warm_up(
            MarketHistory(values_by_underlying_id={1: (3.0,), 2: (500.0,), 3: (420.0,)})
        ),
    )
    add(
        "warm_up: rate path only",
        lambda: MarketMaker(state, [], 100.0).warm_up(
            MarketHistory(values_by_underlying_id={FED_FUNDS_RATE_UNDERLYING_ID: (3.0,) * 50})
        ),
    )
    add(
        "warm_up: a company at zero throughout",
        lambda: MarketMaker(state, [], 100.0).warm_up(
            MarketHistory(values_by_underlying_id={1: (3.0,) * 50, 2: (0.0,) * 50, 3: (420.0,) * 50})
        ),
    )
    for price in (0.0, 1.0, 1.5, 2.0):
        for order_type in (OrderType.BUY, OrderType.SELL):
            add(
                f"respond_to_fok: price {price} {order_type}",
                lambda p=price, t=order_type: MarketMaker(state, [normal], 100.0).respond_to_fok(
                    normal, FokOrder(counterparty_id=1, option_id=1, order_type=t, price=p, quantity=5)
                ),
            )

    passed: bool = True
    for label, function in cases:
        try:
            result = function()
            status = "ok"
        except Exception as error:  # noqa: BLE001 -- the whole point of the check
            result = f"{type(error).__name__}: {error}"
            status = "RAISED"
            passed = False
        print(f"    {label:<44} {status:>6}   {result}")

    # A declined quote must still be a legal, cash-free quote.
    decline = MarketMaker.DECLINE_QUOTE
    legal: bool = decline.bid_price == 0.0 and decline.offer_price == 1.0
    passed = passed and legal
    print(f"    {'decline quote locks up no cash':<44} {'ok' if legal else 'BAD':>6}   {decline}")
    return passed


if __name__ == "__main__":
    results: list[tuple[str, bool]] = [
        ("pricer", check_pricer()),
        ("continuity", check_continuity()),
        ("estimator", check_estimator()),
        ("solvency", check_solvency()),
        ("settlement", check_settlement_conventions()),
        ("robustness", check_robustness()),
    ]
    print("\n" + "=" * 60)
    for label, ok in results:
        print(f"  {label:<12} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if all(ok for _, ok in results) else 1)
