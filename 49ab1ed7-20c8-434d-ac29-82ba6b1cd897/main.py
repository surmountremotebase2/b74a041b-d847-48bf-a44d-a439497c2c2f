#Type code here
from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.data import SocialSentiment, FinancialStatement, Ratios

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# USER CONFIGURATION
# =============================================================

# Number of stocks to hold.
PORTFOLIO_SIZE = 15

# Approximate scoring model.
#
# IMPORTANT:
# These are NOT Dr. Lira's proprietary weights.
# They are a transparent approximation of an AI stock-ranking process.
SENTIMENT_WEIGHT = 0.40
MOMENTUM_WEIGHT = 0.30
FUNDAMENTAL_WEIGHT = 0.20
RISK_WEIGHT = 0.10

# Momentum periods in trading days.
MOMENTUM_3M = 63
MOMENTUM_6M = 126

# Recent sentiment observations to average.
SENTIMENT_LOOKBACK = 7

# Risk calculation.
VOLATILITY_LOOKBACK = 63


# =============================================================
# STOCK UNIVERSE
# =============================================================
#
# This is intentionally configurable.
# The public GPT Portfolio's complete investable universe
# is not publicly disclosed.
#
# These are liquid US large/mid-cap growth and quality stocks.
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
    "NFLX",
    "ORCL",
    "CRM",
    "NOW",
    "ADBE",
    "INTU",
    "PANW",
    "CRWD",
    "ANET",
    "AMAT",
    "LRCX",
    "KLAC",
    "MU",
    "QCOM",
    "TXN",
    "PLTR",
    "UBER",
    "SHOP",
    "MELI",
    "V",
    "MA",
    "JPM",
    "GS",
    "COST",
    "WMT",
    "HD",
    "CAT",
    "GE",
    "ETN",
    "VRT",
    "CEG",
    "VST"
]


class TradingStrategy(Strategy):

    def __init__(self):

        self.tickers = STOCK_UNIVERSE

        # Request Surmount alternative data.
        self.data_list = []

        for ticker in self.tickers:

            self.data_list.append(
                SocialSentiment(ticker)
            )

            self.data_list.append(
                FinancialStatement(ticker)
            )

            self.data_list.append(
                Ratios(ticker)
            )

        # Preserve monthly portfolio between rebalances.
        self.last_target = {}

        self.last_rebalance_month = None


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

        value = str(value)

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ"
        ]

        for fmt in formats:

            try:
                return datetime.strptime(
                    value[:19],
                    fmt
                )
            except:
                pass

        try:
            return datetime.strptime(
                value[:10],
                "%Y-%m-%d"
            )

        except:
            return None


    def current_date(self, ohlcv):

        if not ohlcv:
            return None

        # Use the first ticker for date extraction.
        ticker = self.tickers[0]

        try:

            return self.parse_date(
                ohlcv[-1][ticker]["date"]
            )

        except:

            return None


    # =========================================================
    # PREVENT LOOK-AHEAD BIAS
    # =========================================================
    #
    # Alternative datasets can contain historical records.
    # Only use records that would have been known on the
    # current backtest date.
    # =========================================================

    def record_date(
        self,
        record
    ):

        possible_fields = [
            "acceptedDate",
            "fillingDate",
            "filingDate",
            "date",
            "publishedDate"
        ]

        for field in possible_fields:

            if field in record:

                parsed = self.parse_date(
                    record.get(field)
                )

                if parsed is not None:
                    return parsed

        return None


    def records_available_as_of(
        self,
        records,
        as_of_date
    ):

        if not records:
            return []

        available = []

        for record in records:

            date = self.record_date(
                record
            )

            if date is None:
                continue

            if date <= as_of_date:

                available.append(
                    (date, record)
                )

        available.sort(
            key=lambda x: x[0]
        )

        return [
            item[1]
            for item in available
        ]


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
    # MOMENTUM SCORE
    # =========================================================

    def momentum_score(
        self,
        ticker,
        ohlcv
    ):

        three_month = (
            self.trailing_return(
                ticker,
                ohlcv,
                MOMENTUM_3M
            )
        )

        six_month = (
            self.trailing_return(
                ticker,
                ohlcv,
                MOMENTUM_6M
            )
        )

        if (
            three_month is None
            or six_month is None
        ):
            return None

        return (
            0.50 * three_month
            + 0.50 * six_month
        )


    # =========================================================
    # REALIZED VOLATILITY / RISK
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

        returns = []

        for i in range(
            1,
            len(prices)
        ):

            returns.append(
                ln(
                    prices[i]
                    / prices[i - 1]
                )
            )

        if len(returns) < 2:
            return None

        mean_return = (
            sum(returns)
            / len(returns)
        )

        variance = sum(
            (x - mean_return) ** 2
            for x in returns
        ) / (
            len(returns) - 1
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

        # Lower volatility receives a higher score.
        return -volatility


    # =========================================================
    # SOCIAL / NEWS SENTIMENT PROXY
    # =========================================================

    def sentiment_score(
        self,
        ticker,
        data,
        as_of_date
    ):

        records = data.get(
            (
                "social_sentiment",
                ticker
            ),
            []
        )

        records = (
            self.records_available_as_of(
                records,
                as_of_date
            )
        )

        if not records:
            return None

        recent = records[
            -SENTIMENT_LOOKBACK:
        ]

        values = []

        for item in recent:

            twitter = item.get(
                "twitterSentiment"
            )

            stocktwits = item.get(
                "stocktwitsSentiment"
            )

            daily_values = []

            if twitter is not None:

                try:
                    daily_values.append(
                        float(twitter)
                    )
                except:
                    pass

            if stocktwits is not None:

                try:
                    daily_values.append(
                        float(stocktwits)
                    )
                except:
                    pass

            if daily_values:

                values.append(
                    sum(daily_values)
                    / len(daily_values)
                )

        if not values:
            return None

        return (
            sum(values)
            / len(values)
        )


    # =========================================================
    # FUNDAMENTAL SCORE
    # =========================================================

    def fundamental_score(
        self,
        ticker,
        data,
        as_of_date
    ):

        statements = data.get(
            (
                "financial_statement",
                ticker
            ),
            []
        )

        ratios = data.get(
            (
                "ratios",
                ticker
            ),
            []
        )

        statements = (
            self.records_available_as_of(
                statements,
                as_of_date
            )
        )

        ratios = (
            self.records_available_as_of(
                ratios,
                as_of_date
            )
        )

        # Prefer annual statements when possible.
        annual = [
            x
            for x in statements
            if x.get("period") == "FY"
        ]

        score_parts = []

        # -----------------------------------------------------
        # REVENUE + EARNINGS GROWTH
        # -----------------------------------------------------

        if len(annual) >= 2:

            latest = annual[-1]
            previous = annual[-2]

            latest_revenue = latest.get(
                "revenue"
            )

            previous_revenue = previous.get(
                "revenue"
            )

            latest_income = latest.get(
                "netIncome"
            )

            previous_income = previous.get(
                "netIncome"
            )

            try:

                if (
                    latest_revenue is not None
                    and previous_revenue
                    and previous_revenue > 0
                ):

                    revenue_growth = (
                        float(latest_revenue)
                        / float(previous_revenue)
                    ) - 1.0

                    score_parts.append(
                        revenue_growth
                    )

            except:
                pass

            try:

                if (
                    latest_income is not None
                    and previous_income
                    and previous_income > 0
                ):

                    earnings_growth = (
                        float(latest_income)
                        / float(previous_income)
                    ) - 1.0

                    score_parts.append(
                        earnings_growth
                    )

            except:
                pass


        # -----------------------------------------------------
        # PROFITABILITY
        # -----------------------------------------------------

        if ratios:

            latest_ratio = ratios[-1]

            profitability_fields = [
                "netProfitMargin",
                "returnOnEquity",
                "returnOnAssets"
            ]

            for field in profitability_fields:

                value = latest_ratio.get(
                    field
                )

                if value is not None:

                    try:

                        score_parts.append(
                            float(value)
                        )

                    except:
                        pass


        if not score_parts:
            return None

        return (
            sum(score_parts)
            / len(score_parts)
        )


    # =========================================================
    # CROSS-SECTIONAL Z-SCORE
    # =========================================================

    def zscores(
        self,
        values
    ):

        valid = [
            value
            for value in values.values()
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
                (x - average) ** 2
                for x in valid
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

                # Missing data gets neutral score.
                result[ticker] = 0.0

            else:

                result[ticker] = (
                    value - average
                ) / standard_deviation

        return result


    # =========================================================
    # MONTHLY REBALANCE CHECK
    # =========================================================

    def should_rebalance(
        self,
        as_of_date
    ):

        month_key = (
            as_of_date.year,
            as_of_date.month
        )

        if (
            self.last_rebalance_month
            is None
        ):

            self.last_rebalance_month = (
                month_key
            )

            return True

        if (
            month_key
            != self.last_rebalance_month
        ):

            self.last_rebalance_month = (
                month_key
            )

            return True

        return False


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

        if (
            ohlcv is None
            or len(ohlcv)
            < MOMENTUM_6M + 10
        ):

            return TargetAllocation({})


        as_of_date = self.current_date(
            ohlcv
        )

        if as_of_date is None:

            return TargetAllocation({})


        # -----------------------------------------------------
        # HOLD EXISTING PORTFOLIO BETWEEN MONTHLY REBALANCES
        # -----------------------------------------------------

        if (
            self.last_target
            and not self.should_rebalance(
                as_of_date
            )
        ):

            return TargetAllocation(
                self.last_target
            )


        # Ensure the first portfolio creation
        # records the current month.
        if (
            self.last_rebalance_month
            is None
        ):

            self.last_rebalance_month = (
                as_of_date.year,
                as_of_date.month
            )


        # -----------------------------------------------------
        # BUILD RAW FACTOR SCORES
        # -----------------------------------------------------

        sentiment_raw = {}
        momentum_raw = {}
        fundamental_raw = {}
        risk_raw = {}


        for ticker in self.tickers:

            sentiment_raw[ticker] = (
                self.sentiment_score(
                    ticker,
                    data,
                    as_of_date
                )
            )

            momentum_raw[ticker] = (
                self.momentum_score(
                    ticker,
                    ohlcv
                )
            )

            fundamental_raw[ticker] = (
                self.fundamental_score(
                    ticker,
                    data,
                    as_of_date
                )
            )

            risk_raw[ticker] = (
                self.risk_score(
                    ticker,
                    ohlcv
                )
            )


        # -----------------------------------------------------
        # NORMALIZE EACH FACTOR
        # -----------------------------------------------------

        sentiment_z = self.zscores(
            sentiment_raw
        )

        momentum_z = self.zscores(
            momentum_raw
        )

        fundamental_z = self.zscores(
            fundamental_raw
        )

        risk_z = self.zscores(
            risk_raw
        )


        # -----------------------------------------------------
        # GPT-STYLE COMPOSITE RANKING
        # -----------------------------------------------------

        composite = {}


        for ticker in self.tickers:

            composite[ticker] = (

                SENTIMENT_WEIGHT
                * sentiment_z[ticker]

                +

                MOMENTUM_WEIGHT
                * momentum_z[ticker]

                +

                FUNDAMENTAL_WEIGHT
                * fundamental_z[ticker]

                +

                RISK_WEIGHT
                * risk_z[ticker]

            )


        ranked = sorted(
            self.tickers,
            key=lambda ticker:
                composite[ticker],
            reverse=True
        )


        # -----------------------------------------------------
        # SELECT TOP 15
        # -----------------------------------------------------

        selected = ranked[
            :PORTFOLIO_SIZE
        ]


        if not selected:

            return TargetAllocation({})


        # Equal-weight portfolio.
        weight = (
            1.0
            / len(selected)
        )


        allocation = {
            ticker: weight
            for ticker in selected
        }


        self.last_target = (
            allocation.copy()
        )


        # -----------------------------------------------------
        # DEBUG LOGGING
        # -----------------------------------------------------

        log(
            "GPT-style monthly ranking:"
            + str(ranked)
        )

        log(
            "Selected portfolio:"
            + str(selected)
        )

        log(
            "Composite scores:"
            + str(composite)
        )

        log(
            "Allocation:"
            + str(allocation)
        )


        return TargetAllocation(
            allocation
        )