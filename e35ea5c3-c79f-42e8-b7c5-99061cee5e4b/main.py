from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# USER CONFIGURATION
# =============================================================

# -------------------------------------------------------------
# REBALANCING
# -------------------------------------------------------------
#
# Options:
# "weekly"
# "biweekly"
# "monthly"
#

REBALANCE_FREQUENCY = "weekly"


# -------------------------------------------------------------
# TREND FILTER
# -------------------------------------------------------------

TREND_SMA = 200
FAST_SMA = 50


# -------------------------------------------------------------
# MOMENTUM LOOKBACKS
# -------------------------------------------------------------

LOOKBACK_3M = 63
LOOKBACK_6M = 126
LOOKBACK_12M = 252
SKIP_RECENT = 21


# -------------------------------------------------------------
# COMPOSITE MOMENTUM WEIGHTS
# -------------------------------------------------------------
#
# Inspired by Surmount's discussion of:
#
# - medium-term momentum
# - 12-1 momentum
# - RSI signal strength
#

WEIGHT_3M = 0.30
WEIGHT_6M = 0.30
WEIGHT_12_MINUS_1 = 0.25
WEIGHT_RSI = 0.15


# -------------------------------------------------------------
# ABSOLUTE MOMENTUM FILTER
# -------------------------------------------------------------
#
# A risk asset must have positive 6-month momentum.
#

REQUIRE_POSITIVE_6M = True


# -------------------------------------------------------------
# RSI
# -------------------------------------------------------------

RSI_PERIOD = 14


# -------------------------------------------------------------
# PORTFOLIO SIZE
# -------------------------------------------------------------

MAX_RISK_ASSETS = 3


# -------------------------------------------------------------
# LEVERAGE LIMIT
# -------------------------------------------------------------
#
# Total maximum allocation to:
# QLD + TQQQ + SPXL
#

MAX_LEVERAGED_EXPOSURE = 0.25


# -------------------------------------------------------------
# VOLATILITY CONTROL
# -------------------------------------------------------------
#
# When short-term QQQ volatility exceeds this multiple
# of long-term volatility, risk exposure is reduced.
#

VOL_SHORT = 20
VOL_LONG = 100
VOL_THRESHOLD = 1.50

HIGH_VOL_RISK_MULTIPLIER = 0.50


# -------------------------------------------------------------
# DEFENSIVE ALLOCATION
# -------------------------------------------------------------

DEFENSIVE_GLD_WEIGHT = 0.30
DEFENSIVE_SGOV_WEIGHT = 0.70


# =============================================================
# STRATEGY
# =============================================================

class TradingStrategy(Strategy):

    def __init__(self):

        self.risk_assets = [
            "QQQ",
            "SOXX",
            "SMH",
            "XLI",
            "QLD",
            "TQQQ",
            "SPXL"
        ]

        self.leveraged_assets = [
            "QLD",
            "TQQQ",
            "SPXL"
        ]

        self.defensive_assets = [
            "GLD",
            "SGOV"
        ]

        # SPY is only used as a market regime indicator.
        self.tickers = [
            "SPY"
        ] + self.risk_assets + self.defensive_assets

        self.last_target = {}
        self.last_rebalance_key = None


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
        return []


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


        past = self.close_price(
            ticker,
            ohlcv,
            days
        )


        if (
            current is None
            or past is None
            or past <= 0
        ):

            return None


        return (
            current / past
        ) - 1.0


    # =========================================================
    # 12-MONTH MINUS MOST RECENT MONTH MOMENTUM
    # =========================================================
    #
    # Measures return from roughly 12 months ago
    # through one month ago.
    #
    # This intentionally excludes the most recent month.
    # =========================================================

    def twelve_minus_one_return(
        self,
        ticker,
        ohlcv
    ):

        if len(ohlcv) <= LOOKBACK_12M:
            return None


        old_price = self.close_price(
            ticker,
            ohlcv,
            LOOKBACK_12M
        )


        one_month_ago = self.close_price(
            ticker,
            ohlcv,
            SKIP_RECENT
        )


        if (
            old_price is None
            or one_month_ago is None
            or old_price <= 0
        ):

            return None


        return (
            one_month_ago
            / old_price
        ) - 1.0


    # =========================================================
    # REALIZED VOLATILITY
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


        average = (
            sum(returns)
            / len(returns)
        )


        variance = (

            sum(
                (r - average) ** 2
                for r in returns
            )

            / (len(returns) - 1)

        )


        return (
            sqrt(variance)
            * sqrt(252)
        )


    # =========================================================
    # DATE / REBALANCE LOGIC
    # =========================================================

    def current_date(
        self,
        ohlcv
    ):

        try:

            value = str(
                ohlcv[-1]["SPY"]["date"]
            )

            return datetime.strptime(
                value[:10],
                "%Y-%m-%d"
            )

        except:

            return None


    def rebalance_key(
        self,
        current_date
    ):

        if REBALANCE_FREQUENCY == "weekly":

            iso = current_date.isocalendar()

            return (
                iso[0],
                iso[1]
            )


        if REBALANCE_FREQUENCY == "biweekly":

            iso = current_date.isocalendar()

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
                (value - average) ** 2
                for value in valid
            )

            / len(valid)

        )


        standard_deviation = sqrt(
            variance
        )


        if standard_deviation == 0:

            return {
                ticker: 0.0
                for ticker in values
            }


        result = {}


        for ticker, value in values.items():

            if value is None:

                result[ticker] = 0.0

            else:

                result[ticker] = (

                    value - average

                ) / standard_deviation


        return result


    # =========================================================
    # DEFENSIVE PORTFOLIO
    # =========================================================

    def defensive_allocation(
        self
    ):

        return {

            "SGOV":
                DEFENSIVE_SGOV_WEIGHT,

            "GLD":
                DEFENSIVE_GLD_WEIGHT

        }


    # =========================================================
    # ALLOCATION CLEANUP
    # =========================================================

    def clean_allocation(
        self,
        allocation
    ):

        cleaned = {}


        for ticker, weight in allocation.items():

            if weight > 0:

                cleaned[ticker] = float(
                    weight
                )


        total = sum(
            cleaned.values()
        )


        if total > 1.0:

            cleaned = {

                ticker:
                    weight / total

                for ticker, weight
                in cleaned.items()

            }


        return cleaned


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


        # Need enough history for:
        #
        # 200-day trend
        # 252-day 12-1 momentum
        #

        required_history = max(
            TREND_SMA,
            LOOKBACK_12M,
            VOL_LONG
        ) + 10


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


        # =====================================================
        # HOLD EXISTING PORTFOLIO BETWEEN REBALANCES
        # =====================================================

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


        # =====================================================
        # MARKET TREND REGIME
        # =====================================================

        spy_price = self.close_price(
            "SPY",
            ohlcv
        )


        qqq_price = self.close_price(
            "QQQ",
            ohlcv
        )


        spy_sma = SMA(
            "SPY",
            ohlcv,
            TREND_SMA
        )


        qqq_sma = SMA(
            "QQQ",
            ohlcv,
            TREND_SMA
        )


        qqq_fast = SMA(
            "QQQ",
            ohlcv,
            FAST_SMA
        )


        if (
            spy_price is None
            or qqq_price is None
            or spy_sma is None
            or qqq_sma is None
            or qqq_fast is None
        ):

            return TargetAllocation({})


        market_risk_on = (

            spy_price
            > spy_sma[-1]

            and

            qqq_price
            > qqq_sma[-1]

            and

            qqq_fast[-1]
            > qqq_sma[-1]

        )


        # =====================================================
        # FULL RISK-OFF
        # =====================================================

        if not market_risk_on:

            allocation = (
                self.defensive_allocation()
            )

            self.last_target = allocation

            log(
                "Market regime: RISK OFF"
            )

            log(
                "Allocation: "
                + str(allocation)
            )

            return TargetAllocation(
                allocation
            )


        # =====================================================
        # RAW MOMENTUM SIGNALS
        # =====================================================

        returns_3m = {}
        returns_6m = {}
        returns_12_1 = {}
        rsi_values = {}


        for ticker in self.risk_assets:

            returns_3m[ticker] = (
                self.trailing_return(
                    ticker,
                    ohlcv,
                    LOOKBACK_3M
                )
            )


            returns_6m[ticker] = (
                self.trailing_return(
                    ticker,
                    ohlcv,
                    LOOKBACK_6M
                )
            )


            returns_12_1[ticker] = (
                self.twelve_minus_one_return(
                    ticker,
                    ohlcv
                )
            )


            try:

                rsi_series = RSI(
                    ticker,
                    ohlcv,
                    RSI_PERIOD
                )

                rsi_values[ticker] = (
                    float(
                        rsi_series[-1]
                    )
                )

            except:

                rsi_values[ticker] = None


        # =====================================================
        # ABSOLUTE MOMENTUM FILTER
        # =====================================================

        eligible = []


        for ticker in self.risk_assets:

            price = self.close_price(
                ticker,
                ohlcv
            )


            trend = SMA(
                ticker,
                ohlcv,
                TREND_SMA
            )


            if (
                price is None
                or trend is None
            ):

                continue


            above_trend = (
                price > trend[-1]
            )


            positive_6m = (
                returns_6m[ticker] is not None
                and returns_6m[ticker] > 0
            )


            if (
                above_trend
                and (
                    positive_6m
                    or not REQUIRE_POSITIVE_6M
                )
            ):

                eligible.append(
                    ticker
                )


        # No qualifying momentum assets.
        if not eligible:

            allocation = (
                self.defensive_allocation()
            )

            self.last_target = allocation

            return TargetAllocation(
                allocation
            )


        # =====================================================
        # STANDARDIZE SIGNALS
        # =====================================================

        z3 = self.zscores(
            {
                ticker: returns_3m[ticker]
                for ticker in eligible
            }
        )


        z6 = self.zscores(
            {
                ticker: returns_6m[ticker]
                for ticker in eligible
            }
        )


        z12 = self.zscores(
            {
                ticker: returns_12_1[ticker]
                for ticker in eligible
            }
        )


        zrsi = self.zscores(
            {
                ticker: rsi_values[ticker]
                for ticker in eligible
            }
        )


        # =====================================================
        # COMPOSITE MOMENTUM SCORE
        # =====================================================

        composite = {}


        for ticker in eligible:

            composite[ticker] = (

                WEIGHT_3M
                * z3[ticker]

                +

                WEIGHT_6M
                * z6[ticker]

                +

                WEIGHT_12_MINUS_1
                * z12[ticker]

                +

                WEIGHT_RSI
                * zrsi[ticker]

            )


        ranked = sorted(

            eligible,

            key=lambda ticker:
                composite[ticker],

            reverse=True

        )


        selected = ranked[
            :MAX_RISK_ASSETS
        ]


        # =====================================================
        # PROPORTIONAL MOMENTUM WEIGHTING
        # =====================================================
        #
        # Rather than fixed 50/25/25 weights,
        # stronger momentum signals receive larger weights.
        #
        # Shift scores so all selected positions have
        # positive sizing values.
        # =====================================================

        minimum_score = min(
            composite[ticker]
            for ticker in selected
        )


        adjusted_scores = {}


        for ticker in selected:

            adjusted_scores[ticker] = (

                composite[ticker]
                - minimum_score
                + 0.10

            )


        score_total = sum(
            adjusted_scores.values()
        )


        raw_weights = {

            ticker:
                adjusted_scores[ticker]
                / score_total

            for ticker in selected

        }


        # =====================================================
        # LEVERAGE CAP
        # =====================================================

        leveraged_total = sum(

            raw_weights.get(
                ticker,
                0.0
            )

            for ticker in self.leveraged_assets

        )


        if (
            leveraged_total
            > MAX_LEVERAGED_EXPOSURE
        ):

            scale = (

                MAX_LEVERAGED_EXPOSURE
                / leveraged_total

            )


            removed_weight = 0.0


            for ticker in self.leveraged_assets:

                if ticker in raw_weights:

                    old_weight = (
                        raw_weights[ticker]
                    )

                    new_weight = (
                        old_weight
                        * scale
                    )

                    removed_weight += (
                        old_weight
                        - new_weight
                    )

                    raw_weights[ticker] = (
                        new_weight
                    )


            # Redistribute removed leverage allocation
            # proportionally across non-leveraged selections.

            nonleveraged_selected = [

                ticker

                for ticker in selected

                if ticker
                not in self.leveraged_assets

            ]


            if nonleveraged_selected:

                base_total = sum(

                    raw_weights[ticker]

                    for ticker
                    in nonleveraged_selected

                )


                if base_total > 0:

                    for ticker in (
                        nonleveraged_selected
                    ):

                        share = (

                            raw_weights[ticker]
                            / base_total

                        )

                        raw_weights[ticker] += (

                            removed_weight
                            * share

                        )

                else:

                    raw_weights[
                        "SGOV"
                    ] = (
                        raw_weights.get(
                            "SGOV",
                            0.0
                        )
                        + removed_weight
                    )

            else:

                raw_weights[
                    "SGOV"
                ] = (
                    raw_weights.get(
                        "SGOV",
                        0.0
                    )
                    + removed_weight
                )


        # =====================================================
        # VOLATILITY SCALING
        # =====================================================

        vol_short = (
            self.realized_volatility(
                "QQQ",
                ohlcv,
                VOL_SHORT
            )
        )


        vol_long = (
            self.realized_volatility(
                "QQQ",
                ohlcv,
                VOL_LONG
            )
        )


        risk_multiplier = 1.0


        if (
            vol_short is not None
            and vol_long is not None
            and vol_long > 0
            and vol_short
                > VOL_THRESHOLD * vol_long
        ):

            risk_multiplier = (
                HIGH_VOL_RISK_MULTIPLIER
            )


        # =====================================================
        # FINAL PORTFOLIO
        # =====================================================

        allocation = {}


        for ticker, weight in (
            raw_weights.items()
        ):

            allocation[ticker] = (
                weight
                * risk_multiplier
            )


        unused = (

            1.0
            - sum(allocation.values())

        )


        if unused > 0:

            allocation[
                "SGOV"
            ] = (
                allocation.get(
                    "SGOV",
                    0.0
                )
                + unused
            )


        allocation = (
            self.clean_allocation(
                allocation
            )
        )


        self.last_target = (
            allocation.copy()
        )


        # =====================================================
        # LOGGING
        # =====================================================

        log(
            "Market regime: RISK ON"
        )


        log(
            "Eligible assets: "
            + str(eligible)
        )


        log(
            "Momentum scores: "
            + str(composite)
        )


        log(
            "Selected assets: "
            + str(selected)
        )


        log(
            "Volatility multiplier: "
            + str(risk_multiplier)
        )


        log(
            "Target allocation: "
            + str(allocation)
        )


        return TargetAllocation(
            allocation
        )