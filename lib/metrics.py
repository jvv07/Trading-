"""
Performance and risk metrics — all functions accept pandas Series.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sharpe(returns: pd.Series, risk_free: float = 0.05) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    excess = r - risk_free / TRADING_DAYS
    std = excess.std()
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS)) if std else 0.0


def sortino(returns: pd.Series, risk_free: float = 0.05) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    excess = r - risk_free / TRADING_DAYS
    downside = excess[excess < 0].std()
    return float(excess.mean() / downside * np.sqrt(TRADING_DAYS)) if downside else 0.0


def max_drawdown(equity: pd.Series) -> float:
    eq = equity.dropna()
    if eq.empty:
        return 0.0
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    return float(dd.min())


def drawdown_series(equity: pd.Series) -> pd.Series:
    eq = equity.dropna()
    roll_max = eq.cummax()
    return (eq - roll_max) / roll_max


def calmar(returns: pd.Series, equity: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    annual = (1 + r.mean()) ** TRADING_DAYS - 1
    mdd = abs(max_drawdown(equity))
    return float(annual / mdd) if mdd else 0.0


def annual_return(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    return float((1 + r.mean()) ** TRADING_DAYS - 1)


def win_rate(pnls: pd.Series) -> float:
    p = pnls.dropna()
    if len(p) == 0:
        return 0.0
    return float((p > 0).sum() / len(p))


def profit_factor(pnls: pd.Series) -> float:
    p = pnls.dropna()
    gross_win = p[p > 0].sum()
    gross_loss = abs(p[p < 0].sum())
    return float(gross_win / gross_loss) if gross_loss else float("inf")


def var_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    r = returns.dropna()
    return float(r.quantile(1 - confidence)) if len(r) else 0.0


def cvar_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    r = returns.dropna()
    if r.empty:
        return 0.0
    v = var_historical(r, confidence)
    tail = r[r <= v]
    return float(tail.mean()) if not tail.empty else v


def beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    p = portfolio_returns.dropna()
    b = benchmark_returns.dropna()
    aligned = pd.concat([p, b], axis=1).dropna()
    if len(aligned) < 2:
        return 1.0
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
    return float(cov[0, 1] / cov[1, 1]) if cov[1, 1] else 1.0


def alpha(portfolio_returns: pd.Series, benchmark_returns: pd.Series, risk_free: float = 0.05) -> float:
    b = beta(portfolio_returns, benchmark_returns)
    p_ann = annual_return(portfolio_returns)
    bm_ann = annual_return(benchmark_returns)
    return float(p_ann - (risk_free + b * (bm_ann - risk_free)))


def rolling_sharpe(returns: pd.Series, window: int = 63) -> pd.Series:
    def _s(r):
        return sharpe(pd.Series(r))
    return returns.dropna().rolling(window).apply(_s, raw=True)


def summary(returns: pd.Series, equity: pd.Series, trade_pnls: pd.Series = None) -> dict:
    out = {
        "Total Return": f"{(equity.iloc[-1] / equity.iloc[0] - 1) * 100:.2f}%" if len(equity) > 1 else "N/A",
        "Annual Return": f"{annual_return(returns) * 100:.2f}%",
        "Sharpe Ratio": f"{sharpe(returns):.2f}",
        "Sortino Ratio": f"{sortino(returns):.2f}",
        "Max Drawdown": f"{max_drawdown(equity) * 100:.2f}%",
        "Calmar Ratio": f"{calmar(returns, equity):.2f}",
        "VaR 95%": f"{var_historical(returns) * 100:.2f}%",
        "CVaR 95%": f"{cvar_historical(returns) * 100:.2f}%",
    }
    if trade_pnls is not None and len(trade_pnls):
        out.update({
            "Win Rate": f"{win_rate(trade_pnls) * 100:.1f}%",
            "Profit Factor": f"{profit_factor(trade_pnls):.2f}",
            "Avg Win": f"${trade_pnls[trade_pnls > 0].mean():.2f}" if (trade_pnls > 0).any() else "N/A",
            "Avg Loss": f"${trade_pnls[trade_pnls < 0].mean():.2f}" if (trade_pnls < 0).any() else "N/A",
        })
    return out
