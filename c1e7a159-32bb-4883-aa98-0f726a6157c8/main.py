{
  "recommendations": [
    {
      "ticker": "QQQ",
      "company_name": "Invesco QQQ Trust (Nasdaq-100 ETF)",
      "allocation": 30.0,
      "relevance_score": 5,
      "reasoning": "Core non-leveraged growth ETF tracking the Nasdaq-100. Serves as a primary holding during risk-on periods when momentum scoring favors technology and growth exposure."
    },
    {
      "ticker": "SOXX",
      "company_name": "iShares Semiconductor ETF",
      "allocation": 20.0,
      "relevance_score": 5,
      "reasoning": "Semiconductor-focused ETF providing concentrated exposure to the chip sector. Eligible for higher allocation during strong momentum regimes."
    },
    {
      "ticker": "SMH",
      "company_name": "VanEck Semiconductor ETF",
      "allocation": 0.0,
      "relevance_score": 4,
      "reasoning": "Alternative semiconductor ETF included in the momentum ranking universe. Receives allocation when its relative momentum exceeds competing equity ETFs."
    },
    {
      "ticker": "TQQQ",
      "company_name": "ProShares UltraPro QQQ",
      "allocation": 20.0,
      "relevance_score": 4,
      "reasoning": "Leveraged Nasdaq-100 ETF used only during confirmed risk-on conditions. Maximum allocation is limited to 25 percent and it is removed during elevated volatility or drawdown conditions."
    },
    {
      "ticker": "QLD",
      "company_name": "ProShares Ultra QQQ",
      "allocation": 0.0,
      "relevance_score": 3,
      "reasoning": "Two-times leveraged Nasdaq-100 ETF included in the momentum ranking universe. Subject to the total leveraged exposure limit."
    },
    {
      "ticker": "SPXL",
      "company_name": "Direxion Daily S&P 500 Bull 3X Shares",
      "allocation": 0.0,
      "relevance_score": 3,
      "reasoning": "Leveraged S&P 500 ETF providing broad-market leveraged exposure when relative momentum is strong."
    },
    {
      "ticker": "XLI",
      "company_name": "Industrial Select Sector SPDR Fund",
      "allocation": 0.0,
      "relevance_score": 4,
      "reasoning": "Industrial-sector ETF that broadens the strategy beyond technology and semiconductors. It can receive allocation when industrials demonstrate stronger relative momentum."
    },
    {
      "ticker": "GLD",
      "company_name": "SPDR Gold Shares",
      "allocation": 15.0,
      "relevance_score": 5,
      "reasoning": "Defensive asset used as a portfolio diversifier during mixed and risk-off market regimes."
    },
    {
      "ticker": "SGOV",
      "company_name": "iShares 0-3 Month Treasury Bond ETF",
      "allocation": 15.0,
      "relevance_score": 5,
      "reasoning": "Short-duration Treasury ETF serving as the defensive cash-equivalent allocation during periods of elevated risk."
    }
  ],
  "strategy_summary": "High-growth tactical momentum strategy that rotates between growth ETFs, leveraged ETFs, industrials, gold, and short-term Treasuries based on trend, momentum, volatility, and drawdown conditions. Risk-on positioning is permitted only during favorable SPY and QQQ trends. Leveraged exposure is capped and removed during volatility spikes or significant drawdowns.",
  "risk_assessment": "High",
  "rebalancing_frequency": 3.5,
  "rebalancing_period": "days",
  "implementation_notes": {
    "market_regime_indicators": [
      "SPY versus 150-day moving average",
      "QQQ versus 150-day moving average",
      "QQQ 50-day moving average versus QQQ 150-day moving average",
      "VIX versus its 50-day average",
      "QQQ 20-day realized volatility versus QQQ 100-day realized volatility",
      "Portfolio drawdown level"
    ],
    "risk_on_allocation_rules": [
      "Rank QQQ, SOXX, SMH, XLI, QLD, TQQQ, and SPXL by momentum",
      "50 percent to the highest-ranked non-leveraged ETF",
      "25 percent to the second-highest-ranked ETF",
      "Up to 25 percent to the highest-ranked leveraged ETF",
      "Maximum 25 percent allocation to TQQQ",
      "Maximum 35 percent total allocation to leveraged ETFs"
    ],
    "mixed_regime_allocation": [
      "If SPY is above its 150-day moving average and QQQ is below its 150-day moving average, use zero leveraged exposure",
      "Allocate 50 percent to the strongest non-leveraged equity ETF among QQQ, SOXX, SMH, and XLI",
      "Allocate 25 percent to GLD",
      "Allocate 25 percent to SGOV"
    ],
    "risk_off_allocation": [
      "If both SPY and QQQ are below their 150-day moving averages, use zero equity exposure",
      "Allocate 70 percent to SGOV",
      "Allocate 30 percent to GLD"
    ],
    "volatility_override": [
      "If VIX is above its 50-day average, remove all leveraged ETFs",
      "If QQQ 20-day realized volatility exceeds 1.75 times QQQ 100-day realized volatility, remove all leveraged ETFs",
      "Maintain eligible non-leveraged equity exposure unless drawdown controls are triggered"
    ],
    "drawdown_controls": [
      "At a 10 percent drawdown, reduce leveraged exposure to zero",
      "At a 15 percent drawdown, reduce total equity exposure to 25 percent",
      "At a 20 percent drawdown, allocate entirely to SGOV and GLD",
      "Resume normal regime rules after SPY closes above its 100-day moving average"
    ],
    "momentum_scoring_methodology": "Composite momentum score equals 50 percent of 3-month return plus 50 percent of 6-month return. Calculate the score for QQQ, SOXX, SMH, XLI, QLD, TQQQ, and SPXL and rank from highest to lowest.",
    "optimization_constraints": [
      "Target maximum drawdown below 25 percent",
      "Penalize excessive turnover",
      "Average leveraged exposure must not exceed 35 percent",
      "Maximum allocation to TQQQ is 25 percent",
      "Maximize CAGR subject to the stated risk constraints"
    ],
    "current_allocation_rationale": "The illustrative allocation is QQQ 30 percent, SOXX 20 percent, TQQQ 20 percent, GLD 15 percent, and SGOV 15 percent. SMH, QLD, SPXL, and XLI remain in the eligible ranking universe with zero current allocation. Future allocations should change according to trend, momentum, volatility, and drawdown conditions."
  }
}