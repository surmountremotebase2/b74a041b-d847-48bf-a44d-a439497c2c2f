#Type code here
from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# MOMENTUM V2
# DIVERSIFIED ETF ROTATION
# =============================================================
#
# DESIGN:
#
# 1. Broad market regime filter
# 2. Diversified ETF universe
# 3. Individual ETF trend filter
# 4. Positive absolute momentum filter
# 5. Cross-sectional momentum ranking
# 6. Proportional signal-strength allocation
# 7. Single-ETF concentration cap
# 8. Market-volatility scaling
# 9. SGOV / GLD defensive allocation
# 10. Optional SEPARATE leveraged sleeve
#
# =============================================================


# =============================================================
# USER SETTINGS
# =============================================================


# -------------------------------------------------------------
# REBALANCE FREQUENCY
# -------------------------------------------------------------
#
# "weekly"
# "biweekly"
# "monthly"
#

REBALANCE_FREQUENCY = "monthly"


# -------------------------------------------------------------
# NUMBER OF ETFs TO HOLD
# -------------------------------------------------------------

MAX_HOLDINGS = 7


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
# MOMENTUM SCORE
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
# SIGNAL-STRENGTH WEIGHTING
# -------------------------------------------------------------
#
# 1.00 = pure signal-strength weighting
# 0.00 = equal weighting
#
# 0.65 gives momentum an important role while reducing
# extreme position concentration.
#

SIGNAL_WEIGHT_BLEND = 0.65


# Helps prevent the weakest selected ETF from receiving
# essentially zero allocation.

SIGNAL_FLOOR = 0.25


# -------------------------------------------------------------
# POSITION CONCENTRATION LIMIT
# -------------------------------------------------------------

MAX_SINGLE_ASSET_WEIGHT = 0.35


# -------------------------------------------------------------
# VOLATILITY CONTROL
# -------------------------------------------------------------
#
# Uses SPY as broad-market volatility proxy.
#

VOL_SHORT = 20
VOL_LONG = 100

VOL_THRESHOLD = 1.50

HIGH_VOL_RISK_MULTIPLIER = 0.50


# -------------------------------------------------------------
# DEFENSIVE PORTFOLIO
# -------------------------------------------------------------

DEFENSIVE_SGOV_WEIGHT = 0.70
DEFENSIVE_GLD_WEIGHT = 0.30


# -------------------------------------------------------------
# OPTIONAL LEVERAGED SLEEVE
# -------------------------------------------------------------
#
# IMPORTANT:
#
# V2 does NOT allow leveraged ETFs to compete directly with
# QQQ, sectors, international ETFs, etc.
#
# That was a weakness of V1 because TQQQ naturally has much
# larger raw returns than QQQ during bull markets.
#
# Instead leverage is a separate overlay.
#
# Start with False.
#

ENABLE_LEVERAGE = False

LEVERAGED_TICKER = "QLD"

MAX_LEVERAGE_SLEEVE = 0.10


# =============================================================
# STRATEGY
# =============================================================

class TradingStrategy(Strategy):

    def __init__(self):

        # =====================================================
        # DIVERSIFIED CORE MOMENTUM UNIVERSE
        # =====================================================
        #
        # Each ETF represents a meaningfully different
        # economic exposure.
        #
        # Growth:
        # QQQ
        #
        # Small caps:
        # IWM
        #
        # Large-cap value:
        # VTV
        #
        # Semiconductors:
        # SMH
        #
        # Industrials:
        # XLI
        #
        # Financials:
        # XLF
        #
        # Healthcare:
        # XLV
        #
        # Energy:
        # XLE
        #
        # Consumer staples:
        # XLP
        #
        # Developed international:
        # EFA
        #
        # Emerging markets:
        # EEM
        #
        # Real estate:
        # VNQ
        #
        # Gold:
        # GLD
        #
        # Long-duration Treasuries:
        # TLT
        #
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


        # Assets used only for optional leverage overlay.

        self.leveraged_assets = [

            "QLD",
            "TQQQ",
            "SPXL"

        ]


        # Broad-market regime indicator.

        self.market_indicator = "SPY"


        # All tickers Surmount needs price data for.

        self.tickers = list(

            dict.fromkeys(

                ["SPY", "SGOV"]

                + self.core_assets

                + self.leveraged_assets

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

                for value
                in returns

            )

            / (len(returns) - 1)

        )


        return (

            sqrt(variance)
            * sqrt(252)

        )


    # =========================================================
    # DATE HANDLING
    # =========================================================

    def current_date(
        self,
        ohlcv
    ):

        try:

            value = str(

                ohlcv[-1][
                    "SPY"
                ]["date"]

            )


            return datetime.strptime(

                value[:10],
                "%Y-%m-%d"

            )


        except:

            return None


    # =========================================================
    # REBALANCE KEY
    # =========================================================

    def rebalance_key(
        self,
        date
    ):

        if REBALANCE_FREQUENCY == "weekly":

            iso = date.isocalendar()

            return (

                iso[0],
                iso[1]

            )


        if REBALANCE_FREQUENCY == "biweekly":

            iso = date.isocalendar()

            return (

                iso[0],
                iso[1] // 2

            )


        return (

            date.year,
            date.month

        )


    # =========================================================
    # CROSS-SECTIONAL Z-SCORES
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
    # FULL DEFENSIVE PORTFOLIO
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
        # IMPORTANT:
        #
        # Preserve our known-good Surmount fix.
        #
        # No unnecessary 252/262-bar requirement.
        #
        # Defaults:
        #
        # trend = 200
        # momentum = 126
        # volatility = 100
        #
        # minimum = 200
        #
        # =====================================================

        minimum_history = max(

            TREND_SMA,
            LOOKBACK_6M,
            VOL_LONG

        )


        if ohlcv is None:

            log(
                "No OHLCV data"
            )

            return TargetAllocation({})


        if len(ohlcv) < minimum_history:

            log(

                "Not enough history. Bars: "
                + str(len(ohlcv))
                + " Required: "
                + str(minimum_history)

            )

            return TargetAllocation({})


        # =====================================================
        # CURRENT DATE
        # =====================================================

        current_date = self.current_date(
            ohlcv
        )


        if current_date is None:

            log(
                "Unable to read current date"
            )

            return TargetAllocation({})


        # =====================================================
        # REBALANCE
        # =====================================================

        current_key = self.rebalance_key(
            current_date
        )


        if (
            self.last_target
            and
            self.last_rebalance_key
            == current_key
        ):

            return TargetAllocation(
                self.last_target
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
        ):

            log(
                "SPY trend calculation failed"
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
        # FULL RISK-OFF
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
                "V2 REGIME: RISK OFF"
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
        # ABSOLUTE MOMENTUM + OWN TREND FILTER
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

            "Eligible V2 ETFs: "
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


            log(
                "No eligible momentum ETFs"
            )


            return TargetAllocation(
                allocation
            )


        # =====================================================
        # NORMALIZE MOMENTUM COMPONENTS
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
        # RANK
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

            "V2 ranking: "
            + str(ranked)

        )


        log(

            "V2 selected: "
            + str(selected)

        )


        # =====================================================
        # SIGNAL-STRENGTH WEIGHTS
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


        # =====================================================
        # BLEND SIGNAL WEIGHTING WITH EQUAL WEIGHTING
        # =====================================================
        #
        # This reduces the chance that one very strong signal
        # consumes the entire portfolio.
        #
        # =====================================================

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


            # Concentration cap

            core_allocation[ticker] = min(

                calculated_weight,

                MAX_SINGLE_ASSET_WEIGHT

            )


        # =====================================================
        # OPTIONAL LEVERAGE OVERLAY
        # =====================================================
        #
        # Leveraged ETFs DO NOT enter the normal ranking.
        #
        # The overlay only activates when Nasdaq conditions
        # are particularly strong.
        #
        # =====================================================

        leverage_sleeve = 0.0


        if ENABLE_LEVERAGE:

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


            strong_nasdaq = (

                qqq_price is not None

                and qqq_fast is not None

                and qqq_long is not None

                and qqq_3m is not None

                and qqq_6m is not None

                and qqq_price
                    > qqq_long[-1]

                and qqq_fast[-1]
                    > qqq_long[-1]

                and qqq_3m > 0

                and qqq_6m > 0

            )


            if strong_nasdaq:

                leverage_sleeve = min(

                    MAX_LEVERAGE_SLEEVE,

                    0.20

                )


        # Scale core sleeve to make room.

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
        # MARKET VOLATILITY FILTER
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


        risk_multiplier = 1.0


        if (
            short_vol is not None
            and long_vol is not None
            and long_vol > 0
        ):

            if (

                short_vol
                >
                VOL_THRESHOLD
                * long_vol

            ):

                risk_multiplier = (
                    HIGH_VOL_RISK_MULTIPLIER
                )


        # =====================================================
        # APPLY VOLATILITY SCALING
        # =====================================================

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

        portfolio_total = sum(
            allocation.values()
        )


        unused = max(

            0.0,

            1.0 - portfolio_total

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
        # SAVE TARGET
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
            "V2 REGIME: RISK ON"
        )


        log(

            "Momentum scores: "
            + str(scores)

        )


        log(

            "Selected ETFs: "
            + str(selected)

        )


        log(

            "Leverage sleeve: "
            + str(leverage_sleeve)

        )


        log(

            "SPY volatility multiplier: "
            + str(risk_multiplier)

        )


        log(

            "Final V2 allocation: "
            + str(allocation)

        )


        return TargetAllocation(
            allocation
        )