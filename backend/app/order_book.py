"""
Core limit order book with price-time priority matching.

This is deliberately dependency-free (no external libs) so the algorithm itself
is fully visible and auditable - the same reason real exchange cores are often
written in plain, low-level code rather than wrapped in heavy frameworks.

Matching rule: price-time priority.
  - Orders are matched at the RESTING order's price (the order that was already
    in the book), not the incoming order's price - this is standard exchange
    behavior and avoids giving incoming orders a price advantage.
  - Among orders at the same price, earlier orders match first (time priority).

Data structure choice:
  - Bids and asks are each stored in a heap keyed by (price, sequence).
    - Bids use negated price so the heap (a min-heap) surfaces the HIGHEST bid first.
    - Asks use price directly so the heap surfaces the LOWEST ask first.
    - Sequence number breaks ties by arrival order (time priority) and also
      gives every order a unique, comparable second key so Python never has to
      compare Order objects directly.
  - heapq doesn't support O(log n) removal, so cancellations are handled with
    LAZY DELETION: a cancelled order is marked inactive and simply skipped when
    it's eventually popped off the heap. This trades a small amount of wasted
    heap space for much simpler, faster cancellation.
"""
import heapq
import itertools
from dataclasses import dataclass, field
from enum import Enum
from time import time


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    order_id: str
    side: Side
    price: float
    quantity: float
    remaining: float
    timestamp: float
    active: bool = True


@dataclass
class Trade:
    trade_id: int
    price: float
    quantity: float
    buy_order_id: str
    sell_order_id: str
    timestamp: float


class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self._bids: list[tuple[float, int, Order]] = []   # heap of (-price, seq, order)
        self._asks: list[tuple[float, int, Order]] = []   # heap of (price, seq, order)
        self._orders: dict[str, Order] = {}
        self._seq = itertools.count()
        self._trade_seq = itertools.count(1)
        self.trades: list[Trade] = []

    # ---------- public API ----------

    def submit_limit_order(self, order_id: str, side: Side, price: float, quantity: float) -> list[Trade]:
        if price <= 0 or quantity <= 0:
            raise ValueError("price and quantity must be positive")
        if order_id in self._orders:
            raise ValueError(f"duplicate order_id: {order_id}")

        order = Order(
            order_id=order_id,
            side=side,
            price=price,
            quantity=quantity,
            remaining=quantity,
            timestamp=time(),
        )
        self._orders[order_id] = order

        trades = self._match(order)

        # Whatever remains after matching rests on the book
        if order.remaining > 0 and order.active:
            seq = next(self._seq)
            if side == Side.BUY:
                heapq.heappush(self._bids, (-price, seq, order))
            else:
                heapq.heappush(self._asks, (price, seq, order))

        return trades

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or not order.active or order.remaining <= 0:
            return False
        order.active = False  # lazy deletion: skipped when popped from heap
        return True

    def is_resting(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        return bool(order and order.active and order.remaining > 0)

    def snapshot(self, depth: int = 10) -> dict:
        """Aggregated price-level view of the book, best price first on each side."""
        bid_levels = self._aggregate(self._bids, depth, is_bid=True)
        ask_levels = self._aggregate(self._asks, depth, is_bid=False)
        return {"symbol": self.symbol, "bids": bid_levels, "asks": ask_levels}

    def best_bid(self) -> float | None:
        self._prune(self._bids)
        return -self._bids[0][0] if self._bids else None

    def best_ask(self) -> float | None:
        self._prune(self._asks)
        return self._asks[0][0] if self._asks else None

    # ---------- internals ----------

    def _match(self, incoming: Order) -> list[Trade]:
        trades = []
        book = self._asks if incoming.side == Side.BUY else self._bids

        while incoming.remaining > 0:
            self._prune(book)
            if not book:
                break

            top = book[0]
            resting_price = -top[0] if incoming.side == Side.SELL else top[0]
            resting_order = top[2]

            crosses = (
                incoming.price >= resting_price
                if incoming.side == Side.BUY
                else incoming.price <= resting_price
            )
            if not crosses:
                break

            fill_qty = min(incoming.remaining, resting_order.remaining)
            trade_price = resting_price  # trades execute at the resting order's price

            incoming.remaining -= fill_qty
            resting_order.remaining -= fill_qty

            buy_id = incoming.order_id if incoming.side == Side.BUY else resting_order.order_id
            sell_id = resting_order.order_id if incoming.side == Side.BUY else incoming.order_id

            trade = Trade(
                trade_id=next(self._trade_seq),
                price=trade_price,
                quantity=fill_qty,
                buy_order_id=buy_id,
                sell_order_id=sell_id,
                timestamp=time(),
            )
            trades.append(trade)
            self.trades.append(trade)

            if resting_order.remaining <= 0:
                resting_order.active = False
                heapq.heappop(book)
            # if resting order still has quantity left, incoming must be fully filled
            # (since fill_qty = min(...)), so the loop will exit on the next check

        return trades

    @staticmethod
    def _prune(book: list) -> None:
        """Discard cancelled/exhausted orders sitting at the top of the heap."""
        while book and (not book[0][2].active or book[0][2].remaining <= 0):
            heapq.heappop(book)

    @staticmethod
    def _aggregate(book: list, depth: int, is_bid: bool) -> list[dict]:
        # Aggregate remaining quantity by price level without mutating the real heap
        levels: dict[float, float] = {}
        order_of_levels: list[float] = []
        for price_key, _seq, order in sorted(book):
            if not order.active or order.remaining <= 0:
                continue
            price = -price_key if is_bid else price_key
            if price not in levels:
                levels[price] = 0
                order_of_levels.append(price)
            levels[price] += order.remaining

        order_of_levels.sort(reverse=is_bid)
        return [{"price": p, "quantity": levels[p]} for p in order_of_levels[:depth]]
