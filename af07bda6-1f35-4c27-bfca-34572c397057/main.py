from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log

from datetime import datetime
from math import log as ln, sqrt


class TradingStrategy(Strategy):

    def __init__(self):

        # SPY is used as a market-regime indicator.
        # All other tickers can receive allocations.
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
            self.non_leveraged +
            self.leveraged
        )

        # Used for portfolio drawdown estimation.
        self.strategy_nav = 1.0
        self.peak_nav = 1.0
        self.last_prices = None
        self.last_target = {}

        # Once a 20% strategy drawdown occurs,
        # remain defensive until SPY recovers above its 100-day SMA.
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

        try:
            previous = float(
                ohlcv[-1 - days][ticker]["close"]
            )
        except:
            return None

        if (
            current is None or
            previous is None or
            previous <= 0
        ):
            return None

        return (
            current / previous
        ) - 1.0

    # =========================================================
    # MOMENTUM
    # =========================================================

    def momentum_score(self, ticker, ohlcv):

        # Approximate trading-day equivalents.
        three_month = self.trailing_return(
            ticker,
            ohlcv,
            63
        )

        six_month = self.trailing_return(
            ticker,
            ohlcv,
            126
        )

        if (
            three_month is None or
            six_month is None
        ):
            return -999.0

        return (
            0.50 * three_month +
            0.50 * six_month
        )

    # =========================================================
    # REALIZED VOLATILITY
    # =========================================================

    def realized_volatility(self, ticker, ohlcv, days):

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

        for i in range(1, len(prices)):
            returns.append(
                ln(
                    prices[i] /
                    prices[i - 1]
                )
            )

        if len(returns) < 2:
            return None

        average = (
            sum(returns) /
            len(returns)
        )

        variance = sum(
            (r - average) ** 2
            for r in returns
        ) / (len(returns) - 1)

        return (
            sqrt(variance) *
            sqrt(252)
        )

    # =========================================================
    # REBALANCE SCHEDULE
    # =========================================================

    def is_rebalance_day(self, ohlcv):

        try:
            date_string = (
                ohlcv[-1]["QQQ"]["date"]
            )

            current_date = datetime.strptime(
                date_string.split(" ")[0],
                "%Y-%m-%d"
            )

            # Monday = 0
            # Thursday = 3
            return (
                current_date.weekday()
                in [0, 3]
            )

        except:
            # If Surmount changes date formatting,
            # execute rather than fail.
            return True

    # =========================================================
    # ALLOCATION VALIDATION
    # =========================================================

    def clean_allocation(self, allocation):

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

        # Surmount requires total <= 1.0.
        if total > 1.0:

            cleaned = {
                ticker: weight / total
                for ticker, weight
                in cleaned.items()
            }

        return cleaned

    # =========================================================
    # APPROXIMATE STRATEGY DRAWDOWN
    # =========================================================

    def update_strategy_nav(self, ohlcv):

        current_prices = {}

        for ticker in (
            self.non_leveraged +
            self.leveraged +
            ["GLD", "SGOV"]
        ):

            price = self.close_price(
                ticker,
                ohlcv
            )

            if price is not None:
                current_prices[ticker] = price

        if (
            self.last_prices is not None and
            len(self.last_target) > 0
        ):

            daily_return = 0.0

            for ticker, weight in self.last_target.items():

                old_price = (
                    self.last_prices.get(ticker)
                )

                new_price = (
                    current_prices.get(ticker)
                )

                if (
                    old_price is not None and
                    new_price is not None and
                    old_price > 0
                ):

                    asset_return = (
                        new_price /
                        old_price
                    ) - 1.0

                    daily_return += (
                        weight *
                        asset_return
                    )

            self.strategy_nav *= (
                1.0 + daily_return
            )

            if (
                self.strategy_nav >
                self.peak_nav
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
            self.strategy_nav /
            self.peak_nav
        ) - 1.0

    # =========================================================
    # SAVE + RETURN TARGET
    # =========================================================

    def target(self, allocation):

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

    def run(self, data):

        ohlcv = data.get("ohlcv")

        if ohlcv is None:
            return TargetAllocation({})

        # Need 150-day SMA plus
        # 126-day momentum history.
        if len(ohlcv) < 160:
            return TargetAllocation({})

        # -----------------------------------------------------
        # CURRENT PRICES
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
            spy_price is None or
            qqq_price is None
        ):
            return TargetAllocation({})

        # -----------------------------------------------------
        # TREND FILTERS
        # -----------------------------------------------------

        spy_sma_150 = SMA(
            "SPY",
            ohlcv,
            150
        )

        spy_sma_100 = SMA(
            "SPY",
            ohlcv,
            100
        )

        qqq_sma_150 = SMA(
            "QQQ",
            ohlcv,
            150
        )

        qqq_sma_50 = SMA(
            "QQQ",
            ohlcv,
            50
        )

        if (
            spy_sma_150 is None or
            spy_sma_100 is None or
            qqq_sma_150 is None or
            qqq_sma_50 is None
        ):
            return TargetAllocation({})

        spy_above_150 = (
            spy_price >
            spy_sma_150[-1]
        )

        spy_above_100 = (
            spy_price >
            spy_sma_100[-1]
        )

        qqq_above_150 = (
            qqq_price >
            qqq_sma_150[-1]
        )

        qqq_50_above_150 = (
            qqq_sma_50[-1] >
            qqq_sma_150[-1]
        )

        # -----------------------------------------------------
        # PORTFOLIO DRAWDOWN
        # -----------------------------------------------------

        drawdown = (
            self.update_strategy_nav(
                ohlcv
            )
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

                # "Completely to SGOV and GLD"
                return self.target({
                    "SGOV": 0.70,
                    "GLD": 0.30
                })

        # -----------------------------------------------------
        # MOMENTUM SCORES
        # -----------------------------------------------------

        scores = {}

        for ticker in self.momentum_universe:

            scores[ticker] = (
                self.momentum_score(
                    ticker,
                    ohlcv
                )
            )

        ranked_nonleveraged = sorted(
            self.non_leveraged,
            key=lambda x: scores[x],
            reverse=True
        )

        ranked_leveraged = sorted(
            self.leveraged,
            key=lambda x: scores[x],
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
            qqq_vol_20 is not None and
            qqq_vol_100 is not None and
            qqq_vol_100 > 0
        ):

            high_volatility = (
                qqq_vol_20 >
                1.75 *
                qqq_vol_100
            )

        # -----------------------------------------------------
        # 15% DRAWDOWN
        # -----------------------------------------------------

        if drawdown <= -0.15:

            # Total equity = 25%.
            return self.target({
                best_nonleveraged: 0.25,
                "SGOV": 0.50,
                "GLD": 0.25
            })

        # -----------------------------------------------------
        # ONLY REBALANCE TWICE PER WEEK
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
            spy_above_150 and
            qqq_above_150 and
            qqq_50_above_150
        )

        mixed_regime = (
            spy_above_150 and
            not qqq_above_150
        )

        # -----------------------------------------------------
        # FULL RISK-ON
        # -----------------------------------------------------

        if risk_on:

            # Remove leverage when volatility is high
            # or strategy drawdown reaches 10%.
            leverage_allowed = (
                not high_volatility
                and drawdown > -0.10
            )

            if leverage_allowed:

                allocation = {
                    best_nonleveraged: 0.50,
                    second_nonleveraged: 0.25,
                    best_leveraged: 0.25
                }

            else:

                # Replace leveraged sleeve with SGOV.
                allocation = {
                    best_nonleveraged: 0.50,
                    second_nonleveraged: 0.25,
                    "SGOV": 0.25
                }

            return self.target(
                allocation
            )

        # -----------------------------------------------------
        # MIXED REGIME
        # -----------------------------------------------------

        elif mixed_regime:

            return self.target({
                best_nonleveraged: 0.50,
                "GLD": 0.25,
                "SGOV": 0.25
            })

        # -----------------------------------------------------
        # BOTH BELOW 150-DAY SMA
        # -----------------------------------------------------

        elif (
            not spy_above_150 and
            not qqq_above_150
        ):

            return self.target({
                "SGOV": 0.70,
                "GLD": 0.30
            })

        # -----------------------------------------------------
        # OTHER / AMBIGUOUS REGIME
        #
        # Example:
        # SPY below 150-day SMA,
        # QQQ above 150-day SMA.
        #
        # The original prompt does not explicitly define this.
        # Use a conservative mixed allocation.
        # -----------------------------------------------------

        else:

            return self.target({
                best_nonleveraged: 0.50,
                "GLD": 0.25,
                "SGOV": 0.25
            })