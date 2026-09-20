#TacticalETFRedo
from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log

from datetime import datetime
from math import log as math_log, sqrt

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

        self.risk_assets = [
            "QQQ",
            "SOXX",
            "SMH",
            "XLI",
            "QLD",
            "TQQQ",
            "SPXL"
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

        current = self.close_price(ticker, ohlcv)

        try:
            past = float(
                ohlcv[-1 - lookback][ticker]["close"]
            )
        except:
            return None

        if current is None or past <= 0:
            return None

        return current / past - 1.0

    def momentum_score(self, ticker, ohlcv):
        """
        Momentum score:
        40% 3-month return
        40% 6-month return
        20% 12-month return
        """

        r3 = self.trailing_return(ticker, ohlcv, 63)
        r6 = self.trailing_return(ticker, ohlcv, 126)
        r12 = self.trailing_return(ticker, ohlcv, 252)

        if r3 is None or r6 is None or r12 is None:
            return -999.0

        return (
            0.40 * r3
            + 0.40 * r6
            + 0.20 * r12
        )

    # ---------------------------------------------------------
    # MAIN STRATEGY
    # ---------------------------------------------------------

    def run(self, data):

        ohlcv = data.get("ohlcv")

        if ohlcv is None or len(ohlcv) < 260:
            return TargetAllocation({})

        # -----------------------------------------------------
        # MARKET TREND FILTERS
        # -----------------------------------------------------

        spy_sma_200 = SMA("SPY", ohlcv, 200)
        spy_sma_50 = SMA("SPY", ohlcv, 50)

        qqq_sma_200 = SMA("QQQ", ohlcv, 200)
        qqq_sma_50 = SMA("QQQ", ohlcv, 50)

        if (
            spy_sma_200 is None
            or spy_sma_50 is None
            or qqq_sma_200 is None
            or qqq_sma_50 is None
        ):
            return TargetAllocation({})

        spy_price = self.close_price("SPY", ohlcv)
        qqq_price = self.close_price("QQQ", ohlcv)

        if spy_price is None or qqq_price is None:
            return TargetAllocation({})

        spy_bullish = (
            spy_price > spy_sma_200[-1]
            and spy_sma_50[-1] > spy_sma_200[-1]
        )

        qqq_bullish = (
            qqq_price > qqq_sma_200[-1]
            and qqq_sma_50[-1] > qqq_sma_200[-1]
        )

        # -----------------------------------------------------
        # MOMENTUM RANKING
        # -----------------------------------------------------

        scores = {}

        for ticker in self.risk_assets:
            scores[ticker] = self.momentum_score(
                ticker,
                ohlcv
            )

        ranked_all = sorted(
            self.risk_assets,
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

        best_nonleveraged = ranked_nonleveraged[0]
        second_nonleveraged = ranked_nonleveraged[1]
        best_leveraged = ranked_leveraged[0]

        log("Momentum ranking: " + str(ranked_all))
        log("Momentum scores: " + str(scores))

        # -----------------------------------------------------
        # FULL RISK-ON
        # -----------------------------------------------------

        if spy_bullish and qqq_bullish:

            # Require positive medium-term momentum
            best_nonlev_return = self.trailing_return(
                best_nonleveraged,
                ohlcv,
                126
            )

            best_lev_return = self.trailing_return(
                best_leveraged,
                ohlcv,
                126
            )

            # If the strongest leveraged ETF also has
            # positive 6-month momentum, use it.
            if (
                best_lev_return is not None
                and best_lev_return > 0
            ):

                allocation = {
                    best_nonleveraged: 0.45,
                    second_nonleveraged: 0.30,
                    best_leveraged: 0.25
                }

                log("FULL RISK-ON WITH LEVERAGE")

            else:

                allocation = {
                    best_nonleveraged: 0.60,
                    second_nonleveraged: 0.40
                }

                log("RISK-ON WITHOUT LEVERAGE")

            return TargetAllocation(allocation)

        # -----------------------------------------------------
        # PARTIAL RISK-ON
        # -----------------------------------------------------

        elif spy_bullish or qqq_bullish:

            strongest = ranked_nonleveraged[0]

            allocation = {
                strongest: 0.60,
                "GLD": 0.20,
                "SGOV": 0.20
            }

            log("PARTIAL RISK-ON")

            return TargetAllocation(allocation)

        # -----------------------------------------------------
        # RISK-OFF
        # -----------------------------------------------------

        else:

            gld_return = self.trailing_return(
                "GLD",
                ohlcv,
                126
            )

            if (
                gld_return is not None
                and gld_return > 0
            ):

                allocation = {
                    "GLD": 0.40,
                    "SGOV": 0.60
                }

            else:

                allocation = {
                    "SGOV": 1.00
                }

            log("RISK-OFF")

            return TargetAllocation(allocation)