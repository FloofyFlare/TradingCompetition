I need to treat AI stocks as independent while also crossing both assests with rates

Fed rates affect inversely affect stocks

Rate reversion is the ONLY mean reversion in the model — and it propagates into stock drift.

- Company log-returns are i.i.d. `advance_company_value` never reads `current_value`,
  so stock levels carry zero information about their own future returns.
- The rate never reads stock values (`advance_rate(rate_value)`). Causality is one-way:
  rate -> sector -> companies. No feedback edge exists.
- But `tilted_rate_probabilities` tilts toward `rate_target`. FED above target => E[dR] < 0
  over the horizon => with beta_rate < 0, a POSITIVE expected drift for AJR/THR on top of mu.
  Far from target this term dominates n*mu.
- Implementation: the rate DP already yields the terminal-rate distribution. Condition on it.
  Never assume the rate is a martingale — that is the mistake to trade against.

  
Vol increases with large changes in fed rates and large moves in stock prices 

stock should not affect Fed rate

price = column mean
portfolio payoff v = P @ q for position vector q
marginal risk of option i = Cov(P[:,i], v) — a single dot product
bankruptcy risk = a low quantile of cash + v

Expect High volitility

No arbitrage pricing 

Use quote skewing strikes to remove straddles and strategies in my inventory

partially headge AJR & THR for fed rate work at the portfolio level

Don't overfit

Consider sizing of quotes

Consider Near-Expirery behavior

Clip probabilities to [0,1] make

Avoid bankruptcy 

Use Bayesian online updating of fair value model

Per-counterparty adaptation. quote() receives counterparty_id — that's a deliberate hint. Track markout per counterparty: after trading with i, did fair value move against you? Maintain a shrunk estimate ((wins − losses + prior)/(n + prior_n)) and widen h for the informed ones, refuse their FOKs

Sell Premium when volatitlity is high



Quoting

reservation = p − γ·Cov(payoff_i, portfolio_payoff)
bid = reservation − h,   ask = reservation + h
Four things to get right:

Winner's curse on RFQ. The exchange routes to the best bid / lowest offer. You win exactly when you're the most aggressive — which correlates with your estimate being the most wrong. Your naive edge h must be widened for this, and widened more the more competitors there are. This is the single most common way these bots bleed.
Asymmetric sizes, not just skewed prices. Quote larger size on the side that reduces your risk and small size on the side that adds to it. Often better than price skew alone — you stay competitive where you want flow instead of pricing yourself out entirely.
h scales with uncertainty, not constant. Propagate parameter error into p (bump σ̂, μ̂ by their standard errors, see how p moves) and set h ∝ that. Clip final quotes into roughly [0.005, 0.995].
Per-counterparty adaptation. quote() receives counterparty_id — that's a deliberate hint. Track markout per counterparty: after trading with i, did fair value move against you? Maintain a shrunk estimate ((wins − losses + prior)/(n + prior_n)) and widen h for the informed ones, refuse their FOKs.
For respond_to_fok: accept iff price ≤ reservation − h_fok (you buying). h_fok can be tighter than the RFQ edge — no winner's curse since accepts are split, not won — but not zero, because the customer chose to send it.

Bankruptcy
Binaries have bounded payoff, so this is fully controllable. Hard bound: worst-case settlement loss ≤ Σ_i max(0, −q_i) (every short pays 1). Never let a quote take you past cash − that bound > 0. Layer the MC 99.9% quantile on top as a soft limit that starts shrinking your sizes well before the hard wall. Zero credit for bankruptcy makes this asymmetric — be conservative early in a scenario, loosen once you've banked PnL.