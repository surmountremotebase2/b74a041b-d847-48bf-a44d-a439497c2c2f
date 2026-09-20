from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# USER CONFIGURATION
# =============================================================
#
# Change ONLY these three parameters when testing variations.
#
# Suggested TREND_SMA values:
# 100, 125, 150, 175, 200
#
# Suggested LEVERAGED_SLEEVE values:
# 0.10, 0.15, 0.20, 0.25, 0.30
#
# Available MOMENTUM_MODE values:
# "1m+3m"
# "3m+6m"
# "3m+6m+12m"
#

TREND_SMA = 175

LEVERAGED_SLEEVE = 0.25

MOMENTUM_MODE = "3m+6m"


# =============================================================
# MOMENTUM PRESETS
# =============================================================
#
# Approximate trading days:
# 1 month  = 21
# 3 months = 63
# 6 months = 126
# 12 months = 252
#
# Each tuple is:
#
# (lookback_days, weight)
#

MOMENTUM_PRESETS = {

    "1m+3m": [
        (21, 0.50),
        (63, 0.50)
    ],

    "3m+6m": [
        (63, 0.50),
        (126, 0.50)
    ],

    "3m+6m+12m": [
        (63, 0.40),
        (126, 0.40),
        (252, 0.20)
    ]
}


# =============================================================
# STRATEGY
# =============================================================

class TradingStrategy(Strategy):

    def __init__(self):

        self.tickers = [
            "SPY",
            "QQQ",
            "SOXX",
            "SMH",
            "XLI",
            "QLD",
            "TQQQ",
            "SPXL",
            "GLD",
            "SGOV"
        ]

        self.non_leveraged = [
            "QQQ",
            "SOXX",
            "SMH",
            "XLI"
        ]

        self.leveraged = [
            "QLD",
            "TQQQ",
            "SPXL"
        ]

        self.momentum_universe = (
            self.non_leveraged
            + self.leveraged
        )

        # Strategy-level drawdown tracking
        self.strategy_nav = 1.0
        self.peak_nav = 1.0

        self.last_prices = None
        self.last_target = {}

        self.emergency_mode = False


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
                ohlcv[-1 - offset][ticker]["close"]
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

        try:

            previous = float(
                ohlcv[-1 - days][ticker]["close"]
            )

        except:

            return None

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
    # MOMENTUM ENGINE
    # =========================================================

    def momentum_score(
        self,
        ticker,
        ohlcv
    ):

        configuration = (
            MOMENTUM_PRESETS.get(
                MOMENTUM_MODE
            )
        )

        if configuration is None:

            log(
                "Invalid MOMENTUM_MODE: "
                + str(MOMENTUM_MODE)
            )

            return -999.0

        score = 0.0

        for lookback, weight in configuration:

            value = self.trailing_return(
                ticker,
                ohlcv,
                lookback
            )

            if value is None:
                return -999.0

            score += (
                value * weight
            )

        return score


    # =========================================================
    # REALIZED VOLATILITY
    # =========================================================

    def realized_volatility(
        self,
        ticker,
        ohlcv,
        days
    ):

        if len(ohlcv) < days + 1:
            return None

        prices = []

        for row in ohlcv[-(days + 1):]:

            try:

                price = float(
                    row[ticker]["close"]
                )

            except:

                return None

            if price <= 0:
                return None

            prices.append(price)

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
    # TWICE-WEEKLY REBALANCE
    # =========================================================

    def is_rebalance_day(
        self,
        ohlcv
    ):

        try:

            date_string = (
                ohlcv[-1]["QQQ"]["date"]
            )

            current_date = datetime.strptime(
                date_string.split(" ")[0],
                "%Y-%m-%d"
            )

            # Monday and Thursday
            return (
                current_date.weekday()
                in [0, 3]
            )

        except:

            # Do not prevent the strategy from running
            # if Surmount's date format differs.
            return True


    # =========================================================
    # ALLOCATION VALIDATION
    # =========================================================

    def clean_allocation(
        self,
        allocation
    ):

        cleaned = {}

        for ticker, weight in allocation.items():

            weight = max(
                0.0,
                float(weight)
            )

            if weight > 0:

                cleaned[ticker] = weight

        total = sum(
            cleaned.values()
        )

        if total > 1.0:

            cleaned = {

                ticker: weight / total

                for ticker, weight
                in cleaned.items()

            }

        return cleaned


    # =========================================================
    # STRATEGY DRAWDOWN TRACKING
    # =========================================================

    def update_strategy_nav(
        self,
        ohlcv
    ):

        current_prices = {}

        portfolio_assets = (

            self.non_leveraged
            + self.leveraged
            + ["GLD", "SGOV"]

        )

        for ticker in portfolio_assets:

            price = self.close_price(
                ticker,
                ohlcv
            )

            if price is not None:

                current_prices[ticker] = price


        if (
            self.last_prices is not None
            and len(self.last_target) > 0
        ):

            daily_return = 0.0

            for ticker, weight in (
                self.last_target.items()
            ):

                old_price = (
                    self.last_prices.get(
                        ticker
                    )
                )

                new_price = (
                    current_prices.get(
                        ticker
                    )
                )

                if (
                    old_price is not None
                    and new_price is not None
                    and old_price > 0
                ):

                    asset_return = (

                        new_price
                        / old_price

                    ) - 1.0


                    daily_return += (

                        weight
                        * asset_return

                    )


            self.strategy_nav *= (
                1.0 + daily_return
            )


            if (
                self.strategy_nav
                > self.peak_nav
            ):

                self.peak_nav = (
                    self.strategy_nav
                )


        self.last_prices = (
            current_prices
        )


        if self.peak_nav <= 0:
            return 0.0


        return (

            self.strategy_nav
            / self.peak_nav

        ) - 1.0


    # =========================================================
    # RETURN TARGET
    # =========================================================

    def target(
        self,
        allocation
    ):

        allocation = (
            self.clean_allocation(
                allocation
            )
        )

        self.last_target = (
            allocation.copy()
        )

        log(
            "Target allocation: "
            + str(allocation)
        )

        return TargetAllocation(
            allocation
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

        if ohlcv is None:

            return TargetAllocation({})


        # -----------------------------------------------------
        # DYNAMIC HISTORY REQUIREMENT
        # -----------------------------------------------------

        momentum_configuration = (
            MOMENTUM_PRESETS.get(
                MOMENTUM_MODE
            )
        )

        if momentum_configuration is None:

            return TargetAllocation({})


        longest_momentum_period = max(
            lookback
            for lookback, weight
            in momentum_configuration
        )


        required_history = max(
            TREND_SMA,
            longest_momentum_period,
            100
        ) + 10


        if len(ohlcv) < required_history:

            return TargetAllocation({})


        # -----------------------------------------------------
        # PRICES
        # -----------------------------------------------------

        spy_price = self.close_price(
            "SPY",
            ohlcv
        )

        qqq_price = self.close_price(
            "QQQ",
            ohlcv
        )


        if (
            spy_price is None
            or qqq_price is None
        ):

            return TargetAllocation({})


        # -----------------------------------------------------
        # MOVING AVERAGES
        # -----------------------------------------------------

        spy_trend_sma = SMA(
            "SPY",
            ohlcv,
            TREND_SMA
        )

        qqq_trend_sma = SMA(
            "QQQ",
            ohlcv,
            TREND_SMA
        )

        qqq_sma_50 = SMA(
            "QQQ",
            ohlcv,
            50
        )

        spy_sma_100 = SMA(
            "SPY",
            ohlcv,
            100
        )


        if (
            spy_trend_sma is None
            or qqq_trend_sma is None
            or qqq_sma_50 is None
            or spy_sma_100 is None
        ):

            return TargetAllocation({})


        spy_above_trend = (

            spy_price
            > spy_trend_sma[-1]

        )


        qqq_above_trend = (

            qqq_price
            > qqq_trend_sma[-1]

        )


        qqq_trend_confirmation = (

            qqq_sma_50[-1]
            > qqq_trend_sma[-1]

        )


        spy_above_100 = (

            spy_price
            > spy_sma_100[-1]

        )


        # -----------------------------------------------------
        # STRATEGY DRAWDOWN
        # -----------------------------------------------------

        drawdown = (
            self.update_strategy_nav(
                ohlcv
            )
        )


        log(
            "Trend SMA: "
            + str(TREND_SMA)
        )

        log(
            "Leverage sleeve: "
            + str(
                round(
                    LEVERAGED_SLEEVE * 100,
                    1
                )
            )
            + "%"
        )

        log(
            "Momentum mode: "
            + str(MOMENTUM_MODE)
        )

        log(
            "Strategy drawdown: "
            + str(
                round(
                    drawdown * 100,
                    2
                )
            )
            + "%"
        )


        # -----------------------------------------------------
        # 20% EMERGENCY DRAWDOWN
        # -----------------------------------------------------

        if drawdown <= -0.20:

            self.emergency_mode = True


        if self.emergency_mode:

            if spy_above_100:

                self.emergency_mode = False

            else:

                return self.target({

                    "SGOV": 0.70,
                    "GLD": 0.30

                })


        # -----------------------------------------------------
        # MOMENTUM RANKING
        # -----------------------------------------------------

        scores = {}


        for ticker in (
            self.momentum_universe
        ):

            scores[ticker] = (
                self.momentum_score(
                    ticker,
                    ohlcv
                )
            )


        ranked_nonleveraged = sorted(

            self.non_leveraged,

            key=lambda ticker:
                scores[ticker],

            reverse=True

        )


        ranked_leveraged = sorted(

            self.leveraged,

            key=lambda ticker:
                scores[ticker],

            reverse=True

        )


        best_nonleveraged = (
            ranked_nonleveraged[0]
        )

        second_nonleveraged = (
            ranked_nonleveraged[1]
        )

        best_leveraged = (
            ranked_leveraged[0]
        )


        log(
            "Momentum scores: "
            + str(scores)
        )


        # -----------------------------------------------------
        # VOLATILITY FILTER
        # -----------------------------------------------------

        qqq_vol_20 = (
            self.realized_volatility(
                "QQQ",
                ohlcv,
                20
            )
        )


        qqq_vol_100 = (
            self.realized_volatility(
                "QQQ",
                ohlcv,
                100
            )
        )


        high_volatility = False


        if (
            qqq_vol_20 is not None
            and qqq_vol_100 is not None
            and qqq_vol_100 > 0
        ):

            high_volatility = (

                qqq_vol_20
                > 1.75
                * qqq_vol_100

            )


        # -----------------------------------------------------
        # 15% DRAWDOWN
        # -----------------------------------------------------

        if drawdown <= -0.15:

            return self.target({

                best_nonleveraged: 0.25,

                "SGOV": 0.50,

                "GLD": 0.25

            })


        # -----------------------------------------------------
        # REBALANCE TWICE PER WEEK
        # -----------------------------------------------------

        if not self.is_rebalance_day(
            ohlcv
        ):

            if len(self.last_target) > 0:

                return TargetAllocation(
                    self.last_target
                )


        # -----------------------------------------------------
        # MARKET REGIMES
        # -----------------------------------------------------

        risk_on = (

            spy_above_trend
            and qqq_above_trend
            and qqq_trend_confirmation

        )


        mixed_regime = (

            spy_above_trend
            and not qqq_above_trend

        )


        # -----------------------------------------------------
        # FULL RISK-ON
        # -----------------------------------------------------

        if risk_on:

            leverage_allowed = (

                not high_volatility
                and drawdown > -0.10
                and LEVERAGED_SLEEVE > 0

            )


            if leverage_allowed:

                # Keep first non-leveraged ETF at 50%.
                first_weight = 0.50

                # Leveraged allocation is user-adjustable.
                leveraged_weight = min(
                    LEVERAGED_SLEEVE,
                    0.35
                )

                # Remaining allocation goes to
                # second non-leveraged ETF.
                second_weight = (

                    1.0
                    - first_weight
                    - leveraged_weight

                )


                allocation = {

                    best_nonleveraged:
                        first_weight,

                    second_nonleveraged:
                        second_weight,

                    best_leveraged:
                        leveraged_weight

                }


            else:

                allocation = {

                    best_nonleveraged:
                        0.60,

                    second_nonleveraged:
                        0.40

                }


            return self.target(
                allocation
            )


        # -----------------------------------------------------
        # MIXED REGIME
        # -----------------------------------------------------

        elif mixed_regime:

            return self.target({

                best_nonleveraged:
                    0.50,

                "GLD":
                    0.25,

                "SGOV":
                    0.25

            })


        # -----------------------------------------------------
        # FULL RISK-OFF
        # -----------------------------------------------------

        elif (
            not spy_above_trend
            and not qqq_above_trend
        ):

            return self.target({

                "SGOV":
                    0.70,

                "GLD":
                    0.30

            })


        # -----------------------------------------------------
        # OTHER MIXED CONDITION
        # -----------------------------------------------------

        else:

            return self.target({

                best_nonleveraged:
                    0.50,

                "GLD":
                    0.25,

                "SGOV":
                    0.25

            })