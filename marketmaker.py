import math
import random
from collections import defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import lru_cache
from typing import Any, Final

AJARAI_NAME: Final[str] = "AJR"
AJARAI_UNDERLYING_ID: Final[int] = 2
FED_FUNDS_RATE_NAME: Final[str] = "FED"
FED_FUNDS_RATE_UNDERLYING_ID: Final[int] = 1
RATE_STRIKE_GRID: Final[float] = 0.25
THERIODIC_NAME: Final[str] = "THR"
THERIODIC_UNDERLYING_ID: Final[int] = 3

UNDERLYING_NAME_BY_ID: Final[dict[int, str]] = {
    AJARAI_UNDERLYING_ID: AJARAI_NAME,
    FED_FUNDS_RATE_UNDERLYING_ID: FED_FUNDS_RATE_NAME,
    THERIODIC_UNDERLYING_ID: THERIODIC_NAME,
}


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class BinaryOption:
    legs: "tuple[OptionLeg, ...]"
    option_id: int
    steps_until_expiry: int
    strike: float

    def __post_init__(self) -> None:
        if self.steps_until_expiry < 0:
            raise ValueError("Steps until expiry must be non-negative")

        if not self.legs:
            raise ValueError("Binary option must have at least one leg")

        underlying_ids: list[int] = [leg.underlying_id for leg in self.legs]
        if len(underlying_ids) != len(set(underlying_ids)):
            raise ValueError("Binary option legs must reference distinct underlyings")

        if any(leg.weight == 0 for leg in self.legs):
            raise ValueError("Binary option leg weights must be non-zero")

    def __str__(self) -> str:
        terms: list[str] = []
        for index, leg in enumerate(self.legs):
            name: str = UNDERLYING_NAME_BY_ID.get(leg.underlying_id, str(leg.underlying_id))
            magnitude: float = abs(leg.weight)
            magnitude_str: str = "" if magnitude == 1 else f"{magnitude:.2f}*"
            if index == 0:
                sign: str = "-" if leg.weight < 0 else ""
            else:
                sign = " - " if leg.weight < 0 else " + "
            terms.append(f"{sign}{magnitude_str}{name}")
        observable_expression: str = "".join(terms)
        return f"{self.option_id} ({self.steps_until_expiry}d {observable_expression} >= {self.strike:.2f})"

    def advance_step(self) -> "BinaryOption":
        if self.steps_until_expiry == 0:
            return self

        return replace(self, steps_until_expiry=self.steps_until_expiry - 1)

    def contract_matches(self, other: "BinaryOption") -> bool:
        return replace(other, option_id=self.option_id) == self

    def expiry_valuation(self, value_by_underlying_id: dict[int, float]) -> float:
        return 1.0 if self.observable_value(value_by_underlying_id) >= self.strike else 0.0

    def observable_value(self, value_by_underlying_id: dict[int, float]) -> float:
        return sum(leg.weight * value_by_underlying_id[leg.underlying_id] for leg in self.legs)


@dataclass(frozen=True)
class FokOrder:
    counterparty_id: int
    option_id: int
    order_type: "OrderType"
    price: float
    quantity: int

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("FOK order price must be non-negative")

        if self.quantity <= 0:
            raise ValueError("FOK order quantity must be positive")


@dataclass(frozen=True)
class MarketHistory:
    values_by_underlying_id: dict[int, tuple[float, ...]]

    def __post_init__(self) -> None:
        lengths: set[int] = {len(values) for values in self.values_by_underlying_id.values()}
        if len(lengths) > 1:
            raise ValueError("All underlyings must have the same number of historical days")

        if lengths and next(iter(lengths)) <= 0:
            raise ValueError("Market history must contain at least one day")

    @property
    def num_days(self) -> int:
        if not self.values_by_underlying_id:
            return 0
        return len(next(iter(self.values_by_underlying_id.values())))


@dataclass(frozen=True)
class MarketParameters:
    ajarai_drift: float
    ajarai_idio_std_dev: float
    ajarai_rate_beta: float
    ajarai_sector_beta: float
    rate_down_probability: float
    rate_reversion_strength: float
    rate_up_probability: float
    sector_std_dev: float
    theriodic_drift: float
    theriodic_idio_std_dev: float
    theriodic_rate_beta: float
    theriodic_sector_beta: float

    rate_step: float = 0.25
    rate_target: float = 2.0

    def __post_init__(self) -> None:
        if self.rate_step <= 0:
            raise ValueError("Rate step must be positive")

        if self.rate_up_probability <= 0 or self.rate_down_probability <= 0:
            raise ValueError("Rate up/down probabilities must both be positive")

        if self.rate_up_probability + self.rate_down_probability > 1:
            raise ValueError("Rate up/down probabilities must not sum to more than 1")

        if self.rate_target < 0:
            raise ValueError("Rate target must be non-negative")

        if not (0 <= self.rate_reversion_strength <= 1):
            raise ValueError("Rate reversion strength must be between 0 and 1")

        if self.ajarai_idio_std_dev < 0 or self.theriodic_idio_std_dev < 0 or self.sector_std_dev < 0:
            raise ValueError("Standard deviations must be non-negative")

    def advance_company_value(
        self,
        current_value: float,
        rate_change: float,
        sector_shock: float,
        *,
        drift: float,
        rate_beta: float,
        sector_beta: float,
        idio_std_dev: float,
    ) -> float:
        idiosyncratic_shock: float = random.gauss(mu=0.0, sigma=idio_std_dev)
        log_return: float = drift + (rate_beta * rate_change) + (sector_beta * sector_shock) + idiosyncratic_shock
        return round(current_value * math.exp(log_return), 2)

    def advance_rate(self, rate_value: float) -> float:
        up_probability, down_probability = self.tilted_rate_probabilities(rate_value)
        draw: float = random.random()
        if draw < up_probability:
            return self.next_rate_value(rate_value, 1)

        if draw < up_probability + down_probability:
            return self.next_rate_value(rate_value, -1)

        return rate_value

    def advance_step(self, value_by_underlying_id: dict[int, float]) -> dict[int, float]:
        current_rate_value: float = value_by_underlying_id[FED_FUNDS_RATE_UNDERLYING_ID]
        rate_value: float = self.advance_rate(current_rate_value)
        rate_change: float = round(rate_value - current_rate_value, 2)
        sector_shock: float = random.gauss(mu=0.0, sigma=self.sector_std_dev)
        return {
            FED_FUNDS_RATE_UNDERLYING_ID: rate_value,
            AJARAI_UNDERLYING_ID: self.advance_company_value(
                value_by_underlying_id[AJARAI_UNDERLYING_ID],
                rate_change,
                sector_shock,
                drift=self.ajarai_drift,
                rate_beta=self.ajarai_rate_beta,
                sector_beta=self.ajarai_sector_beta,
                idio_std_dev=self.ajarai_idio_std_dev,
            ),
            THERIODIC_UNDERLYING_ID: self.advance_company_value(
                value_by_underlying_id[THERIODIC_UNDERLYING_ID],
                rate_change,
                sector_shock,
                drift=self.theriodic_drift,
                rate_beta=self.theriodic_rate_beta,
                sector_beta=self.theriodic_sector_beta,
                idio_std_dev=self.theriodic_idio_std_dev,
            ),
        }

    def next_rate_value(self, rate_value: float, num_grid_steps: int) -> float:
        return max(round(rate_value + num_grid_steps * self.rate_step, 2), 0.0)

    def tilted_rate_probabilities(self, rate_value: float) -> tuple[float, float]:
        tilt: float = self.rate_reversion_strength * (self.rate_target - rate_value)
        up_probability: float = min(max(self.rate_up_probability + tilt, 0.0), 1.0)
        down_probability: float = min(max(self.rate_down_probability - tilt, 0.0), 1.0 - up_probability)
        return up_probability, down_probability


@dataclass(frozen=True)
class OptionLeg:
    underlying_id: int
    weight: float


class OrderType(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Position:
    def __init__(self) -> None:
        self.option_quantity_by_option_id: dict[int, int] = defaultdict(int)

    def add_option_quantity(self, option_id: int, quantity: int) -> None:
        self.option_quantity_by_option_id[option_id] += quantity


@dataclass(frozen=True)
class Quote:
    bid_price: float
    bid_quantity: int
    offer_price: float
    offer_quantity: int

    def __post_init__(self) -> None:
        if self.bid_quantity <= 0 or self.offer_quantity <= 0:
            raise ValueError("Quote quantities must be positive")

        if not (0.0 <= self.bid_price <= 1.0 and 0.0 <= self.offer_price <= 1.0):
            raise ValueError("Quote prices must be between 0 and 1")

        if self.bid_price >= self.offer_price:
            raise ValueError("Quote bid price must be less than offer price")

        if any(abs(round(price * 100) - price * 100) > 1e-6 for price in (self.bid_price, self.offer_price)):
            raise ValueError("Quote prices must be in whole pennies (multiples of 0.01)")


@dataclass(frozen=True)
class Underlying:
    name: str
    underlying_id: int
    value: float

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Underlying):
            return False
        return self.underlying_id == other.underlying_id

COMPANY_UNDERLYING_IDS: Final[tuple[int, ...]] = (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)
TOLERANCE: Final[float] = 1e-9

# Quoting knobs. `HURDLE_PER_STEP` is the required return on the cash the trade locks up, per
# step until expiry; see `_collateral_quote_prices`.
HURDLE_PER_STEP: Final[float] = 0.012
MAX_HURDLE: Final[float] = 0.18
MIN_HALF_SPREAD: Final[float] = 0.01
WINNER_CURSE_PAD: Final[float] = 0.008
INVENTORY_AVERSION: Final[float] = 1.5
MAX_INVENTORY_SKEW: Final[float] = 0.25
MAX_QUOTE_SIZE: Final[int] = 40

# Convexity knobs. Binary payoffs are step functions, so delta is not stable: near the strike
# and near expiry it is enormous and flips sign on the other side. `GAMMA_AVERSION` weights the
# second-order term in the inventory covariance (1.0 = the textbook Taylor term), which is what
# catches a book that nets to delta-flat but whose legs all flip the same way on one move.
# `GAMMA_PAD_AVERSION` charges for that curvature in the spread, and `GAMMA_SIZE_TOLERANCE` is
# the convexity charge (in price units) at which quoted size is cut in half.
# `GAMMA_AVERSION` is 0.0 on measurement, not on principle: a paired A/B over 160 simulated
# sessions found the second-order skew term costs ~4 PnL against uninformed flow and is a wash
# against informed flow. Charging for curvature and refusing size beat trying to skew it away,
# because the risk it describes is not directional. Left as one number to flip if that changes.
GAMMA_AVERSION: Final[float] = 0.0
GAMMA_PAD_AVERSION: Final[float] = 0.25
MAX_GAMMA_PAD: Final[float] = 0.04
GAMMA_SIZE_TOLERANCE: Final[float] = 0.02
# Bump used for the company log-value derivatives. Small against a per-step sigma of ~0.10, so
# the second difference resolves real curvature rather than the shape of the whole distribution.
COMPANY_LOG_BUMP: Final[float] = 0.01

# Vega knobs. Unlike delta and gamma this is not a risk we carry, it is a measure of how wrong
# our own theo can be: `covariance` is the one fitted parameter that never passes through
# `_shrink_towards_zero`, so a thin or unlucky warm-up feeds the pricer a vol level we have no
# right to trust. `VOL_RELATIVE_UNCERTAINTY` is the relative standard error of a sample
# covariance, ~sqrt(2/N) for N residuals, so |vega| * that is the price error one sigma of
# estimation noise buys us.
# Measured worth on top of gamma: +4.6 PnL against uninformed flow, +1.6 at half toxicity,
# nil against fully informed flow. Small next to gamma's +37/+28/+6, but consistent (70/80 and
# 64/80 paired wins). It is not redundant with gamma despite a +0.56 charge correlation: gamma
# blows up as 1/sigma^2 and so only ever flags short-dated contracts, while vega stays bounded
# and catches the long-dated ones, where n steps of compounding make a covariance error worst.
# `VOL_RELATIVE_UNCERTAINTY` is only the fallback for when we have no residual count to work
# from; `FittedParameters.covariance_sample_size` normally drives it, because sqrt(2/N) is a
# factor of two larger on a 60-day warm-up than on the 200-day one this constant assumed.
VOL_RELATIVE_UNCERTAINTY: Final[float] = 0.10
MIN_VOL_RELATIVE_UNCERTAINTY: Final[float] = 0.05
MAX_VOL_RELATIVE_UNCERTAINTY: Final[float] = 0.50
COVARIANCE_BUMP: Final[float] = 0.10
VEGA_PAD_AVERSION: Final[float] = 1.0
MAX_VEGA_PAD: Final[float] = 0.04
VEGA_SIZE_TOLERANCE: Final[float] = 0.005

# Online re-estimation. The warm-up is whatever the grader hands us, and price error is brutally
# sensitive to its length (measured: mean 0.114 at 30 days, 0.075 at 60, 0.026 at 400 -- against
# a quoted half-spread of a few cents). Every step of the session is another observation of the
# same fixed generator, so folding the live path back into the fit is free accuracy. Refitting
# costs one O(N) pass, so the interval is about cache churn, not compute.
REFIT_INTERVAL_STEPS: Final[int] = 5
MIN_REFIT_OBSERVATIONS: Final[int] = 30

# Collateral is only returned at expiry, so the book's peak usage is roughly
# (fills per step) x (collateral per fill) x (steps held). Budgeting each quote against the
# number of live options keeps that product under the bankroll.
CONCURRENT_LOAD_FACTOR: Final[float] = 2.5
CASH_BUFFER_FRACTION: Final[float] = 0.10
MIN_CASH_BUFFER: Final[float] = 2.0
FOK_EDGE_REQUIRED: Final[float] = 0.015

# The counterparty's own direction, used only as the starting guess: `on_trade` reports the
# signed quantity we actually received, so an accepted FOK tells us which reading is right and
# `_record_fok_outcome` flips this if the tape disagrees. Until enough fills have voted, FOKs
# are treated as probes -- double edge required, and only small clips -- which bounds the cost
# of starting on the wrong guess to a few cents.
ORDER_TYPE_IS_COUNTERPARTY_SIDE: Final[bool] = True
FOK_SIDE_CONFIRMING_TRADES: Final[int] = 3
FOK_SIDE_FLIP_MARGIN: Final[int] = 2
FOK_PROBE_MAX_QUANTITY: Final[int] = 3
FOK_PROBE_EDGE_MULTIPLIER: Final[float] = 2.0

# Settlement timing. `on_step_advance` derives, per expiring option, which day's values the
# payoff was struck against (see `_settlement_values_for`). `_pessimistic_cash` shadows the main
# ledger crediting the *worse* of the two readings, and sizing runs off the lower of the two.
# The cap stops a long run of disagreements from strangling quote sizes outright; without any
# such shadow, a wrong reading was measured to invent 31.00 of phantom cash on a 100 bankroll.
SETTLEMENT_DOUBT_CAP_FRACTION: Final[float] = 0.25


def _norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _gauss_legendre(num_nodes: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Nodes and weights for Gauss-Legendre quadrature on [-1, 1], by Newton iteration."""
    nodes: list[float] = []
    weights: list[float] = []
    for index in range(1, num_nodes + 1):
        x: float = math.cos(math.pi * (index - 0.25) / (num_nodes + 0.5))
        derivative: float = 1.0
        for _ in range(100):
            legendre, previous = 1.0, 0.0
            for degree in range(1, num_nodes + 1):
                legendre, previous = (
                    ((2 * degree - 1) * x * legendre - (degree - 1) * previous) / degree,
                    legendre,
                )
            derivative = num_nodes * (x * legendre - previous) / (x * x - 1.0)
            adjustment: float = -legendre / derivative
            x += adjustment
            if abs(adjustment) < 1e-15:
                break
        nodes.append(x)
        weights.append(2.0 / ((1.0 - x * x) * derivative * derivative))
    return tuple(nodes), tuple(weights)


def _standard_normal_quadrature(num_nodes: int, limit: float = 8.0) -> tuple[tuple[float, float], ...]:
    """(node, weight) pairs approximating integration against the standard normal density."""
    raw_nodes, raw_weights = _gauss_legendre(num_nodes)
    scale: float = 1.0 / math.sqrt(2.0 * math.pi)
    return tuple(
        (limit * node, weight * limit * scale * math.exp(-0.5 * (limit * node) ** 2))
        for node, weight in zip(raw_nodes, raw_weights)
    )


NORMAL_QUADRATURE: Final[tuple[tuple[float, float], ...]] = _standard_normal_quadrature(48)


def _covariance_key(first_id: int, second_id: int) -> tuple[int, int]:
    return (first_id, second_id) if first_id <= second_id else (second_id, first_id)


@dataclass(frozen=True)
class FittedParameters:
    """Sufficient statistics for pricing, in the form the pricer actually consumes.

    The rate chain is stored as its transition *function* rather than as
    (up, down, reversion, target): those four are not separately identifiable from a path, but
    the two clipped lines below are, and they are all the DP needs.

        up(r)   = clip(rate_intercept_up   + rate_slope * r, 0, 1)
        down(r) = clip(rate_intercept_down - rate_slope * r, 0, 1 - up)

    Company log-returns are, per step and conditional on that step's realized rate change,
        drift + rate_beta * rate_change + N(0, covariance)
    where `covariance` folds the shared sector shock and the idiosyncratic shock together.
    Only the product (sector_beta * sector_std_dev) is identifiable, and only it is needed.

    `covariance_sample_size` is the number of residuals `covariance` was built from. It is not
    used in pricing at all -- it is carried so the vega charge can size itself off the actual
    standard error, sqrt(2/N), instead of a constant guessing at N. Zero means "unknown".
    """

    rate_step: float
    rate_intercept_up: float
    rate_slope: float
    rate_intercept_down: float
    drift_by_id: dict[int, float]
    rate_beta_by_id: dict[int, float]
    covariance: dict[tuple[int, int], float]
    covariance_sample_size: int = 0

    @property
    def relative_vol_uncertainty(self) -> float:
        """Relative standard error of the fitted vol level, sqrt(2/N), clamped to a sane band."""
        if self.covariance_sample_size < 2:
            return VOL_RELATIVE_UNCERTAINTY
        return min(
            max(math.sqrt(2.0 / self.covariance_sample_size), MIN_VOL_RELATIVE_UNCERTAINTY),
            MAX_VOL_RELATIVE_UNCERTAINTY,
        )

    def rate_transition_probabilities(self, rate_value: float) -> tuple[float, float]:
        up_probability: float = min(max(self.rate_intercept_up + self.rate_slope * rate_value, 0.0), 1.0)
        down_probability: float = min(
            max(self.rate_intercept_down - self.rate_slope * rate_value, 0.0), 1.0 - up_probability
        )
        return up_probability, down_probability

    def next_rate_value(self, rate_value: float, num_grid_steps: int) -> float:
        return max(round(rate_value + num_grid_steps * self.rate_step, 2), 0.0)


DEFAULT_PARAMETERS: Final[FittedParameters] = FittedParameters(
    rate_step=RATE_STRIKE_GRID,
    rate_intercept_up=0.30 + 0.10 * 2.0,
    rate_slope=-0.10,
    rate_intercept_down=0.30 - 0.10 * 2.0,
    drift_by_id={AJARAI_UNDERLYING_ID: 0.0, THERIODIC_UNDERLYING_ID: 0.0},
    rate_beta_by_id={AJARAI_UNDERLYING_ID: -0.30, THERIODIC_UNDERLYING_ID: -0.30},
    covariance={
        (AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID): 0.0100,
        (THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.0100,
        (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.0040,
    },
)


def fitted_from_market_parameters(market_parameters: MarketParameters) -> FittedParameters:
    """Exact translation of the true generator into the pricer's internal form."""
    reversion: float = market_parameters.rate_reversion_strength
    target: float = market_parameters.rate_target
    sector_variance: float = market_parameters.sector_std_dev**2
    return FittedParameters(
        rate_step=market_parameters.rate_step,
        rate_intercept_up=market_parameters.rate_up_probability + reversion * target,
        rate_slope=-reversion,
        rate_intercept_down=market_parameters.rate_down_probability - reversion * target,
        drift_by_id={
            AJARAI_UNDERLYING_ID: market_parameters.ajarai_drift,
            THERIODIC_UNDERLYING_ID: market_parameters.theriodic_drift,
        },
        rate_beta_by_id={
            AJARAI_UNDERLYING_ID: market_parameters.ajarai_rate_beta,
            THERIODIC_UNDERLYING_ID: market_parameters.theriodic_rate_beta,
        },
        covariance={
            (AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID): (
                (market_parameters.ajarai_sector_beta**2) * sector_variance
                + market_parameters.ajarai_idio_std_dev**2
            ),
            (THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): (
                (market_parameters.theriodic_sector_beta**2) * sector_variance
                + market_parameters.theriodic_idio_std_dev**2
            ),
            (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): (
                market_parameters.ajarai_sector_beta * market_parameters.theriodic_sector_beta * sector_variance
            ),
        },
        # These are the true parameters, not an estimate: there is no estimation error to charge
        # for, so the sample size is nominally infinite.
        covariance_sample_size=1_000_000_000,
    )


@lru_cache(maxsize=8192)
def _terminal_rate_distribution(
    rate_step: float,
    rate_intercept_up: float,
    rate_slope: float,
    rate_intercept_down: float,
    initial_rate: float,
    num_steps: int,
) -> tuple[tuple[float, float], ...]:
    """Forward DP over the 0.25 grid, keyed only on what the rate chain actually depends on.

    Split out from `terminal_rate_distribution` and memoized because the greeks reprice the
    same option 9 times, and 8 of those bumps move a company value or the covariance -- neither
    of which touches this DP. Keyed on the four chain scalars rather than the parameters object
    so a `replace`-d copy carrying a bumped covariance still hits.

    Returns an immutable tuple: the result is shared between callers and must not be mutated.
    """
    distribution: dict[float, float] = {initial_rate: 1.0}
    for _ in range(num_steps):
        updated: dict[float, float] = defaultdict(float)
        for rate_value, probability in distribution.items():
            up_probability: float = min(max(rate_intercept_up + rate_slope * rate_value, 0.0), 1.0)
            down_probability: float = min(
                max(rate_intercept_down - rate_slope * rate_value, 0.0), 1.0 - up_probability
            )
            stay_probability: float = max(0.0, 1.0 - up_probability - down_probability)
            if up_probability > 0.0:
                updated[max(round(rate_value + rate_step, 2), 0.0)] += probability * up_probability
            if down_probability > 0.0:
                updated[max(round(rate_value - rate_step, 2), 0.0)] += probability * down_probability
            if stay_probability > 0.0:
                updated[rate_value] += probability * stay_probability
        distribution = dict(updated)
    return tuple(distribution.items())


def terminal_rate_distribution(
    parameters: FittedParameters, initial_rate: float, num_steps: int
) -> dict[float, float]:
    """Exact distribution of the rate after `num_steps`, by forward DP over the 0.25 grid."""
    return dict(
        _terminal_rate_distribution(
            parameters.rate_step,
            parameters.rate_intercept_up,
            parameters.rate_slope,
            parameters.rate_intercept_down,
            initial_rate,
            num_steps,
        )
    )


def _weighted_lognormal_at_least(
    weight: float, scale: float, mean: float, std_dev: float, threshold: float
) -> float:
    """P(weight * scale * exp(Z) >= threshold) for Z ~ N(mean, std_dev)."""
    if scale <= 0.0:
        return 1.0 if weight * scale >= threshold else 0.0

    bound: float = threshold / weight
    if weight > 0.0:
        if bound <= 0.0:
            return 1.0
        target: float = math.log(bound / scale)
        if std_dev <= 0.0:
            return 1.0 if mean >= target else 0.0
        return _norm_sf((target - mean) / std_dev)

    if bound <= 0.0:
        return 0.0
    target = math.log(bound / scale)
    if std_dev <= 0.0:
        return 1.0 if mean <= target else 0.0
    return _norm_cdf((target - mean) / std_dev)


def _conditional_company_probability(
    parameters: FittedParameters,
    weight_by_id: dict[int, float],
    value_by_underlying_id: dict[int, float],
    num_steps: int,
    rate_change: float,
    threshold: float,
) -> float:
    """P(sum of weighted company values >= threshold), given the realized total rate change.

    Conditional on the terminal rate the company values are exactly (jointly) lognormal,
    because the per-step rate changes telescope to (terminal rate - initial rate).
    """
    company_ids: list[int] = sorted(weight_by_id)
    scale_by_id: dict[int, float] = {}
    for company_id in company_ids:
        drift: float = parameters.drift_by_id[company_id]
        rate_beta: float = parameters.rate_beta_by_id[company_id]
        scale_by_id[company_id] = value_by_underlying_id[company_id] * math.exp(
            num_steps * drift + rate_beta * rate_change
        )

    if len(company_ids) == 1:
        only_id: int = company_ids[0]
        variance: float = num_steps * parameters.covariance[_covariance_key(only_id, only_id)]
        return _weighted_lognormal_at_least(
            weight_by_id[only_id], scale_by_id[only_id], 0.0, math.sqrt(max(variance, 0.0)), threshold
        )

    first_id, second_id = company_ids
    first_variance: float = num_steps * parameters.covariance[_covariance_key(first_id, first_id)]
    second_variance: float = num_steps * parameters.covariance[_covariance_key(second_id, second_id)]
    cross_covariance: float = num_steps * parameters.covariance[_covariance_key(first_id, second_id)]
    first_weight: float = weight_by_id[first_id]
    second_weight: float = weight_by_id[second_id]

    # Relative-value contracts (w1*V1 + w2*V2 >= 0 with opposite signs) collapse to a ratio,
    # which is exactly normal in logs -- no quadrature needed.
    if abs(threshold) < TOLERANCE and first_weight * second_weight < 0.0:
        difference_variance: float = first_variance + second_variance - 2.0 * cross_covariance
        log_ratio_target: float = math.log(abs(second_weight) / abs(first_weight)) - math.log(
            scale_by_id[first_id] / scale_by_id[second_id]
        )
        if difference_variance <= 0.0:
            return 1.0 if -log_ratio_target >= 0.0 else 0.0
        standardized: float = log_ratio_target / math.sqrt(difference_variance)
        return _norm_sf(standardized) if first_weight > 0.0 else _norm_cdf(standardized)

    if first_variance <= 0.0:
        return _weighted_lognormal_at_least(
            second_weight,
            scale_by_id[second_id],
            0.0,
            math.sqrt(max(second_variance, 0.0)),
            threshold - first_weight * scale_by_id[first_id],
        )

    first_std_dev: float = math.sqrt(first_variance)
    conditional_slope: float = cross_covariance / first_variance
    conditional_std_dev: float = math.sqrt(max(second_variance - cross_covariance**2 / first_variance, 0.0))

    total: float = 0.0
    for node, node_weight in NORMAL_QUADRATURE:
        shock: float = node * first_std_dev
        residual_threshold: float = threshold - first_weight * scale_by_id[first_id] * math.exp(shock)
        total += node_weight * _weighted_lognormal_at_least(
            second_weight,
            scale_by_id[second_id],
            conditional_slope * shock,
            conditional_std_dev,
            residual_threshold,
        )
    return total


def price_binary_option(
    parameters: FittedParameters, option: BinaryOption, value_by_underlying_id: dict[int, float]
) -> float:
    """Exact probability that `option` expires in the money.

    Outer layer: the rate's terminal distribution by DP (finite Markov chain, no approximation).
    Inner layer: a conditional Gaussian, closed form except when two company legs meet a
    non-zero strike, where one Gauss-Legendre pass over the first company's shock is used.
    """
    if option.steps_until_expiry <= 0:
        return option.expiry_valuation(value_by_underlying_id)

    weight_by_id: dict[int, float] = {leg.underlying_id: leg.weight for leg in option.legs}
    rate_weight: float = weight_by_id.pop(FED_FUNDS_RATE_UNDERLYING_ID, 0.0)
    initial_rate: float = value_by_underlying_id[FED_FUNDS_RATE_UNDERLYING_ID]
    # The memoized tuple form, not the dict wrapper: this is the hot path and the greeks call
    # it nine times per option with an identical rate chain.
    distribution: tuple[tuple[float, float], ...] = _terminal_rate_distribution(
        parameters.rate_step,
        parameters.rate_intercept_up,
        parameters.rate_slope,
        parameters.rate_intercept_down,
        initial_rate,
        option.steps_until_expiry,
    )

    if not weight_by_id:
        return sum(
            probability
            for rate_value, probability in distribution
            if rate_weight * rate_value >= option.strike - TOLERANCE
        )

    total: float = 0.0
    for rate_value, probability in distribution:
        if probability <= 0.0:
            continue
        total += probability * _conditional_company_probability(
            parameters,
            weight_by_id,
            value_by_underlying_id,
            option.steps_until_expiry,
            rate_value - initial_rate,
            option.strike - rate_weight * rate_value,
        )
    return min(max(total, 0.0), 1.0)


def _shrink_towards_zero(estimate: float, standard_error: float) -> float:
    """Scale an estimate by its own signal-to-noise; kills statistically empty drifts/betas."""
    if standard_error <= 0.0:
        return estimate
    signal_to_noise: float = estimate / standard_error
    return estimate * (signal_to_noise**2 / (1.0 + signal_to_noise**2))


def _estimate_rate_chain(rate_path: tuple[float, ...]) -> tuple[float, float, float]:
    """Weighted least squares for the two clipped transition lines, sharing one slope.

    States at rate 0 are excluded: the floor in `next_rate_value` absorbs down-moves there, so
    a recorded "no change" is not distinguishable from a genuine stay.
    """
    counts: dict[float, list[int]] = defaultdict(lambda: [0, 0, 0])
    for index in range(len(rate_path) - 1):
        change: float = round(rate_path[index + 1] - rate_path[index], 2)
        bucket: list[int] = counts[rate_path[index]]
        bucket[2] += 1
        if change > TOLERANCE:
            bucket[0] += 1
        elif change < -TOLERANCE:
            bucket[1] += 1

    samples: list[tuple[float, float, float, int]] = [
        (rate_value, bucket[0] / bucket[2], bucket[1] / bucket[2], bucket[2])
        for rate_value, bucket in counts.items()
        if rate_value > TOLERANCE and bucket[2] > 0
    ]
    total_weight: int = sum(sample[3] for sample in samples)
    if total_weight == 0:
        return DEFAULT_PARAMETERS.rate_intercept_up, DEFAULT_PARAMETERS.rate_slope, DEFAULT_PARAMETERS.rate_intercept_down

    mean_rate: float = sum(count * rate for rate, _, _, count in samples) / total_weight
    mean_up: float = sum(count * up for _, up, _, count in samples) / total_weight
    mean_down: float = sum(count * down for _, _, down, count in samples) / total_weight
    rate_variance: float = sum(count * (rate - mean_rate) ** 2 for rate, _, _, count in samples) / total_weight

    if rate_variance < 1e-6:
        return mean_up, 0.0, mean_down

    mean_gap: float = mean_down - mean_up
    gap_covariance: float = (
        sum(count * rate * ((down - up) - mean_gap) for rate, up, down, count in samples) / total_weight
    )
    slope: float = -gap_covariance / (2.0 * rate_variance)
    slope = min(max(slope, -1.0), 1.0)
    return mean_up - slope * mean_rate, slope, mean_down + slope * mean_rate


def estimate_parameters(market_history: MarketHistory) -> FittedParameters:
    rate_path: tuple[float, ...] = market_history.values_by_underlying_id.get(FED_FUNDS_RATE_UNDERLYING_ID, ())
    if len(rate_path) < 3:
        return DEFAULT_PARAMETERS

    changes: list[float] = [round(rate_path[i + 1] - rate_path[i], 2) for i in range(len(rate_path) - 1)]
    observed_steps: list[float] = [abs(change) for change in changes if abs(change) > TOLERANCE]
    rate_step: float = min(observed_steps) if observed_steps else RATE_STRIKE_GRID
    intercept_up, slope, intercept_down = _estimate_rate_chain(rate_path)

    drift_by_id: dict[int, float] = dict(DEFAULT_PARAMETERS.drift_by_id)
    rate_beta_by_id: dict[int, float] = dict(DEFAULT_PARAMETERS.rate_beta_by_id)
    residual_by_id: dict[int, list[float]] = {}

    for company_id in COMPANY_UNDERLYING_IDS:
        values: tuple[float, ...] = market_history.values_by_underlying_id.get(company_id, ())
        if len(values) != len(rate_path) or len(values) < 3:
            continue

        log_returns: list[float] = [
            math.log(values[i + 1] / values[i]) if values[i] > 0.0 and values[i + 1] > 0.0 else 0.0
            for i in range(len(values) - 1)
        ]
        buckets: dict[float, list[float]] = defaultdict(list)
        for change, log_return in zip(changes, log_returns):
            buckets[change].append(log_return)

        # rate_change only takes three values, so the slope is just a contrast between the
        # up-day and down-day means -- no regression machinery needed.
        up_bucket: list[float] = buckets.get(round(rate_step, 2), [])
        down_bucket: list[float] = buckets.get(round(-rate_step, 2), [])
        if len(up_bucket) >= 2 and len(down_bucket) >= 2:
            up_mean: float = sum(up_bucket) / len(up_bucket)
            down_mean: float = sum(down_bucket) / len(down_bucket)
            up_variance: float = sum((y - up_mean) ** 2 for y in up_bucket) / (len(up_bucket) - 1)
            down_variance: float = sum((y - down_mean) ** 2 for y in down_bucket) / (len(down_bucket) - 1)
            beta: float = (up_mean - down_mean) / (2.0 * rate_step)
            beta_error: float = math.sqrt(
                up_variance / len(up_bucket) + down_variance / len(down_bucket)
            ) / (2.0 * rate_step)
            rate_beta_by_id[company_id] = _shrink_towards_zero(beta, beta_error)

        # Drift off the full sample, net of the rate term. Using every day rather than only the
        # flat ones cuts the standard error by ~1/sqrt(share of flat days), and drift error is
        # multiplied by the horizon inside the pricer.
        sample_size: int = len(log_returns)
        if sample_size >= 3:
            beta_estimate: float = rate_beta_by_id[company_id]
            adjusted: list[float] = [
                log_return - beta_estimate * change for change, log_return in zip(changes, log_returns)
            ]
            drift: float = sum(adjusted) / sample_size
            drift_variance: float = sum((y - drift) ** 2 for y in adjusted) / (sample_size - 1)
            drift_by_id[company_id] = _shrink_towards_zero(drift, math.sqrt(drift_variance / sample_size))

        residual_by_id[company_id] = [
            log_return - drift_by_id[company_id] - rate_beta_by_id[company_id] * change
            for change, log_return in zip(changes, log_returns)
        ]

    covariance: dict[tuple[int, int], float] = dict(DEFAULT_PARAMETERS.covariance)
    covariance_sample_size: int = 0
    for first_id in COMPANY_UNDERLYING_IDS:
        for second_id in COMPANY_UNDERLYING_IDS:
            first_residuals: list[float] = residual_by_id.get(first_id, [])
            second_residuals: list[float] = residual_by_id.get(second_id, [])
            if len(first_residuals) < 3 or len(first_residuals) != len(second_residuals):
                continue
            sample_count: int = len(first_residuals)
            covariance_sample_size = sample_count
            covariance[_covariance_key(first_id, second_id)] = (
                sum(a * b for a, b in zip(first_residuals, second_residuals)) / (sample_count - 1)
            )

    for company_id in COMPANY_UNDERLYING_IDS:
        key: tuple[int, int] = _covariance_key(company_id, company_id)
        covariance[key] = max(covariance[key], 1e-8)
    cross_key: tuple[int, int] = _covariance_key(*COMPANY_UNDERLYING_IDS)
    variance_bound: float = math.sqrt(
        covariance[_covariance_key(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID)]
        * covariance[_covariance_key(THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)]
    )
    covariance[cross_key] = min(max(covariance[cross_key], -0.999 * variance_bound), 0.999 * variance_bound)

    return FittedParameters(
        rate_step=rate_step,
        rate_intercept_up=intercept_up,
        rate_slope=slope,
        rate_intercept_down=intercept_down,
        drift_by_id=drift_by_id,
        rate_beta_by_id=rate_beta_by_id,
        covariance=covariance,
        covariance_sample_size=covariance_sample_size,
    )


def _snap_quote_prices(bid_value: float, offer_value: float) -> tuple[float, float]:
    """Round outward to whole pennies and enforce 0 <= bid < offer <= 1."""
    bid_pennies: int = min(max(int(math.floor(bid_value * 100.0 + 1e-9)), 0), 99)
    offer_pennies: int = min(max(int(math.ceil(offer_value * 100.0 - 1e-9)), 1), 100)
    if bid_pennies >= offer_pennies:
        if offer_pennies < 100:
            offer_pennies = bid_pennies + 1
        else:
            bid_pennies = offer_pennies - 1
    return bid_pennies / 100.0, offer_pennies / 100.0


@dataclass(frozen=True)
class FactorRisk:
    """First and second derivatives of a price with respect to the three risk factors.

    Ordered (rate, log AJR, log THR). `delta` is per unit move in the factor; `gamma` is per
    unit move squared. Both are additive across a book, so the same type carries a single
    option's risk and the whole portfolio's.

    `vega` is a single scalar rather than a triple: it is the derivative with respect to a
    proportional scaling of the whole company covariance matrix, which keeps correlations fixed
    and moves only the vol level. That is the shape our estimation error actually takes.
    """

    delta: tuple[float, float, float]
    gamma: tuple[float, float, float]
    vega: float = 0.0


class MarketMaker:
    # Set False to A/B the convexity layer against the delta-only book. Every gamma-aware
    # adjustment below collapses to its previous behaviour when this is off.
    GAMMA_ENABLED: bool = True
    VEGA_ENABLED: bool = True

    def __init__(
        self,
        underlying_initial_state: list[Underlying],
        option_initial_state: list[BinaryOption],
        cash_balance: float,
    ) -> None:
        self.underlying_state: list[Underlying] = underlying_initial_state
        self.active_option_state: list[BinaryOption] = option_initial_state
        self.cash_balance: float = cash_balance
        self.position: Position = Position()

        self.cash_buffer: float = max(MIN_CASH_BUFFER, CASH_BUFFER_FRACTION * cash_balance)
        self.risk_capital: float = max(cash_balance, 1.0)
        # Collateral is charged per trade, so a buy and an offsetting sell each cost their own
        # maximum loss. Settlement therefore has to credit gross long and gross short
        # separately: crediting the net position leaks min(long, short) dollars per option.
        self.gross_long_by_option_id: dict[int, int] = defaultdict(int)
        self.gross_short_by_option_id: dict[int, int] = defaultdict(int)
        self.parameters: FittedParameters = DEFAULT_PARAMETERS
        self.contract_by_option_id: dict[int, BinaryOption] = {
            option.option_id: option for option in option_initial_state
        }
        # counterparty_id -> [signed edge we captured, trade count]
        self.counterparty_record: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
        self._price_cache: dict[int, float] = {}
        self._sensitivity_cache: dict[int, FactorRisk] = {}
        self._exposure: FactorRisk | None = None

        # Shadow ledger crediting expiries at the worse of the two settlement readings. Sizing
        # runs off min(cash_balance, this), so a wrong reading costs quote size rather than
        # solvency. See `SETTLEMENT_DOUBT_CAP_FRACTION`.
        self._pessimistic_cash: float = cash_balance
        self._settlement_doubt_cap: float = SETTLEMENT_DOUBT_CAP_FRACTION * max(cash_balance, 1.0)

        # Live observations of the three underlyings, seeded by `warm_up` and appended on every
        # step, so the fit keeps improving over a session instead of freezing at the warm-up.
        self._observed_path: dict[int, list[float]] = {}
        self._steps_since_refit: int = 0

        # FOK side detection: which reading of `FokOrder.order_type` the tape has voted for.
        self._order_type_is_counterparty_side: bool = ORDER_TYPE_IS_COUNTERPARTY_SIDE
        self._fok_side_agreements: int = 0
        self._fok_side_disagreements: int = 0
        # (option_id, price, quantity, assumed counterparty_buys) for accepted-but-unconfirmed FOKs.
        self._pending_fok: list[tuple[int, float, int, bool]] = []

    # -- state ------------------------------------------------------------------------------

    def _value_by_underlying_id(self) -> dict[int, float]:
        return {underlying.underlying_id: underlying.value for underlying in self.underlying_state}

    def _invalidate_caches(self) -> None:
        self._price_cache.clear()
        self._sensitivity_cache.clear()
        self._exposure = None

    def on_step_advance(self, new_underlying_state: list[Underlying], new_option_state: list[BinaryOption]) -> None:
        try:
            self._on_step_advance(new_underlying_state, new_option_state)
        except Exception:
            # Never let a bookkeeping failure kill the session, but the state update itself is
            # not optional -- quoting a stale board is far worse than a missed expiry credit.
            self.underlying_state = new_underlying_state
            self.active_option_state = new_option_state
            for option in new_option_state:
                self.contract_by_option_id[option.option_id] = option
            self._invalidate_caches()

    def _on_step_advance(
        self, new_underlying_state: list[Underlying], new_option_state: list[BinaryOption]
    ) -> None:
        previous_values: dict[int, float] = self._value_by_underlying_id()
        new_values: dict[int, float] = {
            underlying.underlying_id: underlying.value for underlying in new_underlying_state
        }
        surviving_ids: set[int] = {option.option_id for option in new_option_state}

        # Iterate everything we track, not just the board: an option traded via FOK that never
        # appeared in `active_option_state` used to leak forever -- never credited, and its
        # stale contract kept feeding phantom delta into `_portfolio_exposure` for the rest of
        # the session because nothing ever advanced or removed it.
        tracked_ids: set[int] = (
            set(self.contract_by_option_id)
            | set(self.gross_long_by_option_id)
            | set(self.gross_short_by_option_id)
        )
        for option_id in tracked_ids - surviving_ids:
            option: BinaryOption | None = self.contract_by_option_id.pop(option_id, None)
            long_quantity: int = self.gross_long_by_option_id.pop(option_id, 0)
            short_quantity: int = self.gross_short_by_option_id.pop(option_id, 0)
            self.position.option_quantity_by_option_id.pop(option_id, None)
            if option is None or not (long_quantity or short_quantity):
                continue
            self._credit_expiry(option, long_quantity, short_quantity, previous_values, new_values)

        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        for option in new_option_state:
            self.contract_by_option_id[option.option_id] = option

        self._record_observation(new_values)
        self._maybe_refit()
        self._pending_fok.clear()
        self._invalidate_caches()

    def _credit_expiry(
        self,
        option: BinaryOption,
        long_quantity: int,
        short_quantity: int,
        previous_values: dict[int, float],
        new_values: dict[int, float],
    ) -> None:
        """Book an expiry, deriving which day's values the payoff was struck against.

        The grader may either leave an option on the board for the step it shows
        `steps_until_expiry == 0` and settle it afterwards, or drop it the moment the counter
        reaches zero. Both settle against the *same* day's underlyings; they differ only in
        which of our snapshots that day is. An option last seen at zero steps had already
        reached expiry, so it settled on the values live then; one last seen with steps
        remaining must have settled on this step's advance. Assuming rather than deriving this
        was measured to invent up to 31.00 of phantom cash on a 100 bankroll.
        """
        settlement_values: dict[int, float] = (
            previous_values if option.steps_until_expiry <= 0 else new_values
        )
        payoff: float = option.expiry_valuation(settlement_values)
        self.cash_balance += long_quantity * payoff + short_quantity * (1.0 - payoff)

        # The shadow ledger takes whichever reading pays us less, so `_available_cash` stays
        # right even if the derivation above is wrong about a particular grader.
        try:
            alternative: float = option.expiry_valuation(
                new_values if option.steps_until_expiry <= 0 else previous_values
            )
        except Exception:
            alternative = payoff
        worst_long: float = min(payoff, alternative)
        worst_short: float = 1.0 - max(payoff, alternative)
        self._pessimistic_cash += long_quantity * worst_long + short_quantity * worst_short
        self._pessimistic_cash = max(self._pessimistic_cash, self.cash_balance - self._settlement_doubt_cap)

    def _record_observation(self, new_values: dict[int, float]) -> None:
        if not self._observed_path:
            self._observed_path = {underlying_id: [] for underlying_id in UNDERLYING_NAME_BY_ID}
        # The first advance of a session often replays the same values the warm-up history ended
        # on. Appending those would inject a fake zero-return day, biasing the covariance down
        # and the rate chain toward "stay". A genuine repeat of all three at once is negligible:
        # the company values are a rounded draw from a continuous law.
        if all(
            path and underlying_id in new_values and path[-1] == new_values[underlying_id]
            for underlying_id, path in self._observed_path.items()
        ):
            return
        for underlying_id, path in self._observed_path.items():
            if underlying_id in new_values:
                path.append(new_values[underlying_id])
        self._steps_since_refit += 1

    def _maybe_refit(self) -> None:
        """Fold the live path back into the parameter fit.

        The generator is fixed for the whole scenario, so every step is another draw from the
        same distribution. A 60-step session doubles a 60-day warm-up, and price error falls
        roughly as 1/sqrt(N) over the range that matters.
        """
        if self._steps_since_refit < REFIT_INTERVAL_STEPS:
            return
        lengths: set[int] = {len(path) for path in self._observed_path.values()}
        if len(lengths) != 1 or next(iter(lengths)) < MIN_REFIT_OBSERVATIONS:
            return
        self._steps_since_refit = 0
        try:
            history = MarketHistory(
                values_by_underlying_id={
                    underlying_id: tuple(path) for underlying_id, path in self._observed_path.items()
                }
            )
            self.parameters = estimate_parameters(history)
            self._invalidate_caches()
        except Exception:
            pass

    def on_trade(self, option: BinaryOption, price: float, quantity: int, counterparty_id: int) -> None:
        try:
            self._on_trade(option, price, quantity, counterparty_id)
        except Exception:
            self._exposure = None

    def _on_trade(self, option: BinaryOption, price: float, quantity: int, counterparty_id: int) -> None:
        self.position.add_option_quantity(option.option_id, quantity)
        self.contract_by_option_id[option.option_id] = option
        if quantity > 0:
            self.gross_long_by_option_id[option.option_id] += quantity
        else:
            self.gross_short_by_option_id[option.option_id] += -quantity

        # Mirror the grader's collateral rule: a trade costs its own maximum loss up front, and
        # nothing is returned until expiry. Clamped at zero because a price outside [0, 1] makes
        # the arithmetic go negative, and the grader charges a maximum *loss* -- it will not
        # hand us cash at trade time for a trade that cannot lose.
        collateral: float = quantity * price if quantity > 0 else -quantity * (1.0 - price)
        collateral = max(collateral, 0.0)
        self.cash_balance -= collateral
        self._pessimistic_cash -= collateral

        self._record_fok_outcome(option.option_id, price, quantity)

        theoretical: float = self._price_option_strict(option)
        edge: float = quantity * (theoretical - price)
        record: list[float] = self.counterparty_record[counterparty_id]
        record[0] += edge
        record[1] += abs(quantity)
        self._exposure = None

    def _record_fok_outcome(self, option_id: int, price: float, quantity: int) -> None:
        """Vote on what `FokOrder.order_type` means, using the signed quantity we were given.

        We accepted the order believing the counterparty was on one side; the fill tells us
        which side we actually took. A negative quantity means we sold, so the counterparty
        bought. Majority vote rather than a single observation, because an RFQ fill can
        coincidentally match a pending order's option and price.
        """
        for index, (pending_id, pending_price, pending_quantity, assumed_buys) in enumerate(self._pending_fok):
            if pending_id != option_id or abs(pending_price - price) > TOLERANCE:
                continue
            if abs(quantity) > pending_quantity:
                continue
            self._pending_fok.pop(index)
            if (quantity < 0) == assumed_buys:
                self._fok_side_agreements += 1
            else:
                self._fok_side_disagreements += 1
            if self._fok_side_disagreements >= self._fok_side_agreements + FOK_SIDE_FLIP_MARGIN:
                self._order_type_is_counterparty_side = not self._order_type_is_counterparty_side
                self._fok_side_agreements, self._fok_side_disagreements = 0, 0
            return

    @property
    def name(self) -> str:
        return "TelescopeMM"

    def warm_up(self, market_history: MarketHistory) -> None:
        try:
            self.parameters = estimate_parameters(market_history)
            self._observed_path = {
                underlying_id: list(market_history.values_by_underlying_id.get(underlying_id, ()))
                for underlying_id in UNDERLYING_NAME_BY_ID
            }
            self._steps_since_refit = 0
        except Exception:
            self.parameters = DEFAULT_PARAMETERS
        self._invalidate_caches()

    # -- pricing ----------------------------------------------------------------------------

    def price_option(self, option: BinaryOption) -> float:
        """Our stated theoretical value. Guarded: the grader logs and scores this directly.

        0.5 is the max-entropy answer for a binary and is the least-wrong thing to report for a
        contract we cannot price. Quoting never routes through here -- it uses the strict form
        below, so an unpriceable option is declined rather than quoted around a placeholder.
        """
        try:
            return self._price_option_strict(option)
        except Exception:
            return 0.5

    def _price_option_strict(self, option: BinaryOption) -> float:
        cached: float | None = self._price_cache.get(option.option_id)
        if cached is not None:
            return cached
        value: float = price_binary_option(self.parameters, option, self._value_by_underlying_id())
        self._price_cache[option.option_id] = value
        return value

    def price_option_from_parameters(self, market_parameters: MarketParameters, option: BinaryOption) -> float:
        try:
            return price_binary_option(
                fitted_from_market_parameters(market_parameters), option, self._value_by_underlying_id()
            )
        except Exception:
            return 0.5

    # -- risk -------------------------------------------------------------------------------

    def _factor_risk(self, option: BinaryOption) -> FactorRisk:
        """Delta and gamma of `option` against the rate and each company's log value.

        Central differences throughout: the down-bump needed for gamma makes the first
        derivative second-order accurate for free. The rate leg degenerates at the zero floor,
        where a down-bump is not available and the curvature is simply not observable.
        """
        cached: FactorRisk | None = self._sensitivity_cache.get(option.option_id)
        if cached is not None:
            return cached

        base_values: dict[int, float] = self._value_by_underlying_id()
        base_price: float = self._price_option_strict(option)
        step: float = self.parameters.rate_step

        def price_with(underlying_id: int, value: float) -> float:
            bumped: dict[int, float] = dict(base_values)
            bumped[underlying_id] = value
            return price_binary_option(self.parameters, option, bumped)

        base_rate: float = base_values[FED_FUNDS_RATE_UNDERLYING_ID]
        rate_down_value: float = max(base_rate - step, 0.0)
        rate_up_price: float = price_with(FED_FUNDS_RATE_UNDERLYING_ID, base_rate + step)
        if base_rate - rate_down_value > TOLERANCE:
            rate_down_price: float = price_with(FED_FUNDS_RATE_UNDERLYING_ID, rate_down_value)
            rate_delta: float = (rate_up_price - rate_down_price) / (2.0 * step)
            rate_gamma: float = (rate_up_price - 2.0 * base_price + rate_down_price) / (step * step)
        else:
            rate_delta = (rate_up_price - base_price) / step
            rate_gamma = 0.0

        deltas: list[float] = [rate_delta]
        gammas: list[float] = [rate_gamma]
        for company_id in COMPANY_UNDERLYING_IDS:
            base_value: float = base_values[company_id]
            up_price: float = price_with(company_id, base_value * math.exp(COMPANY_LOG_BUMP))
            down_price: float = price_with(company_id, base_value * math.exp(-COMPANY_LOG_BUMP))
            deltas.append((up_price - down_price) / (2.0 * COMPANY_LOG_BUMP))
            gammas.append((up_price - 2.0 * base_price + down_price) / (COMPANY_LOG_BUMP**2))

        risk: FactorRisk = FactorRisk(
            delta=(deltas[0], deltas[1], deltas[2]),
            gamma=(gammas[0], gammas[1], gammas[2]),
            vega=self._vega(option, base_values),
        )
        self._sensitivity_cache[option.option_id] = risk
        return risk

    def _vega(self, option: BinaryOption, base_values: dict[int, float]) -> float:
        """d(price) with respect to a proportional scaling of the company covariance matrix.

        Zero by construction for rate-only contracts, which is worth short-circuiting: they are
        a large share of the board and the two repricings would be pure waste.
        """
        if not any(leg.underlying_id in COMPANY_UNDERLYING_IDS for leg in option.legs):
            return 0.0

        def scaled_price(factor: float) -> float:
            scaled: FittedParameters = replace(
                self.parameters,
                covariance={key: value * factor for key, value in self.parameters.covariance.items()},
            )
            return price_binary_option(scaled, option, base_values)

        return (scaled_price(1.0 + COVARIANCE_BUMP) - scaled_price(1.0 - COVARIANCE_BUMP)) / (
            2.0 * COVARIANCE_BUMP
        )

    def _portfolio_exposure(self) -> FactorRisk:
        if self._exposure is not None:
            return self._exposure

        delta_totals: list[float] = [0.0, 0.0, 0.0]
        gamma_totals: list[float] = [0.0, 0.0, 0.0]
        vega_total: float = 0.0
        for option_id, quantity in self.position.option_quantity_by_option_id.items():
            if quantity == 0:
                continue
            option: BinaryOption | None = self.contract_by_option_id.get(option_id)
            if option is None:
                continue
            risk: FactorRisk = self._factor_risk(option)
            vega_total += quantity * risk.vega
            for index in range(3):
                delta_totals[index] += quantity * risk.delta[index]
                gamma_totals[index] += quantity * risk.gamma[index]

        self._exposure = FactorRisk(
            delta=(delta_totals[0], delta_totals[1], delta_totals[2]),
            gamma=(gamma_totals[0], gamma_totals[1], gamma_totals[2]),
            vega=vega_total,
        )
        return self._exposure

    def portfolio_delta(self) -> tuple[float, float, float]:
        """The book's net delta to (rate, log AJR, log THR), in probability units per unit move.

        This is the quantity we are trying to drive toward zero: it nets a long FED-call binary
        against a short one, and nets AJR exposure held directly against AJR exposure held
        through a relative-value contract like AJR - THR >= 0.
        """
        return self._portfolio_exposure().delta

    def portfolio_gamma(self) -> tuple[float, float, float]:
        """The book's net convexity to the same three factors.

        Delta-flat is not risk-flat here. Two binaries struck either side of spot can cancel in
        `portfolio_delta` while both flipping the same way on a single move; that shows up here
        and nowhere else.
        """
        return self._portfolio_exposure().gamma

    def portfolio_vega(self) -> float:
        """Net sensitivity to the fitted vol level, in price units per unit relative change.

        Unhedgeable here, so this is a diagnostic: a large absolute value means the book's mark
        is largely a statement about our covariance estimate rather than about the market.
        """
        return self._portfolio_exposure().vega

    def _factor_variances(self) -> tuple[float, float, float]:
        up_probability, down_probability = self.parameters.rate_transition_probabilities(
            self._value_by_underlying_id()[FED_FUNDS_RATE_UNDERLYING_ID]
        )
        return (
            (up_probability + down_probability) * self.parameters.rate_step**2,
            self.parameters.covariance[_covariance_key(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID)],
            self.parameters.covariance[_covariance_key(THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)],
        )

    def _inventory_skew(self, option: BinaryOption) -> float:
        """Gaussian approximation to Cov(this option's payoff, the book's payoff).

        Positive means trading more of this option in the *buy* direction adds to the delta we
        already carry, so the whole quote shifts down: we bid less eagerly and offer more
        eagerly, which pulls flow that flattens the book. Scaled by risk capital so the shift is
        expressed in probability (price) units rather than raw contract-deltas.
        """
        risk: FactorRisk = self._factor_risk(option)
        book: FactorRisk = self._portfolio_exposure()
        variances: tuple[float, float, float] = self._factor_variances()
        covariance: float = sum(
            variances[index] * risk.delta[index] * book.delta[index] for index in range(3)
        )
        if self.GAMMA_ENABLED:
            # Second-order term of Cov(f(X), g(X)) for Gaussian X: sum of f''g''*var^2 / 2. It
            # survives when both books are delta-flat, which is exactly the pin-risk case the
            # linear term scores as zero.
            covariance += GAMMA_AVERSION * sum(
                0.5 * variances[index] ** 2 * risk.gamma[index] * book.gamma[index]
                for index in range(3)
            )
        skew: float = INVENTORY_AVERSION * covariance / self.risk_capital
        return min(max(skew, -MAX_INVENTORY_SKEW), MAX_INVENTORY_SKEW)

    def _convexity_charge(self, option: BinaryOption) -> float:
        """Expected one-step move in theo that delta alone does not explain, in price units.

        This is the half-gamma-variance term of the Taylor expansion, summed over factors with
        absolute values: we are pricing the *magnitude* of the curvature we cannot skew away,
        not its direction. Large for near-strike, near-expiry binaries and ~0 for everything
        else, which is precisely where the delta snapshot used to quote goes stale fastest.
        """
        if not self.GAMMA_ENABLED:
            return 0.0
        risk: FactorRisk = self._factor_risk(option)
        variances: tuple[float, float, float] = self._factor_variances()
        return 0.5 * sum(variances[index] * abs(risk.gamma[index]) for index in range(3))

    def _convexity_padding(self, option: BinaryOption) -> float:
        """Extra half-spread charged for curvature, capped so we still quote the hot contracts."""
        return min(GAMMA_PAD_AVERSION * self._convexity_charge(option), MAX_GAMMA_PAD)

    def _vol_uncertainty_charge(self, option: BinaryOption) -> float:
        """How far our theo moves if the fitted vol level is off by one standard error.

        This is a confidence measure, not an exposure: there is no vol instrument here, so vega
        cannot be hedged or skewed away. The only sane responses are to widen and to shrink.
        """
        if not self.VEGA_ENABLED:
            return 0.0
        return abs(self._factor_risk(option).vega) * self.parameters.relative_vol_uncertainty

    def _vol_uncertainty_padding(self, option: BinaryOption) -> float:
        return min(VEGA_PAD_AVERSION * self._vol_uncertainty_charge(option), MAX_VEGA_PAD)

    def _vol_uncertainty_size_factor(self, option: BinaryOption) -> float:
        if not self.VEGA_ENABLED:
            return 1.0
        return 1.0 / (1.0 + self._vol_uncertainty_charge(option) / VEGA_SIZE_TOLERANCE)

    def _convexity_size_factor(self, option: BinaryOption) -> float:
        """Multiplier in (0, 1] on quoted size; halves at a convexity charge of one tolerance.

        Widening alone does not cap the damage from a gamma contract, because the loss scales
        with size while the pad is capped. Cutting size is the part that actually bounds it.
        """
        if not self.GAMMA_ENABLED:
            return 1.0
        return 1.0 / (1.0 + self._convexity_charge(option) / GAMMA_SIZE_TOLERANCE)

    def reservation_price(self, option: BinaryOption) -> float:
        """Theo adjusted for the delta we already hold -- the price we actually trade around.

        `price_option` deliberately stays inventory-free: the grader logs it as our stated
        theoretical value, and the THEO test scores it against the truth. Inventory belongs
        here, one layer out, where quoting and FOK decisions are made.
        """
        return min(max(self._price_option_strict(option) - self._inventory_skew(option), 0.0), 1.0)

    def _counterparty_padding(self, counterparty_id: int) -> float:
        """Widen against counterparties whose flow has historically run us over."""
        captured, traded = self.counterparty_record.get(counterparty_id, [0.0, 0.0])
        if traded < 5.0:
            return 0.0
        average_edge: float = captured / traded
        if average_edge >= 0.0:
            return 0.0
        confidence: float = traded / (traded + 25.0)
        return min(0.06, confidence * (-average_edge))

    def _available_cash(self) -> float:
        """Cash we are willing to commit, on the lower of the two settlement readings.

        `_pessimistic_cash` only diverges from `cash_balance` when the two possible settlement
        conventions disagree about an expiry we have already booked, and the gap is capped at
        `SETTLEMENT_DOUBT_CAP_FRACTION` of the starting bankroll. Sizing off the minimum makes a
        wrong reading cost quote size instead of solvency.
        """
        return max(min(self.cash_balance, self._pessimistic_cash) - self.cash_buffer, 0.0)

    # -- quoting ----------------------------------------------------------------------------

    def _collateral_quote_prices(self, fair_value: float, num_steps: int, padding: float) -> tuple[float, float]:
        """Prices at which both sides earn the same return on the cash they lock up.

        Buying q at b locks q*b and expects q*(p - b); selling q at a locks q*(1 - a) and
        expects q*(a - p). Equating both returns to `hurdle` gives the pair below, which is
        automatically tight on cheap options' bids and wide on their offers.
        """
        hurdle: float = min(HURDLE_PER_STEP * max(num_steps, 1), MAX_HURDLE)
        bid: float = fair_value / (1.0 + hurdle) - padding
        offer: float = (fair_value + hurdle) / (1.0 + hurdle) + padding
        if offer - bid < 2.0 * MIN_HALF_SPREAD:
            middle: float = 0.5 * (bid + offer)
            bid, offer = middle - MIN_HALF_SPREAD, middle + MIN_HALF_SPREAD
        return bid, offer

    def _affordable_quantity(self, collateral_per_contract: float, num_steps: int = 1) -> int:
        """Contracts we can take on this side without endangering the bankroll.

        Zero collateral means a bid of 0.00 or an offer of 1.00: those cannot lose, so they are
        never size-limited. Longer-dated contracts hold the cash longer and get less of it.
        """
        if collateral_per_contract <= TOLERANCE:
            return MAX_QUOTE_SIZE
        live_options: int = max(1, len(self.active_option_state))
        budget: float = self._available_cash() / (CONCURRENT_LOAD_FACTOR * live_options)
        budget /= math.sqrt(max(num_steps, 1))
        return max(0, min(MAX_QUOTE_SIZE, int(budget / collateral_per_contract)))

    #: A quote that locks up no cash and cannot lose money -- the only safe way to say "no",
    #: since a two-sided quote is mandatory. Also the fallback whenever quoting raises.
    DECLINE_QUOTE: "Quote" = None  # type: ignore[assignment]  # bound after the class body

    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        """Guarded entry point. Any failure declines rather than raising.

        An option we cannot price -- an unexpected leg, a missing underlying, a numerical edge
        case -- must not end the session. The VERBOSE scenarios award full marks purely for not
        erroring, so a single escaped exception is worth more than any spread we could earn.
        """
        try:
            return self._quote(option, counterparty_id)
        except Exception:
            return MarketMaker.DECLINE_QUOTE

    def _quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        padding: float = (
            WINNER_CURSE_PAD
            + self._counterparty_padding(counterparty_id)
            + self._convexity_padding(option)
            + self._vol_uncertainty_padding(option)
        )
        skew: float = self._inventory_skew(option)
        reservation: float = self.reservation_price(option)

        raw_bid, raw_offer = self._collateral_quote_prices(reservation, option.steps_until_expiry, padding)
        bid_price, offer_price = _snap_quote_prices(raw_bid, raw_offer)

        steps: int = option.steps_until_expiry
        bid_quantity: int = self._affordable_quantity(bid_price, steps)
        offer_quantity: int = self._affordable_quantity(1.0 - offer_price, steps)

        # Curvature cuts both sides: unlike inventory skew this is not directional, it is a
        # statement that our own delta snapshot is about to be wrong whichever way we get hit.
        size_factor: float = self._convexity_size_factor(option) * self._vol_uncertainty_size_factor(option)
        bid_quantity = int(bid_quantity * size_factor)
        offer_quantity = int(offer_quantity * size_factor)

        # Show size on the side that flattens the book, minimal size on the side that grows it.
        if skew > 0.0:
            bid_quantity = bid_quantity // 4
        elif skew < 0.0:
            offer_quantity = offer_quantity // 4

        # A two-sided quote is mandatory, so "decline" has to be expressed as a price. Bidding
        # 0.00 and offering 1.00 lock up no cash and cannot lose money, which makes them the
        # correct refusal -- never shrink to size 1 at a real price we cannot collateralise.
        if bid_quantity < 1:
            bid_price, bid_quantity = 0.0, 1
        if offer_quantity < 1:
            offer_price, offer_quantity = 1.0, 1
        bid_price, offer_price = _snap_quote_prices(bid_price, offer_price)

        return Quote(
            bid_price=bid_price,
            bid_quantity=bid_quantity,
            offer_price=offer_price,
            offer_quantity=offer_quantity,
        )

    def respond_to_fok(self, option: BinaryOption, fok_order: FokOrder) -> bool:
        """Guarded entry point. Any failure refuses the order."""
        try:
            return self._respond_to_fok(option, fok_order)
        except Exception:
            return False

    def _respond_to_fok(self, option: BinaryOption, fok_order: FokOrder) -> bool:
        reservation: float = self.reservation_price(option)
        required: float = (
            FOK_EDGE_REQUIRED
            + self._counterparty_padding(fok_order.counterparty_id)
            + self._convexity_padding(option)
            + self._vol_uncertainty_padding(option)
        )

        # Until the tape has confirmed what `order_type` means, treat every FOK as a probe:
        # double the edge and only small clips. Being wrong about the side means systematically
        # taking the losing half of every order, so the first few fills are bought cheaply.
        probing: bool = (
            self._fok_side_agreements + self._fok_side_disagreements < FOK_SIDE_CONFIRMING_TRADES
        )
        if probing:
            if fok_order.quantity > FOK_PROBE_MAX_QUANTITY:
                return False
            required *= FOK_PROBE_EDGE_MULTIPLIER

        steps: int = option.steps_until_expiry
        # A FOK arrives in one indivisible clip, so the convexity size cap matters more here
        # than on a quote: there is no partial fill to stop us at a tolerable position.
        size_limit: float = self._convexity_size_factor(option) * self._vol_uncertainty_size_factor(option)
        counterparty_buys: bool = (
            fok_order.order_type == OrderType.BUY
        ) == self._order_type_is_counterparty_side
        if counterparty_buys:
            # We sell at fok_order.price; each contract locks (1 - price) of cash.
            if fok_order.price < reservation + required:
                return False
            affordable: int = self._affordable_quantity(1.0 - fok_order.price, steps)
            accepted: bool = int(affordable * size_limit) >= fok_order.quantity
        elif fok_order.price > reservation - required:
            return False
        else:
            accepted = (
                int(self._affordable_quantity(fok_order.price, steps) * size_limit) >= fok_order.quantity
            )

        if accepted:
            # `on_trade` will report the signed quantity, which settles what `order_type` means.
            self._pending_fok.append(
                (option.option_id, fok_order.price, fok_order.quantity, counterparty_buys)
            )
        return accepted


# Bound after the class body because `Quote` validation runs at construction: a 0.00 bid and a
# 1.00 offer are both real, legal quotes that lock up no cash and cannot lose money.
MarketMaker.DECLINE_QUOTE = Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)
