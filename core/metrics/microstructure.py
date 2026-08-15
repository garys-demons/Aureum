"""
Microstructure metrics — pure functions computed from OrderBook state.

Each function takes an OrderBook and returns a number (or None if there
isn't enough data yet, e.g. one side of the book is empty). No side
effects, no mutation of the book — safe to call as often as needed and
trivial to unit test against hand-calculated values.
"""
from services.market_data.order_book import OrderBook


def microprice(book: OrderBook) -> float | None:
    """
    Volume-weighted mid price between best bid and best ask.

    Leans toward whichever side has MORE size resting behind it — e.g.
    if there's a lot more size on the bid, the "fair" price should sit
    closer to the ask (counterintuitive at first: more bid pressure
    pulls the price toward the ask, because it signals the ask is more
    likely to get eaten first).
    """
    bid = book.best_bid()
    ask = book.best_ask()
    if bid is None or ask is None:
        return None

    bid_price, bid_qty = bid
    ask_price, ask_qty = ask
    total_qty = bid_qty + ask_qty
    if total_qty == 0:
        return None

    return (bid_price * ask_qty + ask_price * bid_qty) / total_qty


def depth_weighted_price(book: OrderBook, levels: int = 5) -> float | None:
    """
    Volume-weighted average price across the top N levels on each side,
    instead of just the single best bid/ask. Gives a steadier read of
    "fair price" that isn't swayed by one thin top-of-book quote.
    """
    if not book.bids or not book.asks:
        return None

    top_bids = sorted(book.bids.items(), key=lambda kv: kv[0], reverse=True)[:levels]
    top_asks = sorted(book.asks.items(), key=lambda kv: kv[0])[:levels]

    total_value = sum(price * qty for price, qty in top_bids)
    total_value += sum(price * qty for price, qty in top_asks)
    total_qty = sum(qty for _, qty in top_bids) + sum(qty for _, qty in top_asks)

    if total_qty == 0:
        return None

    return total_value / total_qty


def order_book_imbalance(book: OrderBook, levels: int | None = None) -> float | None:
    """
    Ratio of bid-side size to total size, optionally limited to the top N
    levels on each side. Returns a value between 0 and 1:
      - 0.5 means balanced (equal bid/ask pressure)
      - > 0.5 means more buying pressure
      - < 0.5 means more selling pressure
    """
    if not book.bids or not book.asks:
        return None

    if levels is not None:
        bid_qtys = [qty for _, qty in sorted(book.bids.items(), reverse=True)[:levels]]
        ask_qtys = [qty for _, qty in sorted(book.asks.items())[:levels]]
    else:
        bid_qtys = list(book.bids.values())
        ask_qtys = list(book.asks.values())

    total_bid = sum(bid_qtys)
    total_ask = sum(ask_qtys)
    total = total_bid + total_ask

    if total == 0:
        return None

    return total_bid / total