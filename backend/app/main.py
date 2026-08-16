import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .order_book import OrderBook
from .broadcaster import Broadcaster
from .models import (
    SubmitOrderRequest,
    SubmitOrderResponse,
    TradeResponse,
    CancelResponse,
    SnapshotResponse,
)

SYMBOL = "MOCK"

app = FastAPI(title="MatchCore", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

book = OrderBook(symbol=SYMBOL)
broadcaster = Broadcaster()
# Single lock serializes access to the book, avoiding race conditions between
# concurrent order submissions - simple, obviously correct, and fast enough
# since matching itself is CPU-bound and sub-millisecond per order.
book_lock = asyncio.Lock()


@app.get("/health")
def health():
    return {"status": "ok", "symbol": SYMBOL}


@app.post("/orders", response_model=SubmitOrderResponse)
async def submit_order(req: SubmitOrderRequest):
    async with book_lock:
        try:
            trades = book.submit_limit_order(req.order_id, req.side, req.price, req.quantity)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        snapshot = book.snapshot()

    trade_responses = [TradeResponse(**vars(t)) for t in trades]
    resting = book.is_resting(req.order_id)

    await broadcaster.broadcast({"type": "book", "data": snapshot})
    if trades:
        await broadcaster.broadcast({"type": "trades", "data": [t.model_dump() for t in trade_responses]})

    return SubmitOrderResponse(order_id=req.order_id, trades=trade_responses, resting=resting)


@app.delete("/orders/{order_id}", response_model=CancelResponse)
async def cancel_order(order_id: str):
    async with book_lock:
        cancelled = book.cancel_order(order_id)
        snapshot = book.snapshot()

    if cancelled:
        await broadcaster.broadcast({"type": "book", "data": snapshot})

    return CancelResponse(order_id=order_id, cancelled=cancelled)


@app.get("/book", response_model=SnapshotResponse)
async def get_snapshot(depth: int = 10):
    async with book_lock:
        return book.snapshot(depth=depth)


@app.get("/trades", response_model=list[TradeResponse])
async def get_recent_trades(limit: int = 50):
    async with book_lock:
        recent = book.trades[-limit:]
    return [TradeResponse(**vars(t)) for t in recent]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await broadcaster.connect(ws)
    try:
        # Send current state immediately on connect
        async with book_lock:
            snapshot = book.snapshot()
        await ws.send_json({"type": "book", "data": snapshot})
        while True:
            await ws.receive_text()  # keep connection alive; client doesn't need to send anything meaningful
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)
