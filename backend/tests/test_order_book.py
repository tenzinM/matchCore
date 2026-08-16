import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.order_book import OrderBook, Side


def test_no_match_when_no_crossing_orders():
    book = OrderBook("TEST")
    trades = book.submit_limit_order("b1", Side.BUY, price=99.0, quantity=10)
    assert trades == []
    assert book.best_bid() == 99.0
    assert book.best_ask() is None


def test_simple_full_match():
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=100.0, quantity=10)
    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=10)

    assert len(trades) == 1
    assert trades[0].price == 100.0
    assert trades[0].quantity == 10
    assert trades[0].buy_order_id == "b1"
    assert trades[0].sell_order_id == "s1"
    assert book.best_bid() is None
    assert book.best_ask() is None


def test_trade_executes_at_resting_price_not_incoming_price():
    """A key correctness property: the incoming order should NOT get a worse
    price than what it offered, and should get the RESTING order's price."""
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=98.0, quantity=10)
    # Buyer is willing to pay up to 100, but should only pay the resting ask of 98
    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=10)
    assert trades[0].price == 98.0


def test_partial_fill_leaves_remainder_resting():
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=100.0, quantity=5)
    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=10)

    assert len(trades) == 1
    assert trades[0].quantity == 5
    assert book.is_resting("b1")
    snapshot = book.snapshot()
    assert snapshot["bids"][0]["quantity"] == 5


def test_price_time_priority_same_price():
    """Among orders at the same price, the earlier order should fill first."""
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=100.0, quantity=5)
    book.submit_limit_order("s2", Side.SELL, price=100.0, quantity=5)

    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=5)
    assert trades[0].sell_order_id == "s1"  # earlier order filled first


def test_price_priority_over_time():
    """A better-priced order should fill before an earlier but worse-priced order."""
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=101.0, quantity=5)  # earlier, worse price
    book.submit_limit_order("s2", Side.SELL, price=100.0, quantity=5)  # later, better price

    trades = book.submit_limit_order("b1", Side.BUY, price=101.0, quantity=5)
    assert trades[0].sell_order_id == "s2"  # better price wins despite arriving later


def test_cancel_removes_order_from_book():
    book = OrderBook("TEST")
    book.submit_limit_order("b1", Side.BUY, price=99.0, quantity=10)
    assert book.cancel_order("b1") is True
    assert book.best_bid() is None


def test_cancel_nonexistent_order_returns_false():
    book = OrderBook("TEST")
    assert book.cancel_order("nope") is False


def test_cancelled_order_does_not_participate_in_matching():
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=100.0, quantity=10)
    book.cancel_order("s1")
    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=10)
    assert trades == []  # cancelled order should be skipped, not matched
    assert book.is_resting("b1")


def test_duplicate_order_id_rejected():
    book = OrderBook("TEST")
    book.submit_limit_order("b1", Side.BUY, price=99.0, quantity=10)
    try:
        book.submit_limit_order("b1", Side.BUY, price=99.0, quantity=5)
        assert False, "should have raised"
    except ValueError:
        pass


def test_multiple_resting_orders_consumed_by_large_incoming_order():
    book = OrderBook("TEST")
    book.submit_limit_order("s1", Side.SELL, price=100.0, quantity=5)
    book.submit_limit_order("s2", Side.SELL, price=100.0, quantity=5)
    trades = book.submit_limit_order("b1", Side.BUY, price=100.0, quantity=10)

    assert len(trades) == 2
    assert sum(t.quantity for t in trades) == 10
    assert book.best_ask() is None
