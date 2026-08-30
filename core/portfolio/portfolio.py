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

SHORT-SELLING SUPPORT (added Phase 5)
------------------------------------------
Originally long-only, with short-selling explicitly documented as
"out of scope — add deliberately if needed later." That moment arrived
building the Phase 5 baseline evaluation: BaselineMarketMaker quotes
both a bid and an ask before holding any inventory — a real two-sided
market maker routinely goes net short, that's not an edge case, it's
the normal behavior being tested. So this now supports both directions:

- A position's `quantity` can be positive (long) or negative (short).
- A fill in the OPPOSITE direction of the current position first
  CLOSES existing exposure (realizing PnL on that portion), and any
  remainder beyond that OPENS a new position in the new direction
  (e.g. selling 150 while long 100 realizes PnL on 100, then opens a
  new 50-unit short at the fill price).
- Cash impact is unaffected by long/short/opening/closing — buying
  always costs cash, selling always receives cash, regardless of
  what it does to the position. Only realized PnL and the position's
  average entry price need the open/close/flip logic above.
- No margin requirement is enforced for opening a short (a real
  broker would require margin; this is a documented simplification —
  the goal here is a correct PnL/win-rate/drawdown reference number
  for the baseline, not a margin-risk-managed simulation).
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
    quantity: float = 0.0  # positive = long, negative = short, 0 = flat
    avg_entry_price: float = 0.0


class Portfolio:
    """
    Tracks cash, positions (long or short), and PnL through a backtest run.

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
        """Current position for a symbol — positive if long, negative
        if short, 0.0 if flat/never traded."""
        state = self._positions.get(symbol)
        return state.quantity if state else 0.0

    def process_fill(self, fill: Fill) -> None:
        """
        Applies one fill to portfolio state. A fill in the opposite
        direction of the current position closes existing exposure
        first (realizing PnL on that portion), then opens a new
        position in the new direction with any remaining quantity —
        see module docstring for the full explanation.
        """
        state = self._positions.setdefault(fill.symbol, _PositionState())
        signed_qty = fill.quantity if fill.side == "buy" else -fill.quantity

        # Cash impact doesn't care about long/short/open/close — buying
        # costs cash, selling receives cash, always.
        if fill.side == "buy":
            cash_impact = -(fill.quantity * fill.price + fill.fee)
            if -cash_impact > self.cash:
                raise ValueError(
                    f"Insufficient cash: fill for {fill.symbol} costs {-cash_impact:.2f}, "
                    f"only {self.cash:.2f} available"
                )
        else:
            cash_impact = fill.quantity * fill.price - fill.fee
            # No margin check for opening/extending a short — documented
            # simplification, see module docstring.

        old_qty = state.quantity
        new_qty = old_qty + signed_qty
        realized_this_trade = 0.0

        same_direction_or_flat = old_qty == 0 or (old_qty > 0) == (signed_qty > 0)
        if same_direction_or_flat:
            closing_qty = 0.0
            opening_qty = abs(signed_qty)
        else:
            closing_qty = min(abs(signed_qty), abs(old_qty))
            opening_qty = abs(signed_qty) - closing_qty

        if closing_qty > 0:
            if old_qty > 0:  # was long, this fill sells — profit if price rose
                realized_this_trade = (fill.price - state.avg_entry_price) * closing_qty
            else:  # was short, this fill buys — profit if price fell
                realized_this_trade = (state.avg_entry_price - fill.price) * closing_qty
            # Fee allocated proportionally to the closing portion.
            realized_this_trade -= fill.fee * (closing_qty / abs(signed_qty))
            self.realized_pnl += realized_this_trade

        if opening_qty > 0:
            if closing_qty > 0:
                # Position fully closed and flipped direction — the old
                # position is gone, this is a fresh cost basis.
                state.avg_entry_price = fill.price
            else:
                # Extending an existing same-direction position —
                # weighted average across old and new quantity.
                total_existing = abs(old_qty)
                state.avg_entry_price = (
                    (state.avg_entry_price * total_existing + fill.price * opening_qty)
                    / (total_existing + opening_qty)
                )

        state.quantity = new_qty
        if new_qty == 0:
            state.avg_entry_price = 0.0  # flat — cost basis no longer meaningful
        self.cash += cash_impact

        self.trade_log.append({
            "timestamp": fill.timestamp,
            "symbol": fill.symbol,
            "side": fill.side,
            "quantity": fill.quantity,
            "price": fill.price,
            "fee": fill.fee,
            "realized_pnl": realized_this_trade,  # 0.0 unless this fill closed exposure
            "cash_after": self.cash,
        })

    def unrealized_pnl(self, current_prices: dict[str, float]) -> float:
        """
        Mark-to-market PnL on currently open positions (long or short),
        given current prices. The formula is direction-agnostic: a
        negative (short) quantity naturally flips the sign correctly —
        price rising while short produces negative unrealized PnL, and
        vice versa, with no special-casing needed.
        """
        total = 0.0
        for symbol, state in self._positions.items():
            if state.quantity == 0:
                continue
            if symbol not in current_prices:
                raise ValueError(f"No current price provided for open position {symbol!r}")
            total += (current_prices[symbol] - state.avg_entry_price) * state.quantity
        return total

    def total_equity(self, current_prices: dict[str, float]) -> float:
        """
        Cash plus the current market value of all open positions. A
        short position contributes negatively here (naturally, since
        its quantity is negative) — you owe those units back.
        """
        position_value = sum(
            current_prices[symbol] * state.quantity
            for symbol, state in self._positions.items()
            if state.quantity != 0
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

        # A "closing" trade is any fill (buy OR sell) that realized
        # nonzero PnL — with short-selling, a profitable BUY (covering
        # a short) is just as much a "win" as a profitable sell closing
        # a long. Simplification: a trade closing at exactly breakeven
        # (realized_pnl == 0.0) isn't counted either way — documented,
        # not expected to matter in practice.
        closing_trades = [t for t in self.trade_log if t["realized_pnl"] != 0]
        winning_trades = [t for t in closing_trades if t["realized_pnl"] > 0]
        win_rate_pct = (len(winning_trades) / len(closing_trades) * 100) if closing_trades else None

        return {
            "starting_cash": self.starting_cash,
            "ending_cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized,
            "final_equity": final_equity,
            "total_return_pct": (final_equity - self.starting_cash) / self.starting_cash * 100,
            "num_trades": len(self.trade_log),
            "num_buys": sum(1 for t in self.trade_log if t["side"] == "buy"),
            "num_sells": sum(1 for t in self.trade_log if t["side"] == "sell"),
            "num_closing_trades": len(closing_trades),
            "win_rate_pct": win_rate_pct,  # None if no closing trades yet
            "max_drawdown_pct": self.max_drawdown() * 100,
        }