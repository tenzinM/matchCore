# matchCore
A limit order book matching engine with price-time priority — the same core
algorithm real exchanges use to match buy and sell orders.

Single-symbol, in-memory, dependency-free matching core, wrapped in a FastAPI
service with a live WebSocket feed and a simple order book visualizer.


## How matching works

- **Price-time priority**: the best-priced order matches first; among orders at
  the same price, the earliest one matches first.
- **Trades execute at the resting order's price** — the order already sitting in
  the book — never at the incoming order's price. This mirrors real exchange
  behavior and prevents incoming orders from getting a price advantage.
- **Lazy deletion for cancellations**: since Python's `heapq` doesn't support
  O(log n) removal from the middle of a heap, a cancelled order is marked
  inactive and skipped when it's eventually popped — O(1) cancellation at the
  cost of some wasted heap space, which is a standard, well-understood tradeoff.

## Architecture

┌──────────────────┐   WebSocket (live book + trades)      ┌──────────────────┐
│  Frontend          │◀────────────────────────────────── │  FastAPI backend  │
│  (vanilla JS)      │────────────────────────────────-──▶│  + OrderBook core │
│                    │   REST: submit / cancel / snapshot │                   |
└──────────────────┘                                       └──────────────────┘

## Project structure

matchcore/
├── backend/
│   ├── app/
│   │   ├── order_book.py     # the matching engine core
│   │   ├── main.py            # FastAPI routes + WebSocket
│   │   ├── broadcaster.py     # WebSocket connection manager
│   │   └── models.py          # Pydantic schemas
│   ├── tests/
│   │   ├── test_order_book.py # example-based unit tests
│   │   └── test_invariants.py # Hypothesis property-based tests
│   ├── load_test/
│   │   └── load_test.py       # throughput/latency benchmark
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── app.js                 # WebSocket client + order submission
│   └── style.css
├── docker-compose.yml
