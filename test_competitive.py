"""Competitive RFQ harness: the piece `test_marketmaker.py` cannot model.

That suite hands us 100% of the flow at whatever price we show, so it rewards quoting wide and
can say nothing about whether we would have won the trade. The real exchange "route[s] the order
to the highest bid or lowest offer it receives, splitting up the order if necessary" -- so a
large order walks the book, and a market maker that shows a thin top capture leaves the fat tail
to whoever quotes behind it.

That splitting rule is the whole reason Stalemate Quoter can bank $43 on a $10 book while
quoting 0.00 / 1.00: it never wins the top of an order, but it collects the residual of every
large one at a ruinous price for the counterparty.

Competitors here are the archetypes visible in the graded rankings. They price off the *true*
parameters, which makes them stronger than the real ones and keeps the measurement honest.

Run: python3 test_competitive.py
"""

import math
import random
import statistics
import sys

from marketmaker import (
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    MarketMaker,
    MarketParameters,
    fitted_from_market_parameters,
    price_binary_option,
)
from test_marketmaker import (
    INITIAL_VALUES,
    make_option_suite,
    make_parameters,
    simulate_history,
    underlying_state,
)


class Competitor:
    """Quotes a fixed half-width around the true theo. `half_width=0.5` is the Stalemate bot."""

    def __init__(self, name: str, half_width: float, size: int = 40) -> None:
        self.name = name
        self.half_width = half_width
        self.size = size
        self.cash = 0.0
        self.gross_long: dict[int, int] = {}
        self.gross_short: dict[int, int] = {}
        self.contracts: dict[int, BinaryOption] = {}

    def quote(self, fair: float) -> tuple[float, int, float, int]:
        bid = max(0.0, math.floor((fair - self.half_width) * 100) / 100)
        offer = min(1.0, math.ceil((fair + self.half_width) * 100) / 100)
        return bid, self.size, offer, self.size

    def fill(self, option: BinaryOption, price: float, quantity: int) -> None:
        self.cash -= max(quantity * price if quantity > 0 else -quantity * (1.0 - price), 0.0)
        book = self.gross_long if quantity > 0 else self.gross_short
        book[option.option_id] = book.get(option.option_id, 0) + abs(quantity)
        self.contracts[option.option_id] = option

    def settle(self, option_id: int, values: dict[int, float]) -> None:
        option = self.contracts.pop(option_id, None)
        long_q = self.gross_long.pop(option_id, 0)
        short_q = self.gross_short.pop(option_id, 0)
        if option is not None and (long_q or short_q):
            payoff = option.expiry_valuation(values)
            self.cash += long_q * payoff + short_q * (1.0 - payoff)


class OurMaker:
    """Adapter so the real MarketMaker plugs into the same routing loop."""

    def __init__(self, maker: MarketMaker) -> None:
        self.name = maker.name
        self.maker = maker
        self.cash = 0.0
        self.quotes_issued = 0
        self.contracts_traded = 0

    def quote(self, option, counterparty_id):
        q = self.maker.quote(option, counterparty_id)
        self.quotes_issued += 1
        return q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity

    def fill(self, option, price, quantity, counterparty_id):
        self.cash -= max(quantity * price if quantity > 0 else -quantity * (1.0 - price), 0.0)
        self.contracts_traded += abs(quantity)
        self.maker.on_trade(option, price, quantity, counterparty_id)


def run_session(parameters, values, history, capital, num_days, rng,
                insensitive_share, order_size_range, competitors_spec):
    truth = fitted_from_market_parameters(parameters)
    mm = MarketMaker(underlying_state(values), [], capital)
    mm.warm_up(history)
    us = OurMaker(mm)
    rivals = [Competitor(n, w) for n, w in competitors_spec]

    options, next_id = make_option_suite(values, 1)
    mm.on_step_advance(underlying_state(values), options)
    current = dict(values)

    for _ in range(num_days):
        settle_values = dict(current)
        current = parameters.advance_step(current)
        advanced = [o.advance_step() for o in options if o.steps_until_expiry > 0]
        expired = {o.option_id for o in options} - {o.option_id for o in advanced}
        fresh, next_id = make_option_suite(current, next_id)
        options = advanced + fresh[: rng.randint(1, 3)]
        for oid in expired:
            for r in rivals:
                r.settle(oid, settle_values)
        mm.on_step_advance(underlying_state(current), options)

        for option in options:
            fair = price_binary_option(truth, option, current)
            counterparty_id = rng.randint(1, 6)
            insensitive = rng.random() < insensitive_share
            wants_to_buy = rng.random() < 0.5
            demand = rng.randint(*order_size_range)

            book = []
            b, bq, o, oq = us.quote(option, counterparty_id)
            book.append(("us", us, b, bq, o, oq))
            for r in rivals:
                b2, bq2, o2, oq2 = r.quote(fair)
                book.append((r.name, r, b2, bq2, o2, oq2))

            # Route to the best price first, then walk the book with whatever is left.
            if wants_to_buy:
                ladder = sorted(book, key=lambda e: e[4])           # lowest offer first
                for name, who, _, _, offer, oqty in ladder:
                    if demand <= 0:
                        break
                    if not insensitive and offer >= fair:           # informed: only lift a gift
                        continue
                    take = min(demand, oqty)
                    if take <= 0:
                        continue
                    demand -= take
                    if who is us: us.fill(option, offer, -take, counterparty_id)
                    else: who.fill(option, offer, -take)
            else:
                ladder = sorted(book, key=lambda e: -e[2])          # highest bid first
                for name, who, bid, bqty, _, _ in ladder:
                    if demand <= 0:
                        break
                    if not insensitive and bid <= fair:
                        continue
                    take = min(demand, bqty)
                    if take <= 0:
                        continue
                    demand -= take
                    if who is us: us.fill(option, bid, take, counterparty_id)
                    else: who.fill(option, bid, take)

    for oid in list(mm.gross_long_by_option_id) + list(mm.gross_short_by_option_id):
        pass
    mm.on_step_advance(underlying_state(current), [])   # flush our expiries
    for r in rivals:
        for oid in list(r.contracts):
            r.settle(oid, current)
    return mm.cash_balance - capital, {r.name: r.cash for r in rivals}, us


COMPETITORS = [("FixedWidth0.05", 0.025), ("FixedWidth0.1", 0.05),
               ("FixedWidth0.25", 0.125), ("Stalemate", 0.5)]


def sweep(label, insensitive_share, order_size_range, capital=20.0, num_days=60,
          num_scenarios=20, seed=5):
    rng = random.Random(seed)
    random.seed(seed)
    ours = []
    rival_totals = {n: [] for n, _ in COMPETITORS}
    wins = 0
    for _ in range(num_scenarios):
        p = make_parameters(rng)
        random.seed(rng.random())
        hist, vals = simulate_history(p, INITIAL_VALUES, 300)
        pnl, rivals, us = run_session(p, vals, hist, capital, num_days,
                                      random.Random(rng.random()),
                                      insensitive_share, order_size_range, COMPETITORS)
        ours.append(pnl)
        for n, v in rivals.items():
            rival_totals[n].append(v)
        if pnl >= max(rivals.values()):
            wins += 1
    best_rival = max(rival_totals, key=lambda n: statistics.mean(rival_totals[n]))
    print(f"  {label:<34} ours {statistics.mean(ours):>8.2f}   "
          f"best rival {best_rival} {statistics.mean(rival_totals[best_rival]):>8.2f}   "
          f"we rank 1st in {wins}/{num_scenarios}")
    return statistics.mean(ours), {n: statistics.mean(v) for n, v in rival_totals.items()}


if __name__ == "__main__":
    print("\nCompetitive RFQ, order splitting on. 20 scenarios x 60 days, capital 20.\n")
    print("A) Small orders (1-6): the top of the book is the whole order.")
    sweep("  fully price-insensitive flow", 1.0, (1, 6))
    sweep("  half insensitive", 0.5, (1, 6))
    sweep("  fully informed", 0.0, (1, 6))
    print("\nB) Large orders (1-60): the order walks the book and leaves a residual.")
    sweep("  fully price-insensitive flow", 1.0, (1, 60))
    sweep("  half insensitive", 0.5, (1, 60))
    sweep("  fully informed", 0.0, (1, 60))
