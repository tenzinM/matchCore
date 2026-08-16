"""
Fires a large number of randomized orders directly at the OrderBook (in-process,
no network overhead) to measure pure matching engine throughput and latency.

For an end-to-end number that includes the FastAPI/HTTP layer, see the
`load_test_http.py` variant instructions in the README - this script isolates
the algorithm itself, which is the number worth quoting when describing the
engine's performance characteristics.

Usage:
    python load_test.py --orders 100000
"""
import argparse
import random
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.order_book import OrderBook, Side


def run_load_test(num_orders: int, seed: int = 42) -> None:
    random.seed(seed)
    book = OrderBook("LOAD")

    latencies = []
    start = time.perf_counter()

    for i in range(num_orders):
        side = random.choice([Side.BUY, Side.SELL])
        # Cluster prices around 100 so a meaningful fraction of orders actually cross
        price = round(random.gauss(100, 2), 2)
        price = max(price, 0.01)
        qty = round(random.uniform(1, 50), 2)

        t0 = time.perf_counter()
        book.submit_limit_order(f"order-{i}", side, price, qty)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)  # ms

    total_time = time.perf_counter() - start
    latencies.sort()

    print(f"\n=== MatchCore Load Test ===")
    print(f"Orders submitted:     {num_orders:,}")
    print(f"Trades executed:      {len(book.trades):,}")
    print(f"Total time:           {total_time:.3f}s")
    print(f"Throughput:           {num_orders / total_time:,.0f} orders/sec")
    print(f"Latency p50:          {latencies[len(latencies)//2]:.4f} ms")
    print(f"Latency p99:          {latencies[int(len(latencies)*0.99)]:.4f} ms")
    print(f"Latency max:          {max(latencies):.4f} ms")
    print(f"\nPaste these numbers into your README's performance section.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run_load_test(args.orders, args.seed)
