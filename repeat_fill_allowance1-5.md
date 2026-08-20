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
> TelescopeMM quoted buy 0.23 for 16 / sell 12 @ 0.28 (theo=0.2481)
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
> TelescopeMM quoted buy 0.98 for 12 / sell 40 @ 1.0 (theo=1.0000)
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
> TelescopeMM quoted buy 0.71 for 8 / sell 8 @ 0.77 (theo=0.7444)
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
1. Stalemate Quoter: $37.0
2. TelescopeMM: $1.08
TelescopeMM bankrupt: False (cash balance: 11.08, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.25: $10.94
2. Stalemate Quoter: $1.0
3. TelescopeMM: $-1.17
TelescopeMM bankrupt: False (cash balance: 8.83, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.25: $12.47
2. TelescopeMM: $7.74
TelescopeMM bankrupt: False (cash balance: 17.74, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. Fixed Width 0.1: $30.39
2. Stalemate Quoter: $1.0
3. TelescopeMM: $0.72
TelescopeMM bankrupt: False (cash balance: 10.72, starting capital: 10.0)
Result: PASS (score=0.40)

Ranking:
1. TelescopeMM: $33.61
2. Fixed Width 0.1: $9.38
3. Fixed Width 0.25: $2.0
TelescopeMM bankrupt: False (cash balance: 43.61, starting capital: 10.0)
Result: PASS (score=1.00)

Ranking:
1. Fixed Width 0.1: $24.88
2. TelescopeMM: $17.38
3. Stalemate Quoter: $3.0
TelescopeMM bankrupt: False (cash balance: 37.38, starting capital: 20.0)
Result: PASS (score=0.70)

Ranking:
1. TelescopeMM: $9.6
2. Fixed Width 0.1: $0.28
3. Fixed Width 0.05: $-5.18
TelescopeMM bankrupt: False (cash balance: 29.6, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $6.57
2. Fixed Width 0.05: $-11.99
TelescopeMM bankrupt: False (cash balance: 26.57, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. Lattice: $21.97
2. TelescopeMM: $4.24
3. Fixed Width 0.1: $3.38
4. Situational Unawareness: $2.37
TelescopeMM bankrupt: False (cash balance: 24.24, starting capital: 20.0)
Result: PASS (score=0.80)

Ranking:
1. Lattice: $18.04
2. Fixed Width 0.05: $5.87
3. TelescopeMM: $3.82
TelescopeMM bankrupt: False (cash balance: 23.82, starting capital: 20.0)
Result: PASS (score=0.40)

Ranking:
1. TelescopeMM: $14.57
2. Situational Unawareness: $3.85
3. Lattice: $-6.87
TelescopeMM bankrupt: False (cash balance: 34.57, starting capital: 20.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $42.92
2. Fixed Width 0.05: $0.38
3. Lattice: $-0.17
TelescopeMM bankrupt: False (cash balance: 82.92, starting capital: 40.0)
Result: PASS (score=1.00)

Ranking:
1. TelescopeMM: $15.51
2. Lattice: $11.01
3. Situational Unawareness: $10.7
4. Mongoose: $-2.5
TelescopeMM bankrupt: False (cash balance: 55.51, starting capital: 40.0)
Result: PASS (score=1.00)

Ranking:
1. Fixed Width 0.05: $29.94
2. TelescopeMM: $17.55
3. Lattice: $-1.0
4. Mongoose: $-31.79
TelescopeMM bankrupt: False (cash balance: 57.55, starting capital: 40.0)
Result: PASS (score=0.80)

Ranking:
1. Situational Unawareness: $20.08
2. TelescopeMM: $9.64
3. Mongoose: $-26.03
4. Fixed Width 0.05: $-28.99
TelescopeMM bankrupt: False (cash balance: 49.64, starting capital: 40.0)
Result: PASS (score=0.80)

Ranking:
1. Lattice: $-16.37
2. TelescopeMM: $-20.42
3. Mongoose: $-33.53
4. Fixed Width 0.05: $-88.29
TelescopeMM bankrupt: False (cash balance: 19.58, starting capital: 40.0)
Result: PASS (score=0.80)