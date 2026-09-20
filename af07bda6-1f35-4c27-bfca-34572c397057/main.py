from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log


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

        self.risk_assets = (
            self.non_leveraged
            + self.leveraged
        )

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
    # HELPERS
    # ---------------------------------------------------------

    def close_price(self, ticker, ohlcv, offset=0):

        try:
            return float(
                ohlcv[-1 - offset][ticker]["close"]
            )
        except:
            return None

    def trailing_return(self, ticker, ohlcv, lookback):

        if len(ohlcv) <= lookback:
            return None

        current = self.close_price(
            ticker,
            ohlcv
        )

        try:
            past = float(
                ohlcv[-1 - lookback][ticker]["close"]
            )
        except:
            return None

        if current is None:
            return None

        if past <= 0:
            return None

        return (
            current / past
        ) - 1.0

    def momentum_score(self, ticker, ohlcv):

        return_3m = self.trailing_return(
            ticker,
            ohlcv,
            63
        )

        return_6m = self.trailing_return(
            ticker,
            ohlcv,
            126
        )

        if (
            return_3m is None
            or return_6m is None
        ):
            return -999.0

        return (
            0.50 * return_3m
            + 0.50 * return_6m
        )

    def normalize(self, allocation):

        clean = {}

        for ticker, weight in allocation.items():

            if weight > 0:
                clean[ticker] = float(weight)

        total = sum(clean.values())

        if total > 1.0:

            clean = {
                ticker: weight / total
                for ticker, weight
                in clean.items()
            }

        return clean

    # ---------------------------------------------------------
    # MAIN STRATEGY
    # ---------------------------------------------------------

    def run(self, data):

        ohlcv = data.get("ohlcv")

        # Same warm-up requirement as the version
        # that successfully generated backtest results.
        if ohlcv is None:
            return TargetAllocation({})

        if len(ohlcv) < 160:
            return TargetAllocation({})

        # -----------------------------------------------------
        # TREND FILTERS
        # -----------------------------------------------------

        spy_sma_150 = SMA(
            "SPY",
            ohlcv,
            150
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
            spy_sma_150 is None
            or qqq_sma_150 is None
            or qqq_sma_50 is None
        ):
            return TargetAllocation({})

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

        spy_above_150 = (
            spy_price >
            spy_sma_150[-1]
        )

        qqq_above_150 = (
            qqq_price >
            qqq_sma_150[-1]
        )

        qqq_trend_positive = (
            qqq_sma_50[-1] >
            qqq_sma_150[-1]
        )

        # -----------------------------------------------------
        # MOMENTUM RANKING
        # -----------------------------------------------------

        scores = {}

        for ticker in self.risk_assets:

            scores[ticker] = (
                self.momentum_score(
                    ticker,
                    ohlcv
                )
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
        # FULL RISK-ON
        # -----------------------------------------------------

        risk_on = (
            spy_above_150
            and qqq_above_150
            and qqq_trend_positive
        )

        if risk_on:

            leveraged_return = (
                self.trailing_return(
                    best_leveraged,
                    ohlcv,
                    126
                )
            )

            # Use leverage only if its own
            # six-month momentum is positive.
            if (
                leveraged_return is not None
                and leveraged_return > 0
            ):

                allocation = {
                    best_nonleveraged: 0.50,
                    second_nonleveraged: 0.25,
                    best_leveraged: 0.25
                }

                log(
                    "FULL RISK-ON"
                )

            else:

                allocation = {
                    best_nonleveraged: 0.60,
                    second_nonleveraged: 0.40
                }

                log(
                    "RISK-ON WITHOUT LEVERAGE"
                )

        # -----------------------------------------------------
        # MIXED REGIME
        # -----------------------------------------------------

        elif (
            spy_above_150
            or qqq_above_150
        ):

            allocation = {
                best_nonleveraged: 0.50,
                "GLD": 0.25,
                "SGOV": 0.25
            }

            log(
                "MIXED REGIME"
            )

        # -----------------------------------------------------
        # RISK-OFF
        # -----------------------------------------------------

        else:

            gld_return = (
                self.trailing_return(
                    "GLD",
                    ohlcv,
                    126
                )
            )

            if (
                gld_return is not None
                and gld_return > 0
            ):

                allocation = {
                    "SGOV": 0.70,
                    "GLD": 0.30
                }

            else:

                allocation = {
                    "SGOV": 1.00
                }

            log(
                "RISK-OFF"
            )

        # -----------------------------------------------------
        # FINAL ALLOCATION
        # -----------------------------------------------------

        allocation = self.normalize(
            allocation
        )

        log(
            "Target allocation: "
            + str(allocation)
        )

        return TargetAllocation(
            allocation
        )