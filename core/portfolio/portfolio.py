"""
core/portfolio/portfolio.py

Tracks simulated position, cash, and PnL as a backtest engine processes
fills — Phase 4's "Portfolio/PnL tracking" task.

WHY THIS LIVES IN core/, NOT research/
------------------------------------------
This is pure state-tracking logic: cash and quantity arithmetic, no
file I/O, no dependency on research/storage.py or anything else
research-specific. core/portfolio/ was already reserved as an empty
stub in the original architecture skeleton (present since before
Phase 1), which is a strong signal this is where it belongs.

Practically: this keeps the door open for the SAME Portfolio class to
be reused outside backtesting later (e.g. tracking real portfolio
state during live/paper trading), without needing to import anything
from research/ — which core/ and services/ are never allowed to do
(see tests/unit/test_research_boundary.py). Persisting a *completed*
backtest run's results (calling research.storage.save_dataset()) is a
separate concern, handled in research/backtest/results.py instead —
that's where the boundary-crossing call belongs, not here.

SCOPE: long-only, no short-selling
--------------------------------------
Selling more than you currently hold raises a clear error rather than
silently producing a negative position and questionable PnL numbers.
Short-selling isn't part of this phase's scope — if it's needed later,
it should be added deliberately, with its own tested math, not fall
out accidentally from unclamped arithmetic here.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Fill:
    """One completed simulated trade — what a paper exchange (Gauri's
    Phase 4 piece) is expected to produce and hand to the portfolio."""
    symbol: str
    side: str  # "buy" or "sell" — matches core/strategy/base.py's Signal.action vocabulary
    quantity: float
    price: float
    fee: float
    timestamp: datetime

    def __post_init__(self):
        if self.side not in ("buy", "sell"):
            raise ValueError(f"Fill.side must be 'buy' or 'sell', got {self.side!r}")
        if self.quantity <= 0:
            raise ValueError(f"Fill.quantity must be positive, got {self.quantity}")
        if self.price <= 0:
            raise ValueError(f"Fill.price must be positive, got {self.price}")
        if self.fee < 0:
            raise ValueError(f"Fill.fee cannot be negative, got {self.fee}")


@dataclass
class _PositionState:
    quantity: float = 0.0
    avg_entry_price: float = 0.0


class Portfolio:
    """
    Tracks cash, positions, and PnL through a backtest run.

    Usage:
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.process_fill(fill)                       # as each trade happens
        portfolio.record_equity_snapshot(ts, current_prices)  # periodically, for drawdown tracking
        ...
        summary = portfolio.summary()                      # at the end of the run
    """

    def __init__(self, starting_cash: float):
        if starting_cash <= 0:
            raise ValueError(f"starting_cash must be positive, got {starting_cash}")

        self.starting_cash = starting_cash
        self.cash = starting_cash
        self._positions: dict[str, _PositionState] = {}
        self.realized_pnl = 0.0
        self.trade_log: list[dict] = []
        self.equity_curve: list[dict] = []  # [{"timestamp": ..., "equity": ...}, ...]

    def position(self, symbol: str) -> float:
        """Current held quantity for a symbol (0.0 if none)."""
        state = self._positions.get(symbol)
        return state.quantity if state else 0.0

    def process_fill(self, fill: Fill) -> None:
        """
        Applies one fill to portfolio state — updates cash, position,
        average entry price, and (on a sell) realized PnL.
        """
        state = self._positions.setdefault(fill.symbol, _PositionState())
        realized_this_trade = 0.0

        if fill.side == "buy":
            total_cost = fill.quantity * fill.price + fill.fee
            if total_cost > self.cash:
                raise ValueError(
                    f"Insufficient cash: fill for {fill.symbol} costs {total_cost:.2f}, "
                    f"only {self.cash:.2f} available"
                )

            # Weighted-average cost basis across the old and new quantity.
            new_quantity = state.quantity + fill.quantity
            state.avg_entry_price = (
                (state.avg_entry_price * state.quantity + fill.price * fill.quantity)
                / new_quantity
            )
            state.quantity = new_quantity
            self.cash -= total_cost

        else:  # sell
            if fill.quantity > state.quantity:
                raise ValueError(
                    f"Cannot sell {fill.quantity} of {fill.symbol}, only "
                    f"{state.quantity} held (short-selling is out of scope — see module docstring)"
                )

            realized_this_trade = (fill.price - state.avg_entry_price) * fill.quantity - fill.fee
            self.realized_pnl += realized_this_trade
            state.quantity -= fill.quantity
            self.cash += fill.quantity * fill.price - fill.fee
            # avg_entry_price is left as-is for any remaining quantity —
            # selling doesn't change the cost basis of what's left.

        self.trade_log.append({
            "timestamp": fill.timestamp,
            "symbol": fill.symbol,
            "side": fill.side,
            "quantity": fill.quantity,
            "price": fill.price,
            "fee": fill.fee,
            "realized_pnl": realized_this_trade,  # 0.0 for buys, real for sells
            "cash_after": self.cash,
        })

    def unrealized_pnl(self, current_prices: dict[str, float]) -> float:
        """Mark-to-market PnL on currently open positions, given current prices."""
        total = 0.0
        for symbol, state in self._positions.items():
            if state.quantity == 0:
                continue
            if symbol not in current_prices:
                raise ValueError(f"No current price provided for open position {symbol!r}")
            total += (current_prices[symbol] - state.avg_entry_price) * state.quantity
        return total

    def total_equity(self, current_prices: dict[str, float]) -> float:
        """Cash plus the current market value of all open positions."""
        position_value = sum(
            current_prices[symbol] * state.quantity
            for symbol, state in self._positions.items()
            if state.quantity > 0
        )
        return self.cash + position_value

    def record_equity_snapshot(self, timestamp: datetime, current_prices: dict[str, float]) -> None:
        """Records a point on the equity curve — call periodically through
        a run (e.g. once per processed event, or once per bar) so
        summary() can compute drawdown from something other than just
        the start and end points."""
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": self.total_equity(current_prices),
        })

    def max_drawdown(self) -> float:
        """
        Largest peak-to-trough decline in the recorded equity curve, as
        a fraction (0.10 = a 10% drawdown at some point). Returns 0.0 if
        fewer than 2 equity snapshots have been recorded.
        """
        if len(self.equity_curve) < 2:
            return 0.0

        peak = self.equity_curve[0]["equity"]
        max_dd = 0.0
        for point in self.equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)
        return max_dd

    def summary(self, current_prices: dict[str, float] | None = None) -> dict:
        """
        Final performance metrics for a completed (or in-progress) run.
        "Correct numbers first, presentation later" per the task —
        this returns plain values, no formatting/charting.

        current_prices is optional — if omitted, unrealized PnL and
        final equity assume all positions are already closed (0.0
        unrealized). Pass it to get a mark-to-market view of any still-
        open positions.
        """
        current_prices = current_prices or {}
        unrealized = self.unrealized_pnl(current_prices) if current_prices else 0.0
        final_equity = self.cash + sum(
            current_prices.get(symbol, 0) * state.quantity
            for symbol, state in self._positions.items()
        )

        sells = [t for t in self.trade_log if t["side"] == "sell"]
        winning_sells = [t for t in sells if t["realized_pnl"] > 0]
        win_rate_pct = (len(winning_sells) / len(sells) * 100) if sells else None

        return {
            "starting_cash": self.starting_cash,
            "ending_cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized,
            "final_equity": final_equity,
            "total_return_pct": (final_equity - self.starting_cash) / self.starting_cash * 100,
            "num_trades": len(self.trade_log),
            "num_buys": sum(1 for t in self.trade_log if t["side"] == "buy"),
            "num_sells": len(sells),
            "win_rate_pct": win_rate_pct,  # None if no sells have happened yet
            "max_drawdown_pct": self.max_drawdown() * 100,
        }