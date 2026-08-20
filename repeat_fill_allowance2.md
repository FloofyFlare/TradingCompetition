Market parameters: MarketParameters(ajarai_drift=0.001, ajarai_idio_std_dev=0.01, ajarai_rate_beta=-0.02, ajarai_sector_beta=1.0, rate_down_probability=0.2, rate_reversion_strength=0.1, rate_up_probability=0.25, sector_std_dev=0.02, theriodic_drift=0.0015, theriodic_idio_std_dev=0.012, theriodic_rate_beta=-0.015, theriodic_sector_beta=1.0, rate_step=0.25, rate_target=2.0)
Underlyings: FED=3.0, AJR=500.0, THR=600.0
1 (1d FED >= 3.00): user theo=0.7000, actual theo=0.7000
2 (5d FED >= 3.50): user theo=0.0471, actual theo=0.0471
3 (1d AJR >= 500.00): user theo=0.5309, actual theo=0.5309
4 (10d THR >= 650.00): user theo=0.2068, actual theo=0.2068
5 (1d THR - AJR >= 0.00): user theo=1.0000, actual theo=1.0000
6 (10d THR - AJR >= 0.00): user theo=0.9999, actual theo=0.9999
Result: PASS (max_error=0.0000)

Ranking:
1. Stalemate Quoter: $1.0
2. TelescopeMM: $0.06
TelescopeMM bankrupt: False (cash balance: 10.06, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> TelescopeMM ignored the FOK (theo=0.1142)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> TelescopeMM quoted buy 0.0 for 11 / sell 1 @ 0.07 (theo=0.0286)
> TelescopeMM bought 0.0 for 3 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> TelescopeMM quoted buy 0.0 for 2 / sell 1 @ 0.06 (theo=0.0286)
> TelescopeMM sold 1 @ 0.06 8734500 (1d THR >= 2371.00) (counterparty 689497)

[Underlying state advanced by one step]
> FED: 5.75, AJR: 1277.17, THR: 2241.32
> 8734500 (0d THR >= 2371.00) expired with expiry_val=0.0
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $0.84
2. Stalemate Quoter: $0.0
3. Fixed Width 0.1: $0.0
TelescopeMM bankrupt: False (cash balance: 20.84, starting capital: 20.0)
> FED: 1.5, AJR: 1143.14, THR: 1787.62
> FOK from counterparty 482453: buy 0.99 for 2 4895269 (2d THR >= 1735.00)
> TelescopeMM ignored the FOK (theo=0.9995)
> RFQ from counterparty 309546: buy 3 3857985 (1d FED >= 1.75)
> TelescopeMM quoted buy 0.23 for 16 / sell 9 @ 0.28 (theo=0.2481)
> TelescopeMM sold 3 @ 0.28 3857985 (1d FED >= 1.75) (counterparty 309546)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1142.9, THR: 1794.43
> 3857985 (0d FED >= 1.75) expired with expiry_val=0.0
> FOK from counterparty 482453: sell 9 @ 0.99 4895269 (1d THR >= 1735.00)
> TelescopeMM ignored the FOK (theo=1.0000)
> FOK from counterparty 101661: sell 8 @ 0.99 1280022 (2d THR - AJR >= 0.00)
> TelescopeMM ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1162.7, THR: 1808.13
> RFQ from counterparty 474121: buy 4 1280022 (1d THR - AJR >= 0.00)
> TelescopeMM quoted buy 0.98 for 9 / sell 40 @ 1.0 (theo=1.0000)
> TelescopeMM sold 2 @ 1.0 1280022 (1d THR - AJR >= 0.00) (counterparty 474121)
> FOK from counterparty 482453: buy 0.99 for 8 5517759 (1d THR >= 1523.00)
> TelescopeMM ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.25, AJR: 1194.78, THR: 1863.33
> 1280022 (0d THR - AJR >= 0.00) expired with expiry_val=1.0
Result: PASS (score=1.00)

Ranking:
1. Fixed Width 0.05: $1.45
2. Mongoose: $0.0
3. TelescopeMM: $-2.02
TelescopeMM bankrupt: False (cash balance: 37.98, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 123260: buy 0.94 for 26 6685933 (1d THR >= 624.00)
> TelescopeMM ignored the FOK (theo=0.9617)
> FOK from counterparty 469703: buy 0.39 for 11 4986864 (2d AJR >= 1315.00)
> TelescopeMM ignored the FOK (theo=0.4554)
> FOK from counterparty 469703: buy 0.99 for 2 6685933 (1d THR >= 624.00)
> TelescopeMM accepted the FOK (theo=0.9617)
> TelescopeMM sold 2 @ 0.99 6685933 (1d THR >= 624.00) (counterparty 469703)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1324.96, THR: 651.85
> 6685933 (0d THR >= 624.00) expired with expiry_val=1.0
> RFQ from counterparty 469703: sell 11 4986864 (1d AJR >= 1315.00)
> TelescopeMM quoted buy 0.71 for 6 / sell 8 @ 0.77 (theo=0.7444)
> TelescopeMM bought 0.71 for 6 4986864 (1d AJR >= 1315.00) (counterparty 469703)
> FOK from counterparty 808858: buy 0.99 for 16 4765820 (2d FED >= 1.50)
> TelescopeMM ignored the FOK (theo=1.0000)
> FOK from counterparty 578477: buy 0.78 for 17 4986864 (1d AJR >= 1315.00)
> TelescopeMM accepted the FOK (theo=0.7444)
> TelescopeMM sold 17 @ 0.78 4986864 (1d AJR >= 1315.00) (counterparty 578477)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1347.82, THR: 648.13
> 4986864 (0d AJR >= 1315.00) expired with expiry_val=1.0
> FOK from counterparty 757814: sell 25 @ 0.01 7933446 (1d AJR >= 1408.00)
> TelescopeMM ignored the FOK (theo=0.0007)
> FOK from counterparty 808858: buy 0.99 for 26 7316899 (1d FED >= 1.00)
> TelescopeMM ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1361.52, THR: 690.84
Result: PASS (score=1.00)

Ranking:
1. Stalemate Quoter: $39.0
2. TelescopeMM: $1.0
TelescopeMM bankrupt: False (cash balance: 11.0, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.25: $12.4
2. Stalemate Quoter: $1.0
3. TelescopeMM: $-1.73
TelescopeMM bankrupt: False (cash balance: 8.27, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.25: $11.83
2. TelescopeMM: $7.67
TelescopeMM bankrupt: False (cash balance: 17.67, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.1: $31.97
2. Stalemate Quoter: $1.0
3. TelescopeMM: $-0.11
TelescopeMM bankrupt: False (cash balance: 9.89, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. TelescopeMM: $33.45
2. Fixed Width 0.1: $9.15
3. Fixed Width 0.25: $3.0
TelescopeMM bankrupt: False (cash balance: 43.45, starting capital: 10.0)
Result: PASS (score=1.00)

Ranking:
1. Fixed Width 0.1: $26.9
2. TelescopeMM: $15.87
3. Stalemate Quoter: $3.0
TelescopeMM bankrupt: False (cash balance: 35.87, starting capital: 20.0)
Result: PASS (score=0.70)

Ranking:
1. TelescopeMM: $9.9
2. Fixed Width 0.1: $0.6
3. Fixed Width 0.05: $-5.82
TelescopeMM bankrupt: False (cash balance: 29.9, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $5.7
2. Fixed Width 0.05: $-11.46
TelescopeMM bankrupt: False (cash balance: 25.7, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. Lattice: $12.38
2. Fixed Width 0.1: $11.43
3. TelescopeMM: $5.65
4. Situational Unawareness: $1.89
TelescopeMM bankrupt: False (cash balance: 25.65, starting capital: 20.0)
Result: PASS (score=0.60)

Ranking:
1. Lattice: $17.43
2. TelescopeMM: $3.68
3. Fixed Width 0.05: $2.74
TelescopeMM bankrupt: False (cash balance: 23.68, starting capital: 20.0)
Result: PASS (score=0.70)

Ranking:
1. TelescopeMM: $12.95
2. Situational Unawareness: $4.6
3. Lattice: $1.98
TelescopeMM bankrupt: False (cash balance: 32.95, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $37.06
2. Fixed Width 0.05: $1.03
3. Lattice: $0.43
TelescopeMM bankrupt: False (cash balance: 77.06, starting capital: 40.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $14.2
2. Lattice: $11.22
3. Situational Unawareness: $10.85
4. Mongoose: $-2.48
TelescopeMM bankrupt: False (cash balance: 54.2, starting capital: 40.0)
Result: PASS (score=1.00)

Ranking:
1. Fixed Width 0.05: $30.96
2. TelescopeMM: $16.49
3. Lattice: $2.29
4. Mongoose: $-32.03
TelescopeMM bankrupt: False (cash balance: 56.49, starting capital: 40.0)
Result: PASS (score=0.80)

Ranking:
1. Situational Unawareness: $19.42
2. TelescopeMM: $2.1
3. Mongoose: $-24.95
4. Fixed Width 0.05: $-30.31
TelescopeMM bankrupt: False (cash balance: 42.1, starting capital: 40.0)
Result: PASS (score=0.80)

Ranking:
1. Lattice: $-12.1
2. TelescopeMM: $-19.88
3. Mongoose: $-33.15
4. Fixed Width 0.05: $-90.63
TelescopeMM bankrupt: False (cash balance: 20.12, starting capital: 40.0)
Result: PASS (score=0.80)