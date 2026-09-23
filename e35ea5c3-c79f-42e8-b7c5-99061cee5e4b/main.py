from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


# =============================================================
# USER SETTINGS
# =============================================================

# Main trend filter
TREND_SMA = 200

# Faster QQQ trend confirmation
FAST_SMA = 50

# Momentum periods
LOOKBACK_3M = 63
LOOKBACK_6M = 126

# Momentum score weights
WEIGHT_3M = 0.40
WEIGHT_6M = 0.40
WEIGHT_RSI = 0.20

# RSI
RSI_PERIOD = 14

# Number of risk assets to hold
MAX_RISK_ASSETS = 4

# Combined maximum allocation to QLD, TQQQ and SPXL
MAX_LEVERAGED_EXPOSURE = 0.25

# Rebalance frequency:
# "weekly", "biweekly", "monthly"
REBALANCE_FREQUENCY = "monthly"

# Volatility control
VOL_SHORT = 20
VOL_LONG = 100

# If short volatility > this multiple of long volatility,
# reduce risk exposure.
VOL_THRESHOLD = 1.50

# Keep this percentage of normal risk exposure during
# a volatility spike.
HIGH_VOL_RISK_MULTIPLIER = 0.50

# Defensive allocation
SGOV_WEIGHT = 0.70
GLD_WEIGHT = 0.30


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

        self.non_leveraged_assets = [
            "QQQ",
            "SOXX",
            "SMH",
            "XLI"
        ]

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

    def close_price(self, ticker, ohlcv, offset=0):

        try:
            return float(
                ohlcv[-1 - offset][ticker]["close"]
            )

        except:
            return None


    def trailing_return(self, ticker, ohlcv, days):

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

        return (current / past) - 1.0


    # =========================================================
    # VOLATILITY
    # =========================================================

    def realized_volatility(self, ticker, ohlcv, days):

        if len(ohlcv) <= days:
            return None

        prices = []

        for offset in range(days, -1, -1):

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

            prices.append(price)

        returns = []

        for i in range(1, len(prices)):

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
    # DATE / REBALANCE
    # =========================================================

    def current_date(self, ohlcv):

        try:

            date_value = str(
                ohlcv[-1]["SPY"]["date"]
            )

            return datetime.strptime(
                date_value[:10],
                "%Y-%m-%d"
            )

        except:

            return None


    def rebalance_key(self, date):

        if REBALANCE_FREQUENCY == "weekly":

            iso = date.isocalendar()

            return (
                iso[0],
                iso[1]
            )

        elif REBALANCE_FREQUENCY == "biweekly":

            iso = date.isocalendar()

            return (
                iso[0],
                iso[1] // 2
            )

        else:

            return (
                date.year,
                date.month
            )


    def should_rebalance(self, date):

        key = self.rebalance_key(date)

        if self.last_rebalance_key is None:

            self.last_rebalance_key = key
            return True

        if key != self.last_rebalance_key:

            self.last_rebalance_key = key
            return True

        return False


    # =========================================================
    # Z-SCORE
    # =========================================================

    def zscores(self, values):

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
            "SGOV": SGOV_WEIGHT,
            "GLD": GLD_WEIGHT
        }


    # =========================================================
    # NORMALIZE ALLOCATION
    # =========================================================

    def normalize(self, allocation):

        clean = {}

        for ticker, weight in allocation.items():

            if weight > 0:

                clean[ticker] = float(
                    weight
                )

        total = sum(
            clean.values()
        )

        if total > 1.0:

            clean = {
                ticker: weight / total
                for ticker, weight
                in clean.items()
            }

        return clean


    # =========================================================
    # MAIN STRATEGY
    # =========================================================

    def run(self, data):

        ohlcv = data.get("ohlcv")


        # -----------------------------------------------------
        # IMPORTANT FIX
        #
        # We only require enough history for the 200-day trend
        # filter. We no longer require 252+ days.
        # -----------------------------------------------------

        minimum_history = max(
            TREND_SMA,
            LOOKBACK_6M,
            VOL_LONG
        )

        if ohlcv is None:

            log("No OHLCV data")
            return TargetAllocation({})

        if len(ohlcv) < minimum_history:

            log(
                "Not enough OHLCV history. Bars available: "
                + str(len(ohlcv))
                + " Required: "
                + str(minimum_history)
            )

            return TargetAllocation({})


        current_date = self.current_date(
            ohlcv
        )

        if current_date is None:

            log("Unable to read current date")
            return TargetAllocation({})


        # -----------------------------------------------------
        # HOLD PORTFOLIO BETWEEN REBALANCES
        # -----------------------------------------------------

        if self.last_target:

            if not self.should_rebalance(
                current_date
            ):

                return TargetAllocation(
                    self.last_target
                )


        # -----------------------------------------------------
        # MARKET TREND
        # -----------------------------------------------------

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

        qqq_fast_sma = SMA(
            "QQQ",
            ohlcv,
            FAST_SMA
        )


        if (
            spy_price is None
            or qqq_price is None
            or spy_sma is None
            or qqq_sma is None
            or qqq_fast_sma is None
        ):

            log("Trend calculation failed")
            return TargetAllocation({})


        risk_on = (
            spy_price > spy_sma[-1]
            and
            qqq_price > qqq_sma[-1]
            and
            qqq_fast_sma[-1] > qqq_sma[-1]
        )


        # -----------------------------------------------------
        # RISK-OFF
        # -----------------------------------------------------

        if not risk_on:

            allocation = (
                self.defensive_portfolio()
            )

            self.last_target = (
                allocation.copy()
            )

            log("RISK OFF")
            log(str(allocation))

            return TargetAllocation(
                allocation
            )


        # -----------------------------------------------------
        # MOMENTUM SIGNALS
        # -----------------------------------------------------

        returns_3m = {}
        returns_6m = {}
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


        # -----------------------------------------------------
        # ABSOLUTE MOMENTUM + TREND FILTER
        # -----------------------------------------------------

        eligible = []


        for ticker in self.risk_assets:

            price = self.close_price(
                ticker,
                ohlcv
            )

            asset_sma = SMA(
                ticker,
                ohlcv,
                TREND_SMA
            )

            if (
                price is None
                or asset_sma is None
                or returns_6m[ticker] is None
            ):
                continue


            if (
                price > asset_sma[-1]
                and
                returns_6m[ticker] > 0
            ):

                eligible.append(
                    ticker
                )


        log(
            "Eligible assets: "
            + str(eligible)
        )


        if len(eligible) == 0:

            allocation = (
                self.defensive_portfolio()
            )

            self.last_target = (
                allocation.copy()
            )

            return TargetAllocation(
                allocation
            )


        # -----------------------------------------------------
        # STANDARDIZE MOMENTUM COMPONENTS
        # -----------------------------------------------------

        z3 = self.zscores({

            ticker:
                returns_3m[ticker]

            for ticker in eligible

        })


        z6 = self.zscores({

            ticker:
                returns_6m[ticker]

            for ticker in eligible

        })


        zrsi = self.zscores({

            ticker:
                rsi_values[ticker]

            for ticker in eligible

        })


        # -----------------------------------------------------
        # COMPOSITE MOMENTUM
        # -----------------------------------------------------

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


        ranked = sorted(
            eligible,
            key=lambda ticker:
                scores[ticker],
            reverse=True
        )


        selected = ranked[
            :MAX_RISK_ASSETS
        ]


        log(
            "Momentum ranking: "
            + str(ranked)
        )


        # -----------------------------------------------------
        # PROPORTIONAL SIGNAL WEIGHTS
        # -----------------------------------------------------

        minimum = min(
            scores[ticker]
            for ticker in selected
        )


        strength = {}


        for ticker in selected:

            # Makes every selected score positive.
            strength[ticker] = (

                scores[ticker]
                - minimum
                + 0.25

            )


        total_strength = sum(
            strength.values()
        )


        allocation = {

            ticker:
                strength[ticker]
                / total_strength

            for ticker in selected

        }


        # -----------------------------------------------------
        # CAP LEVERAGED ETFs
        # -----------------------------------------------------

        leveraged_weight = sum(

            allocation.get(
                ticker,
                0.0
            )

            for ticker in self.leveraged_assets

        )


        if (
            leveraged_weight
            > MAX_LEVERAGED_EXPOSURE
        ):

            scale = (

                MAX_LEVERAGED_EXPOSURE
                / leveraged_weight

            )

            removed = 0.0


            for ticker in self.leveraged_assets:

                if ticker in allocation:

                    old = allocation[ticker]

                    new = old * scale

                    allocation[ticker] = new

                    removed += (
                        old - new
                    )


            nonleveraged = [

                ticker

                for ticker in selected

                if ticker
                not in self.leveraged_assets

            ]


            if nonleveraged:

                base = sum(
                    allocation[ticker]
                    for ticker in nonleveraged
                )


                if base > 0:

                    for ticker in nonleveraged:

                        allocation[ticker] += (

                            removed
                            * allocation[ticker]
                            / base

                        )

                else:

                    allocation["SGOV"] = (
                        allocation.get(
                            "SGOV",
                            0.0
                        )
                        + removed
                    )

            else:

                allocation["SGOV"] = (
                    allocation.get(
                        "SGOV",
                        0.0
                    )
                    + removed
                )


        # -----------------------------------------------------
        # VOLATILITY SCALING
        # -----------------------------------------------------

        short_vol = (
            self.realized_volatility(
                "QQQ",
                ohlcv,
                VOL_SHORT
            )
        )

        long_vol = (
            self.realized_volatility(
                "QQQ",
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
                > VOL_THRESHOLD * long_vol
            ):

                risk_multiplier = (
                    HIGH_VOL_RISK_MULTIPLIER
                )


        # -----------------------------------------------------
        # APPLY VOLATILITY SCALING
        # -----------------------------------------------------

        for ticker in list(
            allocation.keys()
        ):

            allocation[ticker] *= (
                risk_multiplier
            )


        unused = (
            1.0
            - sum(allocation.values())
        )


        if unused > 0:

            allocation["SGOV"] = (

                allocation.get(
                    "SGOV",
                    0.0
                )

                + unused

            )


        allocation = self.normalize(
            allocation
        )


        self.last_target = (
            allocation.copy()
        )


        log(
            "Risk multiplier: "
            + str(risk_multiplier)
        )

        log(
            "Final allocation: "
            + str(allocation)
        )


        return TargetAllocation(
            allocation
        )