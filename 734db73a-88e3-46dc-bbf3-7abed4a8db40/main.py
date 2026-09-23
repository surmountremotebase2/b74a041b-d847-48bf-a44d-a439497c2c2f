#Type code here
from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# MOMENTUM V2.3
# DIVERSIFIED MONTHLY MOMENTUM
# + ADAPTIVE QLD LEVERAGE
# =============================================================
#
# CORE STRATEGY:
# Same as Momentum V2 Monthly
#
# NEW EXPERIMENT:
#
# Normal market:
#     0% QLD
#
# Strong Nasdaq momentum:
#     5% QLD
#
# Exceptional Nasdaq momentum:
#     10% QLD
#
# High-volatility regime:
#     0% QLD
#
# =============================================================


# =============================================================
# USER SETTINGS
# =============================================================


# -------------------------------------------------------------
# PORTFOLIO
# -------------------------------------------------------------

MAX_HOLDINGS = 4


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


# -------------------------------------------------------------
# CORE MOMENTUM SCORE
# -------------------------------------------------------------

WEIGHT_3M = 0.40
WEIGHT_6M = 0.40
WEIGHT_RSI = 0.20

RSI_PERIOD = 14


# -------------------------------------------------------------
# ABSOLUTE MOMENTUM
# -------------------------------------------------------------

REQUIRE_POSITIVE_6M = True


# -------------------------------------------------------------
# SIGNAL-STRENGTH POSITION SIZING
# -------------------------------------------------------------

SIGNAL_WEIGHT_BLEND = 0.65
SIGNAL_FLOOR = 0.25


# -------------------------------------------------------------
# MAXIMUM CORE ETF WEIGHT
# -------------------------------------------------------------

MAX_SINGLE_ASSET_WEIGHT = 0.35


# -------------------------------------------------------------
# VOLATILITY CONTROL
# -------------------------------------------------------------

VOL_SHORT = 20
VOL_LONG = 100

VOL_THRESHOLD = 1.50

HIGH_VOL_RISK_MULTIPLIER = 0.50


# -------------------------------------------------------------
# DEFENSIVE PORTFOLIO
# -------------------------------------------------------------

DEFENSIVE_SGOV_WEIGHT = 0.70
DEFENSIVE_GLD_WEIGHT = 0.30


# =============================================================
# V2.3 ADAPTIVE LEVERAGE SETTINGS
# =============================================================

ENABLE_ADAPTIVE_LEVERAGE = True

LEVERAGED_TICKER = "QLD"


# -------------------------------------------------------------
# STRONG MOMENTUM REGIME
# -------------------------------------------------------------
#
# Requirements:
#
# QQQ must be selected in Top 4
# QQQ composite momentum score > 0
# QQQ above long-term trend
# QQQ 50 SMA > 200 SMA
# QQQ 3M return > 8%
# QQQ 6M return > 12%
# Market volatility must be normal
#
# Result:
#
# 5% QLD
#

STRONG_LEVERAGE_SLEEVE = 0.05

STRONG_QQQ_3M = 0.08
STRONG_QQQ_6M = 0.12


# -------------------------------------------------------------
# EXCEPTIONAL MOMENTUM REGIME
# -------------------------------------------------------------
#
# More demanding:
#
# QQQ must rank Top 2
# QQQ composite momentum score > 0
# QQQ 3M return > 12%
# QQQ 6M return > 20%
# Market volatility must be normal
#
# Result:
#
# 10% QLD
#

EXCEPTIONAL_LEVERAGE_SLEEVE = 0.10

EXCEPTIONAL_QQQ_3M = 0.12
EXCEPTIONAL_QQQ_6M = 0.20


# =============================================================
# STRATEGY
# =============================================================

class TradingStrategy(Strategy):

    def __init__(self):

        # =====================================================
        # DIVERSIFIED CORE UNIVERSE
        # =====================================================

        self.core_assets = [

            "QQQ",
            "IWM",
            "VTV",

            "SMH",

            "XLI",
            "XLF",
            "XLV",
            "XLE",
            "XLP",

            "EFA",
            "EEM",

            "VNQ",

            "GLD",
            "TLT"

        ]


        self.tickers = list(

            dict.fromkeys(

                [
                    "SPY",
                    "SGOV",
                    "QLD"
                ]

                + self.core_assets

            )

        )


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
    # PRICE HELPER
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


    # =========================================================
    # TRAILING RETURN
    # =========================================================

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

                (value - average) ** 2

                for value in returns

            )

            / (len(returns) - 1)

        )


        return (

            sqrt(variance)
            * sqrt(252)

        )


    # =========================================================
    # DATE
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


    # =========================================================
    # MONTHLY REBALANCE KEY
    # =========================================================

    def rebalance_key(
        self,
        date
    ):

        return (

            date.year,
            date.month

        )


    # =========================================================
    # Z-SCORES
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

                for ticker
                in values

            }


        average = (

            sum(valid)
            / len(valid)

        )


        variance = (

            sum(

                (value - average) ** 2

                for value
                in valid

            )

            / len(valid)

        )


        standard_deviation = sqrt(
            variance
        )


        if standard_deviation == 0:

            return {

                ticker: 0.0

                for ticker
                in values

            }


        output = {}


        for ticker, value in values.items():

            if value is None:

                output[ticker] = 0.0

            else:

                output[ticker] = (

                    value - average

                ) / standard_deviation


        return output


    # =========================================================
    # DEFENSIVE PORTFOLIO
    # =========================================================

    def defensive_portfolio(self):

        return {

            "SGOV":
                DEFENSIVE_SGOV_WEIGHT,

            "GLD":
                DEFENSIVE_GLD_WEIGHT

        }


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


        # =====================================================
        # MINIMUM HISTORY
        # =====================================================
        #
        # Preserve our known-good Surmount fix.
        #
        # Default requirement = 200 bars.
        #
        # =====================================================

        minimum_history = max(

            TREND_SMA,
            LOOKBACK_6M,
            VOL_LONG

        )


        if ohlcv is None:

            log(
                "V2.3: No OHLCV data"
            )

            return TargetAllocation({})


        if len(ohlcv) < minimum_history:

            log(

                "V2.3: Not enough history. Bars: "
                + str(len(ohlcv))
                + " Required: "
                + str(minimum_history)

            )

            return TargetAllocation({})


        # =====================================================
        # DATE
        # =====================================================

        current_date = self.current_date(
            ohlcv
        )


        if current_date is None:

            log(
                "V2.3: Unable to read date"
            )

            return TargetAllocation({})


        current_key = self.rebalance_key(
            current_date
        )


        # =====================================================
        # HOLD CURRENT MONTHLY TARGET
        # =====================================================

        if (
            self.last_target
            and
            self.last_rebalance_key
            == current_key
        ):

            return TargetAllocation(
                self.last_target
            )


        log(

            "V2.3 MONTHLY REBALANCE: "
            + str(current_key)

        )


        # =====================================================
        # BROAD MARKET REGIME
        # =====================================================

        spy_price = self.close_price(
            "SPY",
            ohlcv
        )


        spy_long = SMA(
            "SPY",
            ohlcv,
            TREND_SMA
        )


        spy_fast = SMA(
            "SPY",
            ohlcv,
            FAST_SMA
        )


        if (
            spy_price is None
            or spy_long is None
            or spy_fast is None
            or len(spy_long) == 0
            or len(spy_fast) == 0
        ):

            log(
                "V2.3: SPY trend calculation failed"
            )

            return TargetAllocation({})


        risk_on = (

            spy_price
            > spy_long[-1]

            and

            spy_fast[-1]
            > spy_long[-1]

        )


        # =====================================================
        # FULL RISK OFF
        # =====================================================

        if not risk_on:

            allocation = (
                self.defensive_portfolio()
            )


            self.last_target = (
                allocation.copy()
            )


            self.last_rebalance_key = (
                current_key
            )


            log(
                "V2.3 REGIME: RISK OFF"
            )


            log(

                "V2.3 allocation: "
                + str(allocation)

            )


            return TargetAllocation(
                allocation
            )


        # =====================================================
        # CORE MOMENTUM SIGNALS
        # =====================================================

        returns_3m = {}

        returns_6m = {}

        rsi_values = {}


        for ticker in self.core_assets:

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


            try:

                rsi_series = RSI(

                    ticker,
                    ohlcv,
                    RSI_PERIOD

                )


                if (
                    rsi_series is not None
                    and len(rsi_series) > 0
                ):

                    rsi_values[ticker] = float(
                        rsi_series[-1]
                    )

                else:

                    rsi_values[ticker] = None


            except:

                rsi_values[ticker] = None


        # =====================================================
        # ABSOLUTE MOMENTUM + TREND FILTER
        # =====================================================

        eligible = []


        for ticker in self.core_assets:

            price = self.close_price(
                ticker,
                ohlcv
            )


            asset_trend = SMA(

                ticker,
                ohlcv,
                TREND_SMA

            )


            if (
                price is None
                or asset_trend is None
                or len(asset_trend) == 0
                or returns_6m[ticker] is None
            ):

                continue


            above_trend = (

                price
                > asset_trend[-1]

            )


            positive_momentum = (

                returns_6m[ticker]
                > 0

            )


            if (

                above_trend

                and

                (
                    positive_momentum
                    or not REQUIRE_POSITIVE_6M
                )

            ):

                eligible.append(
                    ticker
                )


        log(

            "V2.3 eligible ETFs: "
            + str(eligible)

        )


        # =====================================================
        # NOTHING QUALIFIES
        # =====================================================

        if len(eligible) == 0:

            allocation = (
                self.defensive_portfolio()
            )


            self.last_target = (
                allocation.copy()
            )


            self.last_rebalance_key = (
                current_key
            )


            return TargetAllocation(
                allocation
            )


        # =====================================================
        # CROSS-SECTIONAL NORMALIZATION
        # =====================================================

        z3 = self.zscores({

            ticker:
                returns_3m[ticker]

            for ticker
            in eligible

        })


        z6 = self.zscores({

            ticker:
                returns_6m[ticker]

            for ticker
            in eligible

        })


        zrsi = self.zscores({

            ticker:
                rsi_values[ticker]

            for ticker
            in eligible

        })


        # =====================================================
        # COMPOSITE MOMENTUM SCORE
        # =====================================================

        scores = {}


        for ticker in eligible:

            scores[ticker] = (

                WEIGHT_3M
                * z3[ticker]

                +

                WEIGHT_6M
                * z6[ticker]

                +

                WEIGHT_RSI
                * zrsi[ticker]

            )


        # =====================================================
        # RANK CORE ETFs
        # =====================================================

        ranked = sorted(

            eligible,

            key=lambda ticker:
                scores[ticker],

            reverse=True

        )


        selected = ranked[
            :MAX_HOLDINGS
        ]


        log(

            "V2.3 ranking: "
            + str(ranked)

        )


        log(

            "V2.3 selected: "
            + str(selected)

        )


        # =====================================================
        # CORE SIGNAL-STRENGTH ALLOCATION
        # =====================================================

        minimum_score = min(

            scores[ticker]

            for ticker
            in selected

        )


        strength = {}


        for ticker in selected:

            strength[ticker] = (

                scores[ticker]
                - minimum_score
                + SIGNAL_FLOOR

            )


        strength_total = sum(
            strength.values()
        )


        signal_weights = {

            ticker:

                strength[ticker]
                / strength_total

            for ticker
            in selected

        }


        equal_weight = (

            1.0
            / len(selected)

        )


        core_allocation = {}


        for ticker in selected:

            calculated_weight = (

                SIGNAL_WEIGHT_BLEND
                * signal_weights[ticker]

                +

                (
                    1.0
                    - SIGNAL_WEIGHT_BLEND
                )
                * equal_weight

            )


            core_allocation[ticker] = min(

                calculated_weight,

                MAX_SINGLE_ASSET_WEIGHT

            )


        # =====================================================
        # MARKET VOLATILITY
        # =====================================================

        short_vol = (
            self.realized_volatility(
                "SPY",
                ohlcv,
                VOL_SHORT
            )
        )


        long_vol = (
            self.realized_volatility(
                "SPY",
                ohlcv,
                VOL_LONG
            )
        )


        high_volatility = False


        if (
            short_vol is not None
            and long_vol is not None
            and long_vol > 0
        ):

            high_volatility = (

                short_vol
                >
                VOL_THRESHOLD
                * long_vol

            )


        # =====================================================
        # QQQ LEVERAGE SIGNALS
        # =====================================================

        qqq_price = self.close_price(
            "QQQ",
            ohlcv
        )


        qqq_fast = SMA(
            "QQQ",
            ohlcv,
            FAST_SMA
        )


        qqq_long = SMA(
            "QQQ",
            ohlcv,
            TREND_SMA
        )


        qqq_3m = self.trailing_return(
            "QQQ",
            ohlcv,
            LOOKBACK_3M
        )


        qqq_6m = self.trailing_return(
            "QQQ",
            ohlcv,
            LOOKBACK_6M
        )


        qqq_score = scores.get(
            "QQQ",
            None
        )


        qqq_rank = None


        if "QQQ" in ranked:

            qqq_rank = (
                ranked.index("QQQ")
                + 1
            )


        qqq_trend_good = (

            qqq_price is not None

            and qqq_fast is not None

            and qqq_long is not None

            and len(qqq_fast) > 0

            and len(qqq_long) > 0

            and qqq_price
                > qqq_long[-1]

            and qqq_fast[-1]
                > qqq_long[-1]

        )


        qqq_score_good = (

            qqq_score is not None

            and qqq_score > 0

        )


        # =====================================================
        # ADAPTIVE LEVERAGE
        # =====================================================

        leverage_sleeve = 0.0

        leverage_regime = "NONE"


        if (
            ENABLE_ADAPTIVE_LEVERAGE

            and not high_volatility

            and qqq_trend_good

            and qqq_score_good

            and qqq_3m is not None

            and qqq_6m is not None

            and qqq_rank is not None
        ):

            # -------------------------------------------------
            # EXCEPTIONAL MOMENTUM
            # -------------------------------------------------

            exceptional_momentum = (

                qqq_rank <= 2

                and qqq_3m
                    > EXCEPTIONAL_QQQ_3M

                and qqq_6m
                    > EXCEPTIONAL_QQQ_6M

            )


            # -------------------------------------------------
            # STRONG MOMENTUM
            # -------------------------------------------------

            strong_momentum = (

                qqq_rank <= MAX_HOLDINGS

                and qqq_3m
                    > STRONG_QQQ_3M

                and qqq_6m
                    > STRONG_QQQ_6M

            )


            if exceptional_momentum:

                leverage_sleeve = (
                    EXCEPTIONAL_LEVERAGE_SLEEVE
                )

                leverage_regime = (
                    "EXCEPTIONAL"
                )


            elif strong_momentum:

                leverage_sleeve = (
                    STRONG_LEVERAGE_SLEEVE
                )

                leverage_regime = (
                    "STRONG"
                )


        # =====================================================
        # FUND QLD FROM CORE PORTFOLIO
        # =====================================================

        if leverage_sleeve > 0:

            for ticker in list(
                core_allocation.keys()
            ):

                core_allocation[ticker] *= (

                    1.0
                    - leverage_sleeve

                )


            core_allocation[
                LEVERAGED_TICKER
            ] = leverage_sleeve


        # =====================================================
        # VOLATILITY SCALING
        # =====================================================

        risk_multiplier = 1.0


        if high_volatility:

            risk_multiplier = (
                HIGH_VOL_RISK_MULTIPLIER
            )


        allocation = {}


        for ticker, weight in (
            core_allocation.items()
        ):

            allocation[ticker] = (

                weight
                * risk_multiplier

            )


        # =====================================================
        # UNUSED CAPITAL -> SGOV
        # =====================================================

        total_allocated = sum(
            allocation.values()
        )


        unused = max(

            0.0,

            1.0 - total_allocated

        )


        if unused > 0:

            allocation["SGOV"] = (

                allocation.get(
                    "SGOV",
                    0.0
                )

                + unused

            )


        # =====================================================
        # SAFETY NORMALIZATION
        # =====================================================

        total = sum(
            allocation.values()
        )


        if total > 1.0:

            allocation = {

                ticker:
                    weight / total

                for ticker, weight
                in allocation.items()

            }


        # =====================================================
        # SAVE MONTHLY TARGET
        # =====================================================

        self.last_target = (
            allocation.copy()
        )


        self.last_rebalance_key = (
            current_key
        )


        # =====================================================
        # LOGGING
        # =====================================================

        log(
            "V2.3 REGIME: RISK ON"
        )


        log(

            "V2.3 selected ETFs: "
            + str(selected)

        )


        log(

            "V2.3 QQQ rank: "
            + str(qqq_rank)

        )


        log(

            "V2.3 QQQ score: "
            + str(qqq_score)

        )


        log(

            "V2.3 QQQ 3M: "
            + str(qqq_3m)

        )


        log(

            "V2.3 QQQ 6M: "
            + str(qqq_6m)

        )


        log(

            "V2.3 high volatility: "
            + str(high_volatility)

        )


        log(

            "V2.3 leverage regime: "
            + str(leverage_regime)

        )


        log(

            "V2.3 QLD allocation: "
            + str(leverage_sleeve)

        )


        log(

            "V2.3 FINAL ALLOCATION: "
            + str(allocation)

        )


        return TargetAllocation(
            allocation
        )