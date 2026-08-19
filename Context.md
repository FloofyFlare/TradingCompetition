### Competition description
Akuna Capital’s 2026 Virtual Quant Trading Challenge
Virtual
Quant Virtual Trading Challenge 
About Akuna: 
Akuna Capital is an innovative trading firm with a strong focus on collaboration, cutting-edge technology, data driven solutions and automation. We specialize in providing liquidity as an options market-maker – meaning we are committed to providing competitive quotes that we are willing to both buy and sell. To do this successfully, we design and implement our own low latency technologies, trading strategies and mathematical models.  
Our Founding Partners* *first conceptualized Akuna in their hometown of Sydney. They opened the firm’s first office in 2011 in the heart of the derivatives industry and the options capital of the world – Chicago. Today, Akuna is proud to operate from additional offices in Sydney, Shanghai, London, and Singapore. 
What you’ll do as a Virtual Quant Trading Challenge Participant: 
Are you quantitative, competitive, proficient with Python and looking to test your skills in a Quantitative Trading environment? Break into the Trading industry by participating in our latest simulation! Candidates will gain hands-on trading experience by writing their own market-making bots which will compete both against our models and one another on a simulated exchange. The most profitable submissions will win Akuna swag and expedited recruitment processes in our Quant full-time and internship roles in Chicago! 
The challenge will take about 5-8 hours to complete, and the competition will be open for 1 week (from August 17th – August 21st). 
Qualities that make great candidates: 

    Able to dedicate 5-8 hours uninterrupted to complete the challenge from August 17th through August 21st 2026.

    Pursuing a BS/MS/ PhD in Engineering, Economics, Statistics, Mathematics, Computer Science, Actuarial Science or a related/equivalent field.

    Strong math aptitude, statistical and quantitative analysis skills.

    Strong Python programming background.

    Entrepreneurial self-starter ready to work in a fast paced, competitive, team environment.

    Desire and ability to learn the intricacies of financial markets.

    Major GPA of 3.5 or above

    Graduating between December 2026 – August 2028.

These are some of the addititioanl information that I gained : You cannot go bankrupt, More information on the competition is on Price and trading strategies for binary options, Underlyings are fed funs rate, and two AI companies, When rates fall AI rises, Bid and offer with quantities and respond directly to customer buy/sell orders

### Youtube prep video from Akuna
0:04
4 seconds
Welcome to the 2026 Akuna Capital Trading Competition. My name is Sean Vernon and I'm a quantitative trader here at Akuna Capital.
0:11
11 seconds
And I'm Jack Dane, a junior trader at Auna, trading binary options. You may be familiar with binary options, also known as event contracts, from different
0:20
20 seconds
exchanges like KHI or predicted. These instruments price the probability of a given event or outcome occurring, which
0:27
27 seconds
could range from who will win an election to whether or not Bitcoin closes above $100,000 at the end of this year. These contracts are worth zero or
0:36
36 seconds
one at settlement based on whether or not the given outcome occurs.
0:40
40 seconds
I find these instruments to be conceptually easier to think about than traditional financial options as they are simply priced using the probability
0:48
48 seconds
distribution of the underlying. the probability one event will occur out of a set of events, the distribution of returns of an index, or any other
0:56
56 seconds
measurable outcome. In this challenge, you will design both pricing and trading strategies for binary options. I'll let Sean explain more of the details.
1:06
1 minute, 6 seconds
Thanks, Jack. The trading competition will involve binary options on three underlyings, the Fed funds rate and the valuations of two madeup private AI
1:14
1 minute, 14 seconds
companies, Ajarai and Theori. These three underlyings will vary in value according to a joint distribution which you'll have to estimate from historical
1:21
1 minute, 21 seconds
returns. Generally, as interest rates fall, the valuations of moonshot startups rise and vice versa. You'll be both quoting and responding to orders
1:29
1 minute, 29 seconds
for binary options involving these three underlyings. You'll see all the details in the code once you start the challenge. Your goal will be to make a market-making bot, which both provides
1:37
1 minute, 37 seconds
two-sided quotes, a bid and an offer with quantities, and responds directly to customer buyell orders. Your marketmaking bot should balance the risk
1:45
1 minute, 45 seconds
of trading orders, being mindful of both your theoretical value for the options and the position you already hold.
1:50
1 minute, 50 seconds
You'll be competing in a variety of scenarios with both progressively more difficult competitors and more difficult trading conditions. So, you'll want to find ways to adapt your behavior based
1:58
1 minute, 58 seconds
on information you get from your counterparties. You'll also want to be careful to avoid going bankrupt, which will cause you to automatically fail the scenario. You'll first be scored based
2:07
2 minutes, 7 seconds
on how well you do in the hacker rank environment. So, get started soon and try to get your score as high as possible. The top competitors will then face off directly to determine the
2:14
2 minutes, 14 seconds
winners of the competition. Also note that using AI assistance is allowed, but we've structured the competition to try to balance the scales in favor of
2:22
2 minutes, 22 seconds
competitors that also draw on their own ideas. Be creative, good luck, and have fun.

### Problem context
only three underlyings
Fed funds rate (FED)
AjarAI (AJR)
Theriodic(THR) 

options are represented by the BinaryOption class

Each option pays out 1.0 at expiry if the event occurs otherwise it is 0.0

examples include FED rate greater than or equal to 3.0 in 3 days
THR valuation is greater than 1tn in 5 days
AJR valuation greater than or equal to THR in 2 days
Not that although the Binary Otpion class can represent options with any amount of leges. in practice you will only encounter single-legged options, or "spreads" on whether AJR or THR has a higher valuation like the third example above 

There are two distinct pipelines RFQ (request-for-quote), the exchange will request quotes from all participating market makers, and route the order to the highest bid or lowest offer it receives, splitting up the order if necessary. Therefore, your quote method should return the most competitive prices and quantities you are able to trade on. Note that you will not know ahead of time whether the RFQ is a buy or sell order. FOK orders give you all the informatio nup front, and it is up to you whether you wnat to trade them, via your return value from `respond_to_fok`. If multiple market makers denot that they want to trade an FOK order, it will be broken up between them.

The eveloution fo the underlying prices are controlled by a join distribution parameterized by MarketParameters. The first test. THEO. will score whether you correctly price binary options give the true MarketParameters via the method price_option_from-parameters: the other tests will all provide a warm-up MarketHistory object which you should estimate the true MarketParameters

The first three tests after the THEO test are denoted VERBOSE these are short tests which output helpful logs to assist with debugging your MarketMaker. You will recieve full points for these tests so long as your code does not error and your MarketMaker does not go bankrupt

Score will vary based on PnL zero credit for going bankrupt and session will end early (worst case senario), partial credit for avoiding bankruptcy

The tests will vary in difficulty, including via different counterparities and different competing market makers.

Bankruptcy: The autograder will keep track of cash balance, separate of the balancy you may store on the MarketMaker. Every time you do a trade, your balanmce will decrease by the maximum loss of your trade. So if you buy 5 contracts for $0.20 each, your cassh balance will go down by a dollar: if you sell 5 contracts at $0.20 apiece, your cash balance will go down by $4. Cash solvency is checked at the end of each day. First, any payoffs associated with expired options will be credited - note that this process can only increase your balanace, At this point in fyour cash balance is below zero, you will be marked as bankrupt, and the session will end early.

