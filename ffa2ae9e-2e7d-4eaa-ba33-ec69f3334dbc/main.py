from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log

from datetime import datetime
from math import log as math_log, sqrt


class TradingStrategy(Strategy):

    def __init__(self):
        # SPY is included because it is used as a market-regime signal.
        # It is not allocated capital by this strategy.
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

        self.non_leveraged = ["QQQ", "SOXX", "SMH", "XLI"]
        self.leveraged = ["QLD", "TQQQ", "SPXL"]

        # Persistent strategy state used to estimate strategy-level drawdown.
        self.nav = 1.0
        self.peak_nav = 1.0
        self.previous_prices = {}
        self.current_allocation = {}
        self.hard_risk_off = False

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return []

    # ---------------------------------------------------------
    # HELPER FUNCTIONS
    # ---------------------------------------------------------

    def close_price(self, ticker, ohlcv, offset=0):
        """
        Return closing price.
        offset=0 means latest close.
        offset=1 means previous close.
        """
        index = -1 - offset

        try:
            return float(ohlcv[index][ticker]["close"])
        except:
            return None

    def trailing_return(self, ticker, ohlcv, lookback):
        """
        Calculate simple trailing price return.
        63 trading days ~= 3 months.
        126 trading days ~= 6 months.
        """
        if len(ohlcv) <= lookback:
            return None

        current = self.close_price(ticker, ohlcv)

        try:
            old_price = float(
                ohlcv[-1 - lookback][ticker]["close"]
            )
        except:
            return None

        if current is None or old_price <= 0:
            return None

        return current / old_price - 1.0

    def momentum_score(self, ticker, ohlcv):
        """
        Composite momentum:
        50% three-month return
        50% six-month return
        """
        r3 = self.trailing_return(ticker, ohlcv, 63)
        r6 = self.trailing_return(ticker, ohlcv, 126)

        if r3 is None or r6 is None:
            return -999.0

        return (0.50 * r3) + (0.50 * r6)

    def realized_volatility(self, ticker, ohlcv, length):
        """
        Annualized realized volatility calculated
        from daily logarithmic returns.
        """
        if len(ohlcv) < length + 1:
            return None

        prices = []

        for row in ohlcv[-(length + 1):]:
            try:
                price = float(row[ticker]["close"])
            except:
                return None

            if price <= 0:
                return None

            prices.append(price)

        returns = []

        for i in range(1, len(prices)):
            returns.append(
                math_log(prices[i] / prices[i - 1])
            )

        if len(returns) < 2:
            return None

        mean_return = sum(returns) / len(returns)

        variance = sum(
            (r - mean_return) ** 2
            for r in returns
        ) / (len(returns) - 1)

        daily_std = sqrt(variance)

        return daily_std * sqrt(252)

    def normalize(self, allocation):
        """
        Remove zero allocations and guarantee that
        TargetAllocation never exceeds 100%.
        """
        clean = {}

        for ticker, weight in allocation.items():
            if weight > 0:
                clean[ticker] = max(0.0, float(weight))

        total = sum(clean.values())

        if total > 1.0:
            clean = {
                ticker: weight / total
                for ticker, weight in clean.items()
            }

        return clean

    def update_strategy_nav(self, ohlcv):
        """
        Estimate portfolio NAV from the previous target
        allocation and today's asset returns.

        This allows drawdown rules to refer to the strategy's
        estimated portfolio drawdown rather than an index drawdown.
        """

        latest_prices = {}

        for ticker in self.tickers:
            price = self.close_price(ticker, ohlcv)

            if price is not None:
                latest_prices[ticker] = price

        if (
            len(self.previous_prices) > 0
            and len(self.current_allocation) > 0
        ):
            portfolio_return = 0.0

            for ticker, weight in self.current_allocation.items():

                old_price = self.previous_prices.get(ticker)
                new_price = latest_prices.get(ticker)

                if (
                    old_price is not None
                    and new_price is not None
                    and old_price > 0
                ):
                    asset_return = (
                        new_price / old_price
                    ) - 1.0

                    portfolio_return += (
                        weight * asset_return
                    )

            self.nav *= (1.0 + portfolio_return)

            if self.nav > self.peak_nav:
                self.peak_nav = self.nav

        self.previous_prices = latest_prices

        if self.peak_nav <= 0:
            return 0.0

        return (
            self.nav / self.peak_nav
        ) - 1.0

    def is_rebalance_day(self, ohlcv):
        """
        Rebalance Monday and Thursday.
        Monday = 0
        Thursday = 3
        """
        try:
            date_string = ohlcv[-1]["QQQ"]["date"]

            # Surmount examples use:
            # YYYY-MM-DD HH:MM:SS
            date_part = date_string.split(" ")[0]

            current_date = datetime.strptime(
                date_part,
                "%Y-%m-%d"
            )

            return current_date.weekday() in [0, 3]

        except:
            # If date parsing fails, allow execution rather
            # than stopping the strategy.
            return True

    # ---------------------------------------------------------
    # MAIN STRATEGY
    # ---------------------------------------------------------

    def run(self, data):

        ohlcv = data.get("ohlcv")

        if ohlcv is None:
            return TargetAllocation({})

        # Need enough history for the 150-day trend filter
        # and 126-day momentum calculation.
        if len(ohlcv) < 160:
            return TargetAllocation({})

        # -----------------------------------------------------
        # UPDATE PORTFOLIO DRAWDOWN
        # -----------------------------------------------------

        drawdown = self.update_strategy_nav(ohlcv)

        log(
            "Estimated strategy drawdown: "
            + str(round(drawdown * 100, 2))
            + "%"
        )

        # -----------------------------------------------------
        # MOVING AVERAGES
        # -----------------------------------------------------

        spy_ma_150 = SMA("SPY", ohlcv, 150)
        spy_ma_100 = SMA("SPY", ohlcv, 100)

        qqq_ma_150 = SMA("QQQ", ohlcv, 150)
        qqq_ma_50 = SMA("QQQ", ohlcv, 50)

        if (
            spy_ma_150 is None
            or spy_ma_100 is None
            or qqq_ma_150 is None
            or qqq_ma_50 is None
        ):
            return TargetAllocation({})

        spy_price = self.close_price("SPY", ohlcv)
        qqq_price = self.close_price("QQQ", ohlcv)

        if spy_price is None or qqq_price is None:
            return TargetAllocation({})

        spy_above_150 = (
            spy_price > spy_ma_150[-1]
        )

        qqq_above_150 = (
            qqq_price > qqq_ma_150[-1]
        )

        qqq_50_above_150 = (
            qqq_ma_50[-1] > qqq_ma_150[-1]
        )

        spy_above_100 = (
            spy_price > spy_ma_100[-1]
        )

        # -----------------------------------------------------
        # 20% DRAWDOWN EMERGENCY MODE
        # -----------------------------------------------------

        if drawdown <= -0.20:
            self.hard_risk_off = True

        if self.hard_risk_off:

            # Recovery rule from the original strategy:
            # remain defensive until SPY closes above 100-day MA.
            if spy_above_100:
                self.hard_risk_off = False
            else:
                allocation = {
                    "SGOV": 0.70,
                    "GLD": 0.30
                }

                self.current_allocation = allocation

                log("20% drawdown protection active")

                return TargetAllocation(allocation)

        # -----------------------------------------------------
        # ONLY CHANGE TARGETS MONDAY AND THURSDAY
        # -----------------------------------------------------

        if not self.is_rebalance_day(ohlcv):

            if len(self.current_allocation) > 0:
                return TargetAllocation(
                    self.normalize(
                        self.current_allocation
                    )
                )

            return TargetAllocation({})

        # -----------------------------------------------------
        # MOMENTUM RANKINGS
        # -----------------------------------------------------

        ranking_universe = (
            self.non_leveraged
            + self.leveraged
        )

        scores = {}

        for ticker in ranking_universe:
            scores[ticker] = self.momentum_score(
                ticker,
                ohlcv
            )

        ranked_all = sorted(
            ranking_universe,
            key=lambda ticker: scores[ticker],
            reverse=True
        )

        ranked_nonleveraged = sorted(
            self.non_leveraged,
            key=lambda ticker: scores[ticker],
            reverse=True
        )

        ranked_leveraged = sorted(
            self.leveraged,
            key=lambda ticker: scores[ticker],
            reverse=True
        )

        strongest_nonleveraged = (
            ranked_nonleveraged[0]
        )

        second_nonleveraged = (
            ranked_nonleveraged[1]
        )

        strongest_leveraged = (
            ranked_leveraged[0]
        )

        log(
            "Momentum ranking: "
            + str(ranked_all)
        )

        # -----------------------------------------------------
        # VOLATILITY FILTER
        # -----------------------------------------------------

        vol_20 = self.realized_volatility(
            "QQQ",
            ohlcv,
            20
        )

        vol_100 = self.realized_volatility(
            "QQQ",
            ohlcv,
            100
        )

        volatility_high = False

        if (
            vol_20 is not None
            and vol_100 is not None
            and vol_100 > 0
        ):
            volatility_high = (
                vol_20 >
                1.75 * vol_100
            )

        # -----------------------------------------------------
        # MARKET REGIME
        # -----------------------------------------------------

        risk_on = (
            spy_above_150
            and qqq_above_150
            and qqq_50_above_150
        )

        mixed_regime = (
            spy_above_150
            and not qqq_above_150
        )

        # -----------------------------------------------------
        # 15% DRAWDOWN CONTROL
        # -----------------------------------------------------

        if drawdown <= -0.15:

            allocation = {
                strongest_nonleveraged: 0.25,
                "SGOV": 0.50,
                "GLD": 0.25
            }

            allocation = self.normalize(allocation)
            self.current_allocation = allocation

            log("15% drawdown protection active")

            return TargetAllocation(allocation)

        # -----------------------------------------------------
        # RISK-ON REGIME
        # -----------------------------------------------------

        if risk_on:

            # At 10% drawdown or during elevated volatility,
            # leveraged ETFs are removed.
            no_leverage = (
                drawdown <= -0.10
                or volatility_high
            )

            if no_leverage:

                allocation = {
                    strongest_nonleveraged: 0.50,
                    second_nonleveraged: 0.25,
                    "SGOV": 0.25
                }

                log(
                    "Risk-on but leverage disabled"
                )

            else:

                # 50% strongest non-leveraged
                # 25% second strongest non-leveraged
                # 25% strongest leveraged ETF
                #
                # This automatically satisfies:
                # - TQQQ <= 25%
                # - total leverage <= 35%
                allocation = {
                    strongest_nonleveraged: 0.50,
                    second_nonleveraged: 0.25,
                    strongest_leveraged: 0.25
                }

                log(
                    "Full risk-on allocation"
                )

        # -----------------------------------------------------
        # MIXED REGIME
        # -----------------------------------------------------

        elif mixed_regime:

            allocation = {
                strongest_nonleveraged: 0.50,
                "GLD": 0.25,
                "SGOV": 0.25
            }

            log(
                "Mixed market regime"
            )

        # -----------------------------------------------------
        # RISK-OFF REGIME
        # -----------------------------------------------------

        else:

            allocation = {
                "SGOV": 0.70,
                "GLD": 0.30
            }

            log(
                "Risk-off market regime"
            )

        # -----------------------------------------------------
        # FINAL VALIDATION
        # -----------------------------------------------------

        allocation = self.normalize(allocation)

        self.current_allocation = allocation

        log(
            "Target allocation: "
            + str(allocation)
        )

        return TargetAllocation(allocation)