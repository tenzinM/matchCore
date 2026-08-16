from pydantic import BaseModel, Field
from .order_book import Side


class SubmitOrderRequest(BaseModel):
    order_id: str = Field(..., description="Client-supplied unique order ID")
    side: Side
    price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


class TradeResponse(BaseModel):
    trade_id: int
    price: float
    quantity: float
    buy_order_id: str
    sell_order_id: str
    timestamp: float


class SubmitOrderResponse(BaseModel):
    order_id: str
    trades: list[TradeResponse]
    resting: bool  # True if any quantity remains on the book after matching


class CancelResponse(BaseModel):
    order_id: str
    cancelled: bool


class PriceLevel(BaseModel):
    price: float
    quantity: float


class SnapshotResponse(BaseModel):
    symbol: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]
