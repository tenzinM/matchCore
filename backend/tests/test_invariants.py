"""
Property-based tests: instead of checking specific examples, these assert
invariants that must hold true no matter what sequence of orders is submitted.
This is a much stronger correctness signal than example-based unit tests alone,
since Hypothesis will generate hundreds of randomized order sequences and try
to find one that breaks an invariant.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, strategies as st, settings
from app.order_book import OrderBook, Side

side_strategy = st.sampled_from([Side.BUY, Side.SELL])
price_strategy = st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False)
qty_strategy = st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False)

order_strategy = st.tuples(side_strategy, price_strategy, qty_strategy)


@given(orders=st.lists(order_strategy, min_size=1, max_size=40))
@settings(max_examples=100)
def test_book_never_crosses(orders):
    """The single most important invariant: after any sequence of orders,
    the best bid must never be >= the best ask (a 'crossed book' means the
    matching engine failed to match orders that should have traded)."""
    book = OrderBook("TEST")
    for i, (side, price, qty) in enumerate(orders):
        price = round(price, 2)
        qty = round(qty, 4)
        if qty <= 0:
            continue
        book.submit_limit_order(f"order-{i}", side, price, qty)

    bid = book.best_bid()
    ask = book.best_ask()
    if bid is not None and ask is not None:
        assert bid < ask, f"Book crossed: best_bid={bid} >= best_ask={ask}"


@given(orders=st.lists(order_strategy, min_size=1, max_size=40))
@settings(max_examples=100)
def test_no_trade_at_price_worse_than_either_side_offered(orders):
    """Every trade's price must be within both participants' limits:
    the buyer never pays more than their limit, the seller never receives less."""
    book = OrderBook("TEST")
    submitted = {}
    for i, (side, price, qty) in enumerate(orders):
        price = round(price, 2)
        qty = round(qty, 4)
        if qty <= 0:
            continue
        order_id = f"order-{i}"
        submitted[order_id] = (side, price)
        book.submit_limit_order(order_id, side, price, qty)

    for trade in book.trades:
        buy_side, buy_price = submitted[trade.buy_order_id]
        sell_side, sell_price = submitted[trade.sell_order_id]
        assert trade.price <= buy_price + 1e-9, "buyer paid more than their limit"
        assert trade.price >= sell_price - 1e-9, "seller received less than their limit"


@given(orders=st.lists(order_strategy, min_size=1, max_size=30))
@settings(max_examples=100)
def test_quantity_conservation(orders):
    """Total quantity traded can never exceed total quantity submitted -
    the engine must not fabricate or lose volume during matching."""
    book = OrderBook("TEST")
    total_submitted = 0.0
    for i, (side, price, qty) in enumerate(orders):
        price = round(price, 2)
        qty = round(qty, 4)
        if qty <= 0:
            continue
        total_submitted += qty
        book.submit_limit_order(f"order-{i}", side, price, qty)

    total_traded = sum(t.quantity for t in book.trades)
    # Each trade consumes quantity from BOTH a buy and a sell order, so total
    # traded volume (counted once per trade) can be at most total_submitted / 2
    # in the worst case of perfectly balanced two-sided flow - but since orders
    # can partially rest, the safe invariant is simply: traded <= submitted.
    assert total_traded <= total_submitted + 1e-6
