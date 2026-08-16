const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

const statusEl = document.getElementById("status");
const symbolEl = document.getElementById("symbol");
const bidsBody = document.querySelector("#bids-table tbody");
const asksBody = document.querySelector("#asks-table tbody");
const tradesBody = document.querySelector("#trades-table tbody");
const submitResult = document.getElementById("submit-result");

function renderBook(data) {
  symbolEl.textContent = data.symbol;

  asksBody.innerHTML = "";
  // Show best ask closest to the spread, i.e. reverse so lowest ask is at bottom near bids
  [...data.asks].reverse().forEach((level) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${level.price.toFixed(2)}</td><td>${level.quantity.toFixed(2)}</td>`;
    asksBody.appendChild(tr);
  });

  bidsBody.innerHTML = "";
  data.bids.forEach((level) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${level.price.toFixed(2)}</td><td>${level.quantity.toFixed(2)}</td>`;
    bidsBody.appendChild(tr);
  });
}

function renderTrades(trades) {
  trades.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${t.price.toFixed(2)}</td><td>${t.quantity.toFixed(2)}</td><td>${t.buy_order_id}</td><td>${t.sell_order_id}</td>`;
    tradesBody.prepend(tr);
  });
  // Keep the tape from growing unbounded
  while (tradesBody.children.length > 50) {
    tradesBody.removeChild(tradesBody.lastChild);
  }
}

function connect() {
  const ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    statusEl.textContent = "connected";
    statusEl.className = "status connected";
  };

  ws.onclose = () => {
    statusEl.textContent = "disconnected — retrying…";
    statusEl.className = "status disconnected";
    setTimeout(connect, 1500);
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "book") renderBook(msg.data);
    if (msg.type === "trades") renderTrades(msg.data);
  };
}

connect();

document.getElementById("order-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const order = {
    order_id: document.getElementById("order-id").value,
    side: document.getElementById("side").value,
    price: parseFloat(document.getElementById("price").value),
    quantity: parseFloat(document.getElementById("quantity").value),
  };
  await submitOrder(order);
});

document.getElementById("random-order-btn").addEventListener("click", async () => {
  const order = {
    order_id: "auto-" + Math.random().toString(36).slice(2, 8),
    side: Math.random() > 0.5 ? "BUY" : "SELL",
    price: +(100 + (Math.random() - 0.5) * 4).toFixed(2),
    quantity: +(Math.random() * 20 + 1).toFixed(2),
  };
  await submitOrder(order);
});

async function submitOrder(order) {
  try {
    const res = await fetch(`${API_BASE}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Order failed");
    submitResult.textContent = `Order ${data.order_id}: ${data.trades.length} trade(s), resting=${data.resting}`;
  } catch (err) {
    submitResult.textContent = `Error: ${err.message}`;
  }
}
