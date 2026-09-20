#Type code here
from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.data import SocialSentiment, FinancialStatement, Ratios

from datetime import datetime, timedelta
from math import log as ln, sqrt


# =============================================================
# USER CONFIGURATION
# =============================================================
#
# Change these settings without editing the strategy logic below.
#

# -------------------------------------------------------------
# PORTFOLIO SIZE
# -------------------------------------------------------------

NUMBER_OF_HOLDINGS = 12


# -------------------------------------------------------------
# REBALANCE FREQUENCY
# -------------------------------------------------------------
#
# Valid choices:
#
# "daily"
# "weekly"
# "biweekly"
# "monthly"
#
REBALANCE_FREQUENCY = "monthly"


# -------------------------------------------------------------
# FACTOR WEIGHTS
# -------------------------------------------------------------
#
# These do NOT have to total exactly 1.0.
# The code automatically normalizes them.
#
# Suggested starting configuration:
#
# Fundamentals   35%
# Momentum       25%
# Sentiment      20%
# Valuation      10%
# Risk           10%
#

FUNDAMENTAL_WEIGHT = 0.35
MOMENTUM_WEIGHT = 0.25
SENTIMENT_WEIGHT = 0.20
VALUATION_WEIGHT = 0.10
RISK_WEIGHT = 0.10


# -------------------------------------------------------------
# MOMENTUM CONFIGURATION
# -------------------------------------------------------------

MOMENTUM_3M_WEIGHT = 0.50
MOMENTUM_6M_WEIGHT = 0.50

LOOKBACK_3M = 63
LOOKBACK_6M = 126


# -------------------------------------------------------------
# SENTIMENT
# -------------------------------------------------------------

SENTIMENT_LOOKBACK = 7


# -------------------------------------------------------------
# RISK
# -------------------------------------------------------------

VOLATILITY_LOOKBACK = 63


# -------------------------------------------------------------
# MARKET REGIME FILTER
# -------------------------------------------------------------
#
# If enabled, the strategy reduces stock exposure when
# SPY falls below its long-term moving average.
#

USE_MARKET_TREND_FILTER = True

MARKET_TREND_DAYS = 200

# Equity exposure while SPY is below trend.
RISK_OFF_EQUITY_EXPOSURE = 0.50

# Defensive asset for unused allocation.
DEFENSIVE_TICKER = "SGOV"


# -------------------------------------------------------------
# PORTFOLIO WEIGHTING
# -------------------------------------------------------------
#
# "equal" = all selected stocks receive equal weights.
#
PORTFOLIO_WEIGHTING = "equal"


# =============================================================
# STOCK UNIVERSE
# =============================================================
#
# Adjust this list whenever desired.
#
# SPY and SGOV are separately included as strategy assets
# and are not ranked as stocks.
#

STOCK_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "AVGO",
    "AMD",
    "ORCL",
    "CRM",
    "NOW",
    "ADBE",
    "INTU",
    "PANW",
    "CRWD",
    "ANET",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "QCOM",
    "TXN",
    "PLTR",
    "UBER",
    "NFLX",
    "V",
    "MA",
    "COST",
    "JPM",
    "GS",
    "CAT",
    "GE",
    "ETN",
    "VRT",
    "CEG",
    "VST",
    "HD",
    "WMT",
    "MELI",
    "SHOP"
]


# =============================================================
# STRATEGY
# =============================================================

class TradingStrategy(Strategy):

    def __init__(self):

        # -----------------------------------------------------
        # Assets
        # -----------------------------------------------------

        self.stock_universe = STOCK_UNIVERSE

        self.tickers = list(
            dict.fromkeys(
                STOCK_UNIVERSE
                + ["SPY", DEFENSIVE_TICKER]
            )
        )


        # -----------------------------------------------------
        # Alternative data
        # -----------------------------------------------------

        self.data_list = []

        for ticker in self.stock_universe:

            self.data_list.append(
                SocialSentiment(ticker)
            )

            self.data_list.append(
                FinancialStatement(ticker)
            )

            self.data_list.append(
                Ratios(ticker)
            )


        # -----------------------------------------------------
        # Rebalance state
        # -----------------------------------------------------

        self.last_rebalance_key = None

        self.last_target = {}


    # =========================================================
    # SURMOUNT SETTINGS
    # =========================================================

    @property
    def interval(self):
        return "1day"


    @property
    def assets(self):
        return self.tickers


    @property
    def data(self):
        return self.data_list


    # =========================================================
    # DATE HELPERS
    # =========================================================

    def parse_date(self, value):

        if value is None:
            return None

        text = str(value)

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d"
        ]

        for fmt in formats:

            try:

                return datetime.strptime(
                    text[:19],
                    fmt
                )

            except:
                pass

        try:

            return datetime.strptime(
                text[:10],
                "%Y-%m-%d"
            )

        except:

            return None


    def current_date(
        self,
        ohlcv
    ):

        try:

            return self.parse_date(
                ohlcv[-1]["SPY"]["date"]
            )

        except:

            return None


    # =========================================================
    # REBALANCE LOGIC
    # =========================================================

    def rebalance_key(
        self,
        current_date
    ):

        if REBALANCE_FREQUENCY == "daily":

            return (
                current_date.year,
                current_date.month,
                current_date.day
            )


        if REBALANCE_FREQUENCY == "weekly":

            iso = (
                current_date.isocalendar()
            )

            return (
                iso[0],
                iso[1]
            )


        if REBALANCE_FREQUENCY == "biweekly":

            iso = (
                current_date.isocalendar()
            )

            return (
                iso[0],
                iso[1] // 2
            )


        # Default = monthly

        return (
            current_date.year,
            current_date.month
        )


    def should_rebalance(
        self,
        current_date
    ):

        key = self.rebalance_key(
            current_date
        )


        if self.last_rebalance_key is None:

            self.last_rebalance_key = key

            return True


        if key != self.last_rebalance_key:

            self.last_rebalance_key = key

            return True


        return False


    # =========================================================
    # PRICE HELPERS
    # =========================================================

    def close_price(
        self,
        ticker,
        ohlcv,
        offset=0
    ):

        try:

            return float(
                ohlcv[
                    -1 - offset
                ][ticker]["close"]
            )

        except:

            return None


    def trailing_return(
        self,
        ticker,
        ohlcv,
        days
    ):

        if len(ohlcv) <= days:
            return None


        current = self.close_price(
            ticker,
            ohlcv
        )


        previous = self.close_price(
            ticker,
            ohlcv,
            days
        )


        if (
            current is None
            or previous is None
            or previous <= 0
        ):

            return None


        return (
            current / previous
        ) - 1.0


    # =========================================================
    # MOMENTUM FACTOR
    # =========================================================

    def momentum_score(
        self,
        ticker,
        ohlcv
    ):

        r3 = self.trailing_return(
            ticker,
            ohlcv,
            LOOKBACK_3M
        )


        r6 = self.trailing_return(
            ticker,
            ohlcv,
            LOOKBACK_6M
        )


        if (
            r3 is None
            or r6 is None
        ):

            return None


        total_weight = (
            MOMENTUM_3M_WEIGHT
            + MOMENTUM_6M_WEIGHT
        )


        if total_weight <= 0:
            return 0.0


        return (

            MOMENTUM_3M_WEIGHT
            * r3

            +

            MOMENTUM_6M_WEIGHT
            * r6

        ) / total_weight


    # =========================================================
    # VOLATILITY / RISK FACTOR
    # =========================================================

    def realized_volatility(
        self,
        ticker,
        ohlcv,
        days
    ):

        if len(ohlcv) <= days:
            return None


        prices = []


        for offset in range(
            days,
            -1,
            -1
        ):

            price = self.close_price(
                ticker,
                ohlcv,
                offset
            )


            if (
                price is None
                or price <= 0
            ):

                return None


            prices.append(
                price
            )


        log_returns = []


        for i in range(
            1,
            len(prices)
        ):

            log_returns.append(

                ln(
                    prices[i]
                    / prices[i - 1]
                )

            )


        if len(log_returns) < 2:
            return None


        mean_return = (

            sum(log_returns)
            / len(log_returns)

        )


        variance = (

            sum(
                (x - mean_return) ** 2
                for x in log_returns
            )

            / (len(log_returns) - 1)

        )


        return (
            sqrt(variance)
            * sqrt(252)
        )


    def risk_score(
        self,
        ticker,
        ohlcv
    ):

        volatility = (
            self.realized_volatility(
                ticker,
                ohlcv,
                VOLATILITY_LOOKBACK
            )
        )


        if volatility is None:
            return None


        # Negative volatility means:
        #
        # Lower volatility = better score.

        return -volatility


    # =========================================================
    # ALTERNATIVE DATA DATE FILTER
    # =========================================================

    def record_date(
        self,
        record
    ):

        fields = [
            "acceptedDate",
            "fillingDate",
            "filingDate",
            "publishedDate",
            "date"
        ]


        for field in fields:

            if field in record:

                parsed = self.parse_date(
                    record.get(field)
                )

                if parsed is not None:

                    return parsed


        return None


    def records_as_of(
        self,
        records,
        current_date
    ):

        if not records:
            return []


        available = []


        for record in records:

            record_date = (
                self.record_date(
                    record
                )
            )


            if record_date is None:
                continue


            if record_date <= current_date:

                available.append(
                    (
                        record_date,
                        record
                    )
                )


        available.sort(
            key=lambda x: x[0]
        )


        return [
            record
            for date, record
            in available
        ]


    # =========================================================
    # SENTIMENT FACTOR
    # =========================================================

    def sentiment_score(
        self,
        ticker,
        data,
        current_date
    ):

        records = data.get(
            (
                "social_sentiment",
                ticker
            ),
            []
        )


        records = self.records_as_of(
            records,
            current_date
        )


        if not records:
            return None


        recent = (
            records[
                -SENTIMENT_LOOKBACK:
            ]
        )


        scores = []


        for record in recent:

            values = []


            twitter = record.get(
                "twitterSentiment"
            )


            stocktwits = record.get(
                "stocktwitsSentiment"
            )


            if twitter is not None:

                try:

                    values.append(
                        float(twitter)
                    )

                except:
                    pass


            if stocktwits is not None:

                try:

                    values.append(
                        float(stocktwits)
                    )

                except:
                    pass


            if values:

                scores.append(
                    sum(values)
                    / len(values)
                )


        if not scores:
            return None


        return (
            sum(scores)
            / len(scores)
        )


    # =========================================================
    # FUNDAMENTAL FACTOR
    # =========================================================

    def fundamental_score(
        self,
        ticker,
        data,
        current_date
    ):

        statements = data.get(
            (
                "financial_statement",
                ticker
            ),
            []
        )


        statements = (
            self.records_as_of(
                statements,
                current_date
            )
        )


        if not statements:
            return None


        # Prefer annual reports.

        annual = [

            record

            for record
            in statements

            if record.get("period") == "FY"

        ]


        if len(annual) < 2:
            return None


        latest = annual[-1]

        previous = annual[-2]


        components = []


        # -----------------------------------------------------
        # REVENUE GROWTH
        # -----------------------------------------------------

        try:

            current_revenue = float(
                latest["revenue"]
            )

            previous_revenue = float(
                previous["revenue"]
            )


            if previous_revenue > 0:

                revenue_growth = (

                    current_revenue
                    / previous_revenue

                ) - 1.0


                components.append(
                    revenue_growth
                )

        except:
            pass


        # -----------------------------------------------------
        # NET INCOME GROWTH
        # -----------------------------------------------------

        try:

            current_income = float(
                latest["netIncome"]
            )

            previous_income = float(
                previous["netIncome"]
            )


            if previous_income > 0:

                income_growth = (

                    current_income
                    / previous_income

                ) - 1.0


                components.append(
                    income_growth
                )

        except:
            pass


        # -----------------------------------------------------
        # PROFITABILITY
        # -----------------------------------------------------

        try:

            margin = float(
                latest["netIncomeRatio"]
            )


            components.append(
                margin
            )

        except:
            pass


        try:

            operating_margin = float(
                latest[
                    "operatingIncomeRatio"
                ]
            )


            components.append(
                operating_margin
            )

        except:
            pass


        if not components:
            return None


        return (
            sum(components)
            / len(components)
        )


    # =========================================================
    # VALUATION FACTOR
    # =========================================================

    def valuation_score(
        self,
        ticker,
        data,
        current_date
    ):

        records = data.get(
            (
                "ratios",
                ticker
            ),
            []
        )


        if not records:
            return None


        # -----------------------------------------------------
        # CONSERVATIVE REPORTING LAG
        # -----------------------------------------------------
        #
        # Ratio records contain a period date but Surmount's
        # documented example does not include a filing date.
        #
        # Add a 45-day lag so the backtest does not immediately
        # use quarter-end ratios before investors could
        # realistically know them.
        # -----------------------------------------------------

        usable = []


        for record in records:

            date = self.parse_date(
                record.get("date")
            )


            if date is None:
                continue


            available_date = (
                date
                + timedelta(days=45)
            )


            if available_date <= current_date:

                usable.append(
                    (
                        date,
                        record
                    )
                )


        if not usable:
            return None


        usable.sort(
            key=lambda x: x[0]
        )


        latest = usable[-1][1]


        valuation_metrics = []


        # Lower P/E = better.

        pe = latest.get(
            "priceEarningsRatio"
        )


        if pe is not None:

            try:

                pe = float(pe)

                if (
                    pe > 0
                    and pe < 200
                ):

                    valuation_metrics.append(
                        -ln(pe)
                    )

            except:
                pass


        # Lower price/free-cash-flow = better.

        pfcf = latest.get(
            "priceToFreeCashFlowsRatio"
        )


        if pfcf is not None:

            try:

                pfcf = float(pfcf)

                if (
                    pfcf > 0
                    and pfcf < 300
                ):

                    valuation_metrics.append(
                        -ln(pfcf)
                    )

            except:
                pass


        # Lower price/sales = better.

        ps = latest.get(
            "priceToSalesRatio"
        )


        if ps is not None:

            try:

                ps = float(ps)

                if (
                    ps > 0
                    and ps < 100
                ):

                    valuation_metrics.append(
                        -ln(ps)
                    )

            except:
                pass


        if not valuation_metrics:
            return None


        return (
            sum(valuation_metrics)
            / len(valuation_metrics)
        )


    # =========================================================
    # Z-SCORE NORMALIZATION
    # =========================================================
    #
    # This allows metrics measured in completely different
    # units to be combined into one ranking score.
    # =========================================================

    def zscores(
        self,
        values
    ):

        valid = [

            value

            for value
            in values.values()

            if value is not None

        ]


        if len(valid) < 2:

            return {
                ticker: 0.0
                for ticker in values
            }


        average = (
            sum(valid)
            / len(valid)
        )


        variance = (

            sum(
                (value - average) ** 2
                for value in valid
            )

            / len(valid)

        )


        standard_deviation = (
            sqrt(variance)
        )


        if standard_deviation == 0:

            return {
                ticker: 0.0
                for ticker in values
            }


        result = {}


        for ticker, value in (
            values.items()
        ):

            if value is None:

                # Neutral rather than automatically
                # punishing missing data.

                result[ticker] = 0.0

            else:

                result[ticker] = (

                    value - average

                ) / standard_deviation


        return result


    # =========================================================
    # NORMALIZED FACTOR WEIGHTS
    # =========================================================

    def factor_weights(self):

        raw = {

            "fundamental":
                max(
                    0.0,
                    FUNDAMENTAL_WEIGHT
                ),

            "momentum":
                max(
                    0.0,
                    MOMENTUM_WEIGHT
                ),

            "sentiment":
                max(
                    0.0,
                    SENTIMENT_WEIGHT
                ),

            "valuation":
                max(
                    0.0,
                    VALUATION_WEIGHT
                ),

            "risk":
                max(
                    0.0,
                    RISK_WEIGHT
                )
        }


        total = sum(
            raw.values()
        )


        if total <= 0:

            return {
                "fundamental": 0.20,
                "momentum": 0.20,
                "sentiment": 0.20,
                "valuation": 0.20,
                "risk": 0.20
            }


        return {

            name:
                weight / total

            for name, weight
            in raw.items()

        }


    # =========================================================
    # MARKET TREND
    # =========================================================

    def simple_moving_average(
        self,
        ticker,
        ohlcv,
        days
    ):

        if len(ohlcv) < days:
            return None


        values = []


        for offset in range(
            days - 1,
            -1,
            -1
        ):

            price = self.close_price(
                ticker,
                ohlcv,
                offset
            )


            if price is None:
                return None


            values.append(
                price
            )


        return (
            sum(values)
            / len(values)
        )


    def equity_exposure(
        self,
        ohlcv
    ):

        if not USE_MARKET_TREND_FILTER:

            return 1.0


        spy_price = self.close_price(
            "SPY",
            ohlcv
        )


        trend = self.simple_moving_average(
            "SPY",
            ohlcv,
            MARKET_TREND_DAYS
        )


        if (
            spy_price is None
            or trend is None
        ):

            return 1.0


        if spy_price >= trend:

            return 1.0


        return max(
            0.0,
            min(
                1.0,
                RISK_OFF_EQUITY_EXPOSURE
            )
        )


    # =========================================================
    # MAIN STRATEGY
    # =========================================================

    def run(
        self,
        data
    ):

        ohlcv = data.get(
            "ohlcv"
        )


        required_history = max(
            LOOKBACK_6M,
            VOLATILITY_LOOKBACK,
            MARKET_TREND_DAYS
            if USE_MARKET_TREND_FILTER
            else 0
        ) + 5


        if (
            ohlcv is None
            or len(ohlcv) < required_history
        ):

            return TargetAllocation({})


        current_date = (
            self.current_date(
                ohlcv
            )
        )


        if current_date is None:

            return TargetAllocation({})


        # -----------------------------------------------------
        # HOLD CURRENT PORTFOLIO BETWEEN REBALANCES
        # -----------------------------------------------------

        if (
            self.last_target
            and not self.should_rebalance(
                current_date
            )
        ):

            return TargetAllocation(
                self.last_target
            )


        if self.last_rebalance_key is None:

            self.last_rebalance_key = (
                self.rebalance_key(
                    current_date
                )
            )


        # -----------------------------------------------------
        # RAW FACTOR VALUES
        # -----------------------------------------------------

        fundamentals = {}
        momentum = {}
        sentiment = {}
        valuation = {}
        risk = {}


        for ticker in self.stock_universe:

            fundamentals[ticker] = (
                self.fundamental_score(
                    ticker,
                    data,
                    current_date
                )
            )


            momentum[ticker] = (
                self.momentum_score(
                    ticker,
                    ohlcv
                )
            )


            sentiment[ticker] = (
                self.sentiment_score(
                    ticker,
                    data,
                    current_date
                )
            )


            valuation[ticker] = (
                self.valuation_score(
                    ticker,
                    data,
                    current_date
                )
            )


            risk[ticker] = (
                self.risk_score(
                    ticker,
                    ohlcv
                )
            )


        # -----------------------------------------------------
        # STANDARDIZE FACTORS
        # -----------------------------------------------------

        fundamental_z = (
            self.zscores(
                fundamentals
            )
        )


        momentum_z = (
            self.zscores(
                momentum
            )
        )


        sentiment_z = (
            self.zscores(
                sentiment
            )
        )


        valuation_z = (
            self.zscores(
                valuation
            )
        )


        risk_z = (
            self.zscores(
                risk
            )
        )


        weights = (
            self.factor_weights()
        )


        # -----------------------------------------------------
        # FINAL HYBRID AI SCORE
        # -----------------------------------------------------

        composite = {}


        for ticker in self.stock_universe:

            composite[ticker] = (

                weights["fundamental"]
                * fundamental_z[ticker]

                +

                weights["momentum"]
                * momentum_z[ticker]

                +

                weights["sentiment"]
                * sentiment_z[ticker]

                +

                weights["valuation"]
                * valuation_z[ticker]

                +

                weights["risk"]
                * risk_z[ticker]

            )


        # -----------------------------------------------------
        # RANK STOCKS
        # -----------------------------------------------------

        ranking = sorted(

            self.stock_universe,

            key=lambda ticker:
                composite[ticker],

            reverse=True

        )


        holdings_count = max(
            1,
            min(
                NUMBER_OF_HOLDINGS,
                len(ranking)
            )
        )


        selected = ranking[
            :holdings_count
        ]


        # -----------------------------------------------------
        # MARKET REGIME
        # -----------------------------------------------------

        equity_allocation = (
            self.equity_exposure(
                ohlcv
            )
        )


        defensive_allocation = (
            1.0
            - equity_allocation
        )


        # -----------------------------------------------------
        # EQUAL WEIGHT SELECTED STOCKS
        # -----------------------------------------------------

        stock_weight = (

            equity_allocation
            / len(selected)

        )


        allocation = {

            ticker:
                stock_weight

            for ticker
            in selected

        }


        if defensive_allocation > 0:

            allocation[
                DEFENSIVE_TICKER
            ] = (
                defensive_allocation
            )


        # -----------------------------------------------------
        # SAVE PORTFOLIO
        # -----------------------------------------------------

        self.last_target = (
            allocation.copy()
        )


        # -----------------------------------------------------
        # LOGGING
        # -----------------------------------------------------

        log(
            "Hybrid AI factor weights: "
            + str(weights)
        )


        log(
            "Rebalance frequency: "
            + REBALANCE_FREQUENCY
        )


        log(
            "Selected stocks: "
            + str(selected)
        )


        log(
            "Composite ranking: "
            + str(ranking)
        )


        log(
            "Composite scores: "
            + str(composite)
        )


        log(
            "Equity exposure: "
            + str(equity_allocation)
        )


        log(
            "Target allocation: "
            + str(allocation)
        )


        return TargetAllocation(
            allocation
        )