COMPANY_UNDERLYING_IDS = (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)
TOLERANCE = 1e-09
HURDLE_PER_STEP = 0.012
MAX_HURDLE = 0.18
MIN_HALF_SPREAD = 0.01
WINNER_CURSE_PAD = 0.008
INVENTORY_AVERSION = 1.5
MAX_INVENTORY_SKEW = 0.25
MAX_QUOTE_SIZE = 40
MIN_LOSS_PROBABILITY = 0.05
TARGET_FILL_RATE = 0.35
GENEROSITY_AVERSION = 0.2
MAX_GENEROSITY_PAD = 0.05
MIN_QUOTES_FOR_FILL_RATE = 20.0
INVENTORY_SIZE_SHRINK = 0.25
GAMMA_AVERSION = 0.0
GAMMA_PAD_AVERSION = 0.25
MAX_GAMMA_PAD = 0.015
GAMMA_SIZE_TOLERANCE = 0.1
COMPANY_LOG_BUMP = 0.01
VOL_RELATIVE_UNCERTAINTY = 0.1
MIN_VOL_RELATIVE_UNCERTAINTY = 0.05
MAX_VOL_RELATIVE_UNCERTAINTY = 0.5
COVARIANCE_BUMP = 0.1
VEGA_PAD_AVERSION = 1.0
MAX_VEGA_PAD = 0.01
VEGA_SIZE_TOLERANCE = 0.025
MAX_MODEL_PADDING = 0.012
MIN_SIZE_FACTOR = 0.25
REFIT_INTERVAL_STEPS = 5
MIN_REFIT_OBSERVATIONS = 30
CONCURRENT_LOAD_FACTOR = 2.5
CASH_BUFFER_FRACTION = 0.1
MIN_CASH_BUFFER = 2.0
FOK_EDGE_REQUIRED = 0.015
ORDER_TYPE_IS_COUNTERPARTY_SIDE = True
ORDER_TYPE_SIDE_CONFIRMED = True
FOK_SIDE_CONFIRMING_TRADES = 3
FOK_SIDE_FLIP_MARGIN = 2
FOK_PROBE_EDGE_MULTIPLIER = 2.0
FOK_PROBE_CASH_FRACTION = 0.05
SETTLEMENT_DOUBT_CAP_FRACTION = 0.25
SEQUENTIAL_CONFIRMING_FILLS = 4

def _norm_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))

def _norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))

def _gauss_legendre(num_nodes):
    nodes = []
    weights = []
    for index in range(1, num_nodes + 1):
        x = math.cos(math.pi * (index - 0.25) / (num_nodes + 0.5))
        derivative = 1.0
        for _ in range(100):
            legendre, previous = (1.0, 0.0)
            for degree in range(1, num_nodes + 1):
                legendre, previous = (((2 * degree - 1) * x * legendre - (degree - 1) * previous) / degree, legendre)
            derivative = num_nodes * (x * legendre - previous) / (x * x - 1.0)
            adjustment = -legendre / derivative
            x += adjustment
            if abs(adjustment) < 1e-15:
                break
        nodes.append(x)
        weights.append(2.0 / ((1.0 - x * x) * derivative * derivative))
    return (tuple(nodes), tuple(weights))

def _standard_normal_quadrature(num_nodes, limit=8.0):
    raw_nodes, raw_weights = _gauss_legendre(num_nodes)
    scale = 1.0 / math.sqrt(2.0 * math.pi)
    return tuple(((limit * node, weight * limit * scale * math.exp(-0.5 * (limit * node) ** 2)) for node, weight in zip(raw_nodes, raw_weights)))
NORMAL_QUADRATURE = _standard_normal_quadrature(48)

def _covariance_key(first_id, second_id):
    return (first_id, second_id) if first_id <= second_id else (second_id, first_id)

@dataclass(frozen=True)
class FittedParameters:
    rate_step: float
    rate_intercept_up: float
    rate_slope: float
    rate_intercept_down: float
    drift_by_id: dict[int, float]
    rate_beta_by_id: dict[int, float]
    covariance: dict[tuple[int, int], float]
    covariance_sample_size: int = 0

    @property
    def relative_vol_uncertainty(self):
        if self.covariance_sample_size < 2:
            return VOL_RELATIVE_UNCERTAINTY
        return min(max(math.sqrt(2.0 / self.covariance_sample_size), MIN_VOL_RELATIVE_UNCERTAINTY), MAX_VOL_RELATIVE_UNCERTAINTY)

    def rate_transition_probabilities(self, rate_value):
        up_probability = min(max(self.rate_intercept_up + self.rate_slope * rate_value, 0.0), 1.0)
        down_probability = min(max(self.rate_intercept_down - self.rate_slope * rate_value, 0.0), 1.0 - up_probability)
        return (up_probability, down_probability)

    def next_rate_value(self, rate_value, num_grid_steps):
        return max(round(rate_value + num_grid_steps * self.rate_step, 2), 0.0)
DEFAULT_PARAMETERS = FittedParameters(rate_step=RATE_STRIKE_GRID, rate_intercept_up=0.3 + 0.1 * 2.0, rate_slope=-0.1, rate_intercept_down=0.3 - 0.1 * 2.0, drift_by_id={AJARAI_UNDERLYING_ID: 0.0, THERIODIC_UNDERLYING_ID: 0.0}, rate_beta_by_id={AJARAI_UNDERLYING_ID: -0.3, THERIODIC_UNDERLYING_ID: -0.3}, covariance={(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID): 0.01, (THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.01, (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): 0.004})

def fitted_from_market_parameters(market_parameters):
    reversion = market_parameters.rate_reversion_strength
    target = market_parameters.rate_target
    sector_variance = market_parameters.sector_std_dev ** 2
    return FittedParameters(rate_step=market_parameters.rate_step, rate_intercept_up=market_parameters.rate_up_probability + reversion * target, rate_slope=-reversion, rate_intercept_down=market_parameters.rate_down_probability - reversion * target, drift_by_id={AJARAI_UNDERLYING_ID: market_parameters.ajarai_drift, THERIODIC_UNDERLYING_ID: market_parameters.theriodic_drift}, rate_beta_by_id={AJARAI_UNDERLYING_ID: market_parameters.ajarai_rate_beta, THERIODIC_UNDERLYING_ID: market_parameters.theriodic_rate_beta}, covariance={(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID): market_parameters.ajarai_sector_beta ** 2 * sector_variance + market_parameters.ajarai_idio_std_dev ** 2, (THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): market_parameters.theriodic_sector_beta ** 2 * sector_variance + market_parameters.theriodic_idio_std_dev ** 2, (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID): market_parameters.ajarai_sector_beta * market_parameters.theriodic_sector_beta * sector_variance}, covariance_sample_size=1000000000)

@lru_cache(maxsize=8192)
def _terminal_rate_distribution(rate_step, rate_intercept_up, rate_slope, rate_intercept_down, initial_rate, num_steps):
    distribution = {initial_rate: 1.0}
    for _ in range(num_steps):
        updated = defaultdict(float)
        for rate_value, probability in distribution.items():
            up_probability = min(max(rate_intercept_up + rate_slope * rate_value, 0.0), 1.0)
            down_probability = min(max(rate_intercept_down - rate_slope * rate_value, 0.0), 1.0 - up_probability)
            stay_probability = max(0.0, 1.0 - up_probability - down_probability)
            if up_probability > 0.0:
                updated[max(round(rate_value + rate_step, 2), 0.0)] += probability * up_probability
            if down_probability > 0.0:
                updated[max(round(rate_value - rate_step, 2), 0.0)] += probability * down_probability
            if stay_probability > 0.0:
                updated[rate_value] += probability * stay_probability
        distribution = dict(updated)
    return tuple(distribution.items())

def terminal_rate_distribution(parameters, initial_rate, num_steps):
    return dict(_terminal_rate_distribution(parameters.rate_step, parameters.rate_intercept_up, parameters.rate_slope, parameters.rate_intercept_down, initial_rate, num_steps))

def _weighted_lognormal_at_least(weight, scale, mean, std_dev, threshold):
    if scale <= 0.0:
        return 1.0 if weight * scale >= threshold else 0.0
    bound = threshold / weight
    if weight > 0.0:
        if bound <= 0.0:
            return 1.0
        target = math.log(bound / scale)
        if std_dev <= 0.0:
            return 1.0 if mean >= target else 0.0
        return _norm_sf((target - mean) / std_dev)
    if bound <= 0.0:
        return 0.0
    target = math.log(bound / scale)
    if std_dev <= 0.0:
        return 1.0 if mean <= target else 0.0
    return _norm_cdf((target - mean) / std_dev)

def _conditional_company_probability(parameters, weight_by_id, value_by_underlying_id, num_steps, rate_change, threshold):
    company_ids = sorted(weight_by_id)
    scale_by_id = {}
    for company_id in company_ids:
        drift = parameters.drift_by_id[company_id]
        rate_beta = parameters.rate_beta_by_id[company_id]
        scale_by_id[company_id] = value_by_underlying_id[company_id] * math.exp(num_steps * drift + rate_beta * rate_change)
    if len(company_ids) == 1:
        only_id = company_ids[0]
        variance = num_steps * parameters.covariance[_covariance_key(only_id, only_id)]
        return _weighted_lognormal_at_least(weight_by_id[only_id], scale_by_id[only_id], 0.0, math.sqrt(max(variance, 0.0)), threshold)
    first_id, second_id = company_ids
    first_variance = num_steps * parameters.covariance[_covariance_key(first_id, first_id)]
    second_variance = num_steps * parameters.covariance[_covariance_key(second_id, second_id)]
    cross_covariance = num_steps * parameters.covariance[_covariance_key(first_id, second_id)]
    first_weight = weight_by_id[first_id]
    second_weight = weight_by_id[second_id]
    if abs(threshold) < TOLERANCE and first_weight * second_weight < 0.0:
        difference_variance = first_variance + second_variance - 2.0 * cross_covariance
        log_ratio_target = math.log(abs(second_weight) / abs(first_weight)) - math.log(scale_by_id[first_id] / scale_by_id[second_id])
        if difference_variance <= 0.0:
            return 1.0 if -log_ratio_target >= 0.0 else 0.0
        standardized = log_ratio_target / math.sqrt(difference_variance)
        return _norm_sf(standardized) if first_weight > 0.0 else _norm_cdf(standardized)
    if first_variance <= 0.0:
        return _weighted_lognormal_at_least(second_weight, scale_by_id[second_id], 0.0, math.sqrt(max(second_variance, 0.0)), threshold - first_weight * scale_by_id[first_id])
    first_std_dev = math.sqrt(first_variance)
    conditional_slope = cross_covariance / first_variance
    conditional_std_dev = math.sqrt(max(second_variance - cross_covariance ** 2 / first_variance, 0.0))
    total = 0.0
    for node, node_weight in NORMAL_QUADRATURE:
        shock = node * first_std_dev
        residual_threshold = threshold - first_weight * scale_by_id[first_id] * math.exp(shock)
        total += node_weight * _weighted_lognormal_at_least(second_weight, scale_by_id[second_id], conditional_slope * shock, conditional_std_dev, residual_threshold)
    return total

def price_binary_option(parameters, option, value_by_underlying_id):
    if option.steps_until_expiry <= 0:
        return option.expiry_valuation(value_by_underlying_id)
    weight_by_id = {leg.underlying_id: leg.weight for leg in option.legs}
    rate_weight = weight_by_id.pop(FED_FUNDS_RATE_UNDERLYING_ID, 0.0)
    initial_rate = value_by_underlying_id[FED_FUNDS_RATE_UNDERLYING_ID]
    distribution = _terminal_rate_distribution(parameters.rate_step, parameters.rate_intercept_up, parameters.rate_slope, parameters.rate_intercept_down, initial_rate, option.steps_until_expiry)
    if not weight_by_id:
        return sum((probability for rate_value, probability in distribution if rate_weight * rate_value >= option.strike - TOLERANCE))
    total = 0.0
    for rate_value, probability in distribution:
        if probability <= 0.0:
            continue
        total += probability * _conditional_company_probability(parameters, weight_by_id, value_by_underlying_id, option.steps_until_expiry, rate_value - initial_rate, option.strike - rate_weight * rate_value)
    return min(max(total, 0.0), 1.0)

def _shrink_towards_zero(estimate, standard_error):
    if standard_error <= 0.0:
        return estimate
    signal_to_noise = estimate / standard_error
    return estimate * (signal_to_noise ** 2 / (1.0 + signal_to_noise ** 2))

def _estimate_rate_chain(rate_path):
    counts = defaultdict(lambda: [0, 0, 0])
    for index in range(len(rate_path) - 1):
        change = round(rate_path[index + 1] - rate_path[index], 2)
        bucket = counts[rate_path[index]]
        bucket[2] += 1
        if change > TOLERANCE:
            bucket[0] += 1
        elif change < -TOLERANCE:
            bucket[1] += 1
    samples = [(rate_value, bucket[0] / bucket[2], bucket[1] / bucket[2], bucket[2]) for rate_value, bucket in counts.items() if rate_value > TOLERANCE and bucket[2] > 0]
    total_weight = sum((sample[3] for sample in samples))
    if total_weight == 0:
        return (DEFAULT_PARAMETERS.rate_intercept_up, DEFAULT_PARAMETERS.rate_slope, DEFAULT_PARAMETERS.rate_intercept_down)
    mean_rate = sum((count * rate for rate, _, _, count in samples)) / total_weight
    mean_up = sum((count * up for _, up, _, count in samples)) / total_weight
    mean_down = sum((count * down for _, _, down, count in samples)) / total_weight
    rate_variance = sum((count * (rate - mean_rate) ** 2 for rate, _, _, count in samples)) / total_weight
    if rate_variance < 1e-06:
        return (mean_up, 0.0, mean_down)
    mean_gap = mean_down - mean_up
    gap_covariance = sum((count * rate * (down - up - mean_gap) for rate, up, down, count in samples)) / total_weight
    slope = -gap_covariance / (2.0 * rate_variance)
    slope = min(max(slope, -1.0), 1.0)
    return (mean_up - slope * mean_rate, slope, mean_down + slope * mean_rate)

def estimate_parameters(market_history):
    rate_path = market_history.values_by_underlying_id.get(FED_FUNDS_RATE_UNDERLYING_ID, ())
    if len(rate_path) < 3:
        return DEFAULT_PARAMETERS
    changes = [round(rate_path[i + 1] - rate_path[i], 2) for i in range(len(rate_path) - 1)]
    observed_steps = [abs(change) for change in changes if abs(change) > TOLERANCE]
    rate_step = min(observed_steps) if observed_steps else RATE_STRIKE_GRID
    intercept_up, slope, intercept_down = _estimate_rate_chain(rate_path)
    drift_by_id = dict(DEFAULT_PARAMETERS.drift_by_id)
    rate_beta_by_id = dict(DEFAULT_PARAMETERS.rate_beta_by_id)
    residual_by_id = {}
    for company_id in COMPANY_UNDERLYING_IDS:
        values = market_history.values_by_underlying_id.get(company_id, ())
        if len(values) != len(rate_path) or len(values) < 3:
            continue
        log_returns = [math.log(values[i + 1] / values[i]) if values[i] > 0.0 and values[i + 1] > 0.0 else 0.0 for i in range(len(values) - 1)]
        buckets = defaultdict(list)
        for change, log_return in zip(changes, log_returns):
            buckets[change].append(log_return)
        up_bucket = buckets.get(round(rate_step, 2), [])
        down_bucket = buckets.get(round(-rate_step, 2), [])
        if len(up_bucket) >= 2 and len(down_bucket) >= 2:
            up_mean = sum(up_bucket) / len(up_bucket)
            down_mean = sum(down_bucket) / len(down_bucket)
            up_variance = sum(((y - up_mean) ** 2 for y in up_bucket)) / (len(up_bucket) - 1)
            down_variance = sum(((y - down_mean) ** 2 for y in down_bucket)) / (len(down_bucket) - 1)
            beta = (up_mean - down_mean) / (2.0 * rate_step)
            beta_error = math.sqrt(up_variance / len(up_bucket) + down_variance / len(down_bucket)) / (2.0 * rate_step)
            rate_beta_by_id[company_id] = _shrink_towards_zero(beta, beta_error)
        sample_size = len(log_returns)
        if sample_size >= 3:
            beta_estimate = rate_beta_by_id[company_id]
            adjusted = [log_return - beta_estimate * change for change, log_return in zip(changes, log_returns)]
            drift = sum(adjusted) / sample_size
            drift_variance = sum(((y - drift) ** 2 for y in adjusted)) / (sample_size - 1)
            drift_by_id[company_id] = _shrink_towards_zero(drift, math.sqrt(drift_variance / sample_size))
        residual_by_id[company_id] = [log_return - drift_by_id[company_id] - rate_beta_by_id[company_id] * change for change, log_return in zip(changes, log_returns)]
    covariance = dict(DEFAULT_PARAMETERS.covariance)
    covariance_sample_size = 0
    for first_id in COMPANY_UNDERLYING_IDS:
        for second_id in COMPANY_UNDERLYING_IDS:
            first_residuals = residual_by_id.get(first_id, [])
            second_residuals = residual_by_id.get(second_id, [])
            if len(first_residuals) < 3 or len(first_residuals) != len(second_residuals):
                continue
            sample_count = len(first_residuals)
            covariance_sample_size = sample_count
            covariance[_covariance_key(first_id, second_id)] = sum((a * b for a, b in zip(first_residuals, second_residuals))) / (sample_count - 1)
    for company_id in COMPANY_UNDERLYING_IDS:
        key = _covariance_key(company_id, company_id)
        covariance[key] = max(covariance[key], 1e-08)
    cross_key = _covariance_key(*COMPANY_UNDERLYING_IDS)
    variance_bound = math.sqrt(covariance[_covariance_key(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID)] * covariance[_covariance_key(THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)])
    covariance[cross_key] = min(max(covariance[cross_key], -0.999 * variance_bound), 0.999 * variance_bound)
    return FittedParameters(rate_step=rate_step, rate_intercept_up=intercept_up, rate_slope=slope, rate_intercept_down=intercept_down, drift_by_id=drift_by_id, rate_beta_by_id=rate_beta_by_id, covariance=covariance, covariance_sample_size=covariance_sample_size)

def _shrink_quantity(quantity, factor):
    if quantity < 1:
        return 0
    return max(1, int(quantity * factor))

def _snap_quote_prices(bid_value, offer_value):
    bid_pennies = min(max(int(math.floor(bid_value * 100.0 + 1e-09)), 0), 99)
    offer_pennies = min(max(int(math.ceil(offer_value * 100.0 - 1e-09)), 1), 100)
    if bid_pennies >= offer_pennies:
        if offer_pennies < 100:
            offer_pennies = bid_pennies + 1
        else:
            bid_pennies = offer_pennies - 1
    return (bid_pennies / 100.0, offer_pennies / 100.0)

@dataclass(frozen=True)
class FactorRisk:
    delta: tuple[float, float, float]
    gamma: tuple[float, float, float]
    vega: float = 0.0

class MarketMaker:
    GAMMA_ENABLED: bool = True
    VEGA_ENABLED: bool = True

    def __init__(self, underlying_initial_state, option_initial_state, cash_balance):
        self.underlying_state = underlying_initial_state
        self.active_option_state = option_initial_state
        self.cash_balance = cash_balance
        self.position = Position()
        self.cash_buffer = max(MIN_CASH_BUFFER, CASH_BUFFER_FRACTION * cash_balance)
        self.risk_capital = max(cash_balance, 1.0)
        self.gross_long_by_option_id = defaultdict(int)
        self.gross_short_by_option_id = defaultdict(int)
        self.parameters = DEFAULT_PARAMETERS
        self.contract_by_option_id = {option.option_id: option for option in option_initial_state}
        self.counterparty_record = defaultdict(lambda: [0.0, 0.0])
        self.counterparty_flow = defaultdict(lambda: [0.0, 0.0])
        self._price_cache = {}
        self._sensitivity_cache = {}
        self._exposure = None
        self._pessimistic_cash = cash_balance
        self._settlement_doubt_cap = SETTLEMENT_DOUBT_CAP_FRACTION * max(cash_balance, 1.0)
        self._observed_path = {}
        self._steps_since_refit = 0
        self._committed_collateral = 0.0
        self._live_quote_commitment = 0.0
        self._last_quote_option_id = None
        self._sequential_fills = 0
        self._batched_fills = 0
        self._order_type_is_counterparty_side = ORDER_TYPE_IS_COUNTERPARTY_SIDE
        self._order_type_side_confirmed = ORDER_TYPE_SIDE_CONFIRMED
        self._fok_side_agreements = 0
        self._fok_side_disagreements = 0
        self._pending_fok = []
        self._last_quoted_counterparty = None

    def _value_by_underlying_id(self):
        return {underlying.underlying_id: underlying.value for underlying in self.underlying_state}

    def _invalidate_caches(self):
        self._price_cache.clear()
        self._sensitivity_cache.clear()
        self._exposure = None

    def on_step_advance(self, new_underlying_state, new_option_state):
        try:
            self._on_step_advance(new_underlying_state, new_option_state)
        except Exception:
            self.underlying_state = new_underlying_state
            self.active_option_state = new_option_state
            for option in new_option_state:
                self.contract_by_option_id[option.option_id] = option
            self._invalidate_caches()

    def _on_step_advance(self, new_underlying_state, new_option_state):
        previous_values = self._value_by_underlying_id()
        new_values = {underlying.underlying_id: underlying.value for underlying in new_underlying_state}
        surviving_ids = {option.option_id for option in new_option_state}
        tracked_ids = set(self.contract_by_option_id) | set(self.gross_long_by_option_id) | set(self.gross_short_by_option_id)
        for option_id in tracked_ids - surviving_ids:
            option = self.contract_by_option_id.pop(option_id, None)
            long_quantity = self.gross_long_by_option_id.pop(option_id, 0)
            short_quantity = self.gross_short_by_option_id.pop(option_id, 0)
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
        self._committed_collateral = 0.0
        self._live_quote_commitment = 0.0
        self._last_quote_option_id = None
        self._invalidate_caches()

    def _credit_expiry(self, option, long_quantity, short_quantity, previous_values, new_values):
        settlement_values = previous_values if option.steps_until_expiry <= 0 else new_values
        payoff = option.expiry_valuation(settlement_values)
        self.cash_balance += long_quantity * payoff + short_quantity * (1.0 - payoff)
        try:
            alternative = option.expiry_valuation(new_values if option.steps_until_expiry <= 0 else previous_values)
        except Exception:
            alternative = payoff
        worst_long = min(payoff, alternative)
        worst_short = 1.0 - max(payoff, alternative)
        self._pessimistic_cash += long_quantity * worst_long + short_quantity * worst_short
        self._pessimistic_cash = max(self._pessimistic_cash, self.cash_balance - self._settlement_doubt_cap)

    def _record_observation(self, new_values):
        if not self._observed_path:
            self._observed_path = {underlying_id: [] for underlying_id in UNDERLYING_NAME_BY_ID}
        if all((path and underlying_id in new_values and (path[-1] == new_values[underlying_id]) for underlying_id, path in self._observed_path.items())):
            return
        for underlying_id, path in self._observed_path.items():
            if underlying_id in new_values:
                path.append(new_values[underlying_id])
        self._steps_since_refit += 1

    def _maybe_refit(self):
        if self._steps_since_refit < REFIT_INTERVAL_STEPS:
            return
        lengths = {len(path) for path in self._observed_path.values()}
        if len(lengths) != 1 or next(iter(lengths)) < MIN_REFIT_OBSERVATIONS:
            return
        self._steps_since_refit = 0
        try:
            history = MarketHistory(values_by_underlying_id={underlying_id: tuple(path) for underlying_id, path in self._observed_path.items()})
            self.parameters = estimate_parameters(history)
            self._invalidate_caches()
        except Exception:
            pass

    def on_trade(self, option, price, quantity, counterparty_id):
        try:
            self._on_trade(option, price, quantity, counterparty_id)
        except Exception:
            self._exposure = None

    def _on_trade(self, option, price, quantity, counterparty_id):
        self.position.add_option_quantity(option.option_id, quantity)
        self.contract_by_option_id[option.option_id] = option
        if quantity > 0:
            self.gross_long_by_option_id[option.option_id] += quantity
        else:
            self.gross_short_by_option_id[option.option_id] += -quantity
        collateral = quantity * price if quantity > 0 else -quantity * (1.0 - price)
        collateral = max(collateral, 0.0)
        self.cash_balance -= collateral
        self._pessimistic_cash -= collateral
        self._release_collateral(collateral)
        matched_fok = self._record_fok_outcome(option.option_id, price, quantity)
        self.counterparty_flow[counterparty_id][1] += 1.0
        if not matched_fok and self._last_quote_option_id is not None:
            if option.option_id == self._last_quote_option_id:
                self._sequential_fills += 1
            else:
                self._batched_fills += 1
        theoretical = self._price_option_strict(option)
        edge = quantity * (theoretical - price)
        record = self.counterparty_record[counterparty_id]
        record[0] += edge
        record[1] += abs(quantity)
        self._exposure = None

    def _record_fok_outcome(self, option_id, price, quantity):
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
                self._order_type_side_confirmed = False
                self._fok_side_agreements, self._fok_side_disagreements = (0, 0)
            elif self._fok_side_agreements >= FOK_SIDE_CONFIRMING_TRADES:
                self._order_type_side_confirmed = True
            return True
        return False

    @property
    def name(self):
        return 'TelescopeMM'

    def warm_up(self, market_history):
        try:
            self.parameters = estimate_parameters(market_history)
            self._observed_path = {underlying_id: list(market_history.values_by_underlying_id.get(underlying_id, ())) for underlying_id in UNDERLYING_NAME_BY_ID}
            self._steps_since_refit = 0
        except Exception:
            self.parameters = DEFAULT_PARAMETERS
        self._invalidate_caches()

    def price_option(self, option):
        try:
            return self._price_option_strict(option)
        except Exception:
            return 0.5

    def _price_option_strict(self, option):
        cached = self._price_cache.get(option.option_id)
        if cached is not None:
            return cached
        value = price_binary_option(self.parameters, option, self._value_by_underlying_id())
        self._price_cache[option.option_id] = value
        return value

    def price_option_from_parameters(self, market_parameters, option):
        try:
            return price_binary_option(fitted_from_market_parameters(market_parameters), option, self._value_by_underlying_id())
        except Exception:
            return 0.5

    def _factor_risk(self, option):
        cached = self._sensitivity_cache.get(option.option_id)
        if cached is not None:
            return cached
        base_values = self._value_by_underlying_id()
        base_price = self._price_option_strict(option)
        step = self.parameters.rate_step

        def price_with(underlying_id, value):
            bumped = dict(base_values)
            bumped[underlying_id] = value
            return price_binary_option(self.parameters, option, bumped)
        base_rate = base_values[FED_FUNDS_RATE_UNDERLYING_ID]
        rate_down_value = max(base_rate - step, 0.0)
        rate_up_price = price_with(FED_FUNDS_RATE_UNDERLYING_ID, base_rate + step)
        if base_rate - rate_down_value > TOLERANCE:
            rate_down_price = price_with(FED_FUNDS_RATE_UNDERLYING_ID, rate_down_value)
            rate_delta = (rate_up_price - rate_down_price) / (2.0 * step)
            rate_gamma = (rate_up_price - 2.0 * base_price + rate_down_price) / (step * step)
        else:
            rate_delta = (rate_up_price - base_price) / step
            rate_gamma = 0.0
        deltas = [rate_delta]
        gammas = [rate_gamma]
        for company_id in COMPANY_UNDERLYING_IDS:
            base_value = base_values[company_id]
            up_price = price_with(company_id, base_value * math.exp(COMPANY_LOG_BUMP))
            down_price = price_with(company_id, base_value * math.exp(-COMPANY_LOG_BUMP))
            deltas.append((up_price - down_price) / (2.0 * COMPANY_LOG_BUMP))
            gammas.append((up_price - 2.0 * base_price + down_price) / COMPANY_LOG_BUMP ** 2)
        risk = FactorRisk(delta=(deltas[0], deltas[1], deltas[2]), gamma=(gammas[0], gammas[1], gammas[2]), vega=self._vega(option, base_values))
        self._sensitivity_cache[option.option_id] = risk
        return risk

    def _vega(self, option, base_values):
        if not any((leg.underlying_id in COMPANY_UNDERLYING_IDS for leg in option.legs)):
            return 0.0

        def scaled_price(factor):
            scaled = replace(self.parameters, covariance={key: value * factor for key, value in self.parameters.covariance.items()})
            return price_binary_option(scaled, option, base_values)
        return (scaled_price(1.0 + COVARIANCE_BUMP) - scaled_price(1.0 - COVARIANCE_BUMP)) / (2.0 * COVARIANCE_BUMP)

    def _portfolio_exposure(self):
        if self._exposure is not None:
            return self._exposure
        delta_totals = [0.0, 0.0, 0.0]
        gamma_totals = [0.0, 0.0, 0.0]
        vega_total = 0.0
        for option_id, quantity in self.position.option_quantity_by_option_id.items():
            if quantity == 0:
                continue
            option = self.contract_by_option_id.get(option_id)
            if option is None:
                continue
            risk = self._factor_risk(option)
            vega_total += quantity * risk.vega
            for index in range(3):
                delta_totals[index] += quantity * risk.delta[index]
                gamma_totals[index] += quantity * risk.gamma[index]
        self._exposure = FactorRisk(delta=(delta_totals[0], delta_totals[1], delta_totals[2]), gamma=(gamma_totals[0], gamma_totals[1], gamma_totals[2]), vega=vega_total)
        return self._exposure

    def portfolio_delta(self):
        return self._portfolio_exposure().delta

    def portfolio_gamma(self):
        return self._portfolio_exposure().gamma

    def portfolio_vega(self):
        return self._portfolio_exposure().vega

    def _factor_variances(self):
        up_probability, down_probability = self.parameters.rate_transition_probabilities(self._value_by_underlying_id()[FED_FUNDS_RATE_UNDERLYING_ID])
        return ((up_probability + down_probability) * self.parameters.rate_step ** 2, self.parameters.covariance[_covariance_key(AJARAI_UNDERLYING_ID, AJARAI_UNDERLYING_ID)], self.parameters.covariance[_covariance_key(THERIODIC_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)])

    def _inventory_skew(self, option):
        risk = self._factor_risk(option)
        book = self._portfolio_exposure()
        variances = self._factor_variances()
        covariance = sum((variances[index] * risk.delta[index] * book.delta[index] for index in range(3)))
        if self.GAMMA_ENABLED:
            covariance += GAMMA_AVERSION * sum((0.5 * variances[index] ** 2 * risk.gamma[index] * book.gamma[index] for index in range(3)))
        skew = INVENTORY_AVERSION * covariance / self.risk_capital
        return min(max(skew, -MAX_INVENTORY_SKEW), MAX_INVENTORY_SKEW)

    def _convexity_charge(self, option):
        if not self.GAMMA_ENABLED:
            return 0.0
        risk = self._factor_risk(option)
        variances = self._factor_variances()
        return 0.5 * sum((variances[index] * abs(risk.gamma[index]) for index in range(3)))

    def _convexity_padding(self, option):
        return min(GAMMA_PAD_AVERSION * self._convexity_charge(option), MAX_GAMMA_PAD)

    def _vol_uncertainty_charge(self, option):
        if not self.VEGA_ENABLED:
            return 0.0
        return abs(self._factor_risk(option).vega) * self.parameters.relative_vol_uncertainty

    def _vol_uncertainty_padding(self, option):
        return min(VEGA_PAD_AVERSION * self._vol_uncertainty_charge(option), MAX_VEGA_PAD)

    def _vol_uncertainty_size_factor(self, option):
        if not self.VEGA_ENABLED:
            return 1.0
        return 1.0 / (1.0 + self._vol_uncertainty_charge(option) / VEGA_SIZE_TOLERANCE)

    def _convexity_size_factor(self, option):
        if not self.GAMMA_ENABLED:
            return 1.0
        return 1.0 / (1.0 + self._convexity_charge(option) / GAMMA_SIZE_TOLERANCE)

    def _model_padding(self, option):
        return min(self._convexity_padding(option) + self._vol_uncertainty_padding(option), MAX_MODEL_PADDING)

    def _model_size_factor(self, option):
        combined = self._convexity_size_factor(option) * self._vol_uncertainty_size_factor(option)
        return min(max(combined, MIN_SIZE_FACTOR), 1.0)

    def reservation_price(self, option):
        return min(max(self._price_option_strict(option) - self._inventory_skew(option), 0.0), 1.0)

    def _counterparty_padding(self, counterparty_id):
        captured, traded = self.counterparty_record.get(counterparty_id, [0.0, 0.0])
        if traded >= 5.0:
            average_edge = captured / traded
            if average_edge < 0.0:
                confidence = traded / (traded + 25.0)
                return min(0.06, confidence * -average_edge)
        quotes, fills = self.counterparty_flow.get(counterparty_id, [0.0, 0.0])
        if quotes < MIN_QUOTES_FOR_FILL_RATE:
            return 0.0
        fill_rate = fills / quotes
        if fill_rate <= TARGET_FILL_RATE:
            return 0.0
        confidence = quotes / (quotes + MIN_QUOTES_FOR_FILL_RATE)
        return min(MAX_GENEROSITY_PAD, confidence * GENEROSITY_AVERSION * (fill_rate - TARGET_FILL_RATE))

    def _available_cash(self):
        return max(min(self.cash_balance, self._pessimistic_cash) - self.cash_buffer, 0.0)

    def _collateral_quote_prices(self, fair_value, num_steps, padding):
        hurdle = min(HURDLE_PER_STEP * max(num_steps, 1), MAX_HURDLE)
        bid = fair_value / (1.0 + hurdle) - padding
        offer = (fair_value + hurdle) / (1.0 + hurdle) + padding
        if offer - bid < 2.0 * MIN_HALF_SPREAD:
            middle = 0.5 * (bid + offer)
            bid, offer = (middle - MIN_HALF_SPREAD, middle + MIN_HALF_SPREAD)
        return (bid, offer)

    def _affordable_quantity(self, collateral_per_contract, num_steps=1, loss_probability=1.0):
        if collateral_per_contract <= TOLERANCE:
            return MAX_QUOTE_SIZE
        uncommitted = self._uncommitted_cash()
        live_options = max(1, len(self.active_option_state))
        budget = uncommitted / (CONCURRENT_LOAD_FACTOR * math.sqrt(live_options))
        budget /= math.sqrt(max(num_steps, 1))
        effective_cost = collateral_per_contract * min(max(loss_probability, MIN_LOSS_PROBABILITY), 1.0)
        by_risk = int(budget / effective_cost)
        by_cash = int(uncommitted / collateral_per_contract)
        return max(0, min(MAX_QUOTE_SIZE, by_risk, by_cash))

    def _uncommitted_cash(self):
        return max(self._available_cash() - self._committed_collateral, 0.0)

    @property
    def _quotes_are_sequential(self):
        return self._batched_fills == 0 and self._sequential_fills >= SEQUENTIAL_CONFIRMING_FILLS

    def _commit_collateral(self, amount):
        self._committed_collateral += max(amount, 0.0)

    def _release_collateral(self, amount):
        self._committed_collateral = max(self._committed_collateral - max(amount, 0.0), 0.0)
    DECLINE_QUOTE: 'Quote' = None

    def quote(self, option, counterparty_id):
        try:
            return self._quote(option, counterparty_id)
        except Exception:
            return MarketMaker.DECLINE_QUOTE
        finally:
            self.counterparty_flow[counterparty_id][0] += 1.0
            self._last_quoted_counterparty = counterparty_id

    def _quote(self, option, counterparty_id):
        if self._quotes_are_sequential and self._live_quote_commitment > 0.0:
            self._release_collateral(self._live_quote_commitment)
        self._live_quote_commitment = 0.0
        self._last_quote_option_id = option.option_id
        padding = WINNER_CURSE_PAD + self._counterparty_padding(counterparty_id) + self._model_padding(option)
        skew = self._inventory_skew(option)
        reservation = self.reservation_price(option)
        raw_bid, raw_offer = self._collateral_quote_prices(reservation, option.steps_until_expiry, padding)
        bid_price, offer_price = _snap_quote_prices(raw_bid, raw_offer)
        steps = option.steps_until_expiry
        bid_quantity = self._affordable_quantity(bid_price, steps, 1.0 - reservation)
        offer_quantity = self._affordable_quantity(1.0 - offer_price, steps, reservation)
        size_factor = self._model_size_factor(option)
        bid_quantity = _shrink_quantity(bid_quantity, size_factor)
        offer_quantity = _shrink_quantity(offer_quantity, size_factor)
        if skew > 0.0:
            bid_quantity = _shrink_quantity(bid_quantity, INVENTORY_SIZE_SHRINK)
        elif skew < 0.0:
            offer_quantity = _shrink_quantity(offer_quantity, INVENTORY_SIZE_SHRINK)
        if bid_quantity < 1:
            bid_price, bid_quantity = (0.0, 1)
        if offer_quantity < 1:
            offer_price, offer_quantity = (1.0, 1)
        bid_price, offer_price = _snap_quote_prices(bid_price, offer_price)
        self._live_quote_commitment = max(bid_price * bid_quantity, (1.0 - offer_price) * offer_quantity)
        self._commit_collateral(self._live_quote_commitment)
        return Quote(bid_price=bid_price, bid_quantity=bid_quantity, offer_price=offer_price, offer_quantity=offer_quantity)

    def respond_to_fok(self, option, fok_order):
        try:
            return self._respond_to_fok(option, fok_order)
        except Exception:
            return False

    def _respond_to_fok(self, option, fok_order):
        reservation = self.reservation_price(option)
        required = FOK_EDGE_REQUIRED + self._counterparty_padding(fok_order.counterparty_id) + self._model_padding(option)
        probing = not self._order_type_side_confirmed and self._fok_side_agreements + self._fok_side_disagreements < FOK_SIDE_CONFIRMING_TRADES
        if probing:
            required *= FOK_PROBE_EDGE_MULTIPLIER
        steps = option.steps_until_expiry
        counterparty_buys = (fok_order.order_type == OrderType.BUY) == self._order_type_is_counterparty_side
        unit_collateral = 1.0 - fok_order.price if counterparty_buys else fok_order.price
        if counterparty_buys:
            if fok_order.price < reservation + required:
                return False
            accepted = self._affordable_quantity(unit_collateral, steps, reservation) >= fok_order.quantity
        elif fok_order.price > reservation - required:
            return False
        else:
            accepted = self._affordable_quantity(unit_collateral, steps, 1.0 - reservation) >= fok_order.quantity
        if accepted and probing:
            accepted = unit_collateral * fok_order.quantity <= FOK_PROBE_CASH_FRACTION * self.risk_capital
        if accepted:
            self._pending_fok.append((option.option_id, fok_order.price, fok_order.quantity, counterparty_buys))
            self._commit_collateral(unit_collateral * fok_order.quantity)
        return accepted
MarketMaker.DECLINE_QUOTE = Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)