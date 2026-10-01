const assert = require("node:assert/strict");

const endpoint = process.env.CDP_ENDPOINT || "http://127.0.0.1:9223";
const dashboardUrl = process.env.DASHBOARD_URL || "http://127.0.0.1:8766/docs/index.html";

async function connect() {
  const pages = await (await fetch(`${endpoint}/json/list`)).json();
  const page = pages.find((item) => item.type === "page");
  if (!page) throw new Error("No Chrome page target found");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  });
  return {
    close: () => socket.close(),
    send(method, params = {}) {
      const id = nextId++;
      socket.send(JSON.stringify({id, method, params}));
      return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
    },
  };
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || "Browser evaluation failed");
  }
  return result.result.value;
}

async function waitFor(client, expression, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for: ${expression}`);
}

async function main() {
  const client = await connect();
  try {
    await evaluate(client, "sessionStorage.setItem('cc_auth','1')");
    await client.send("Page.navigate", {url: dashboardUrl});
    await waitFor(client, "document.readyState === 'complete'");
    await waitFor(client, "typeof ABS_DATA !== 'undefined' && typeof echarts !== 'undefined'");
    await waitFor(client, "document.querySelectorAll('.fund-link').length > 0");

    const state = await evaluate(client, `(async () => {
      const appVisible = getComputedStyle(document.getElementById('app')).display !== 'none';
      const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
      switchTab('excess');
      const excessActive = DATA === EXCESS_DATA;
      switchTab('excess_dd');
      const drawdownActive = DATA === EXCESS_DD_DATA;
      switchTab('abs');
      const first = ABS_DATA.funds[0];
      showProductDetail(first.company, first.strategy);
      await new Promise((resolve) => setTimeout(resolve, 250));
      const modalOpen = document.getElementById('productModal').classList.contains('show');
      const rangeStart = document.getElementById('rangeStart');
      const rangeEnd = document.getElementById('rangeEnd');
      rangeStart.value = rangeEnd.value;
      updateProductMetrics();
      const singlePointUnavailable = document.getElementById('modalMetrics').textContent.includes('—');
      const chartsReady = Boolean(productChart1 && productChart2 && cS && cG && cF);
      closeProductModal();
      return {
        appVisible,
        tabCount: tabButtons.length,
        excessActive,
        drawdownActive,
        modalOpen,
        singlePointUnavailable,
        chartsReady,
        fundCount: ABS_DATA.funds.length,
      };
    })()`);

    assert.equal(state.appVisible, true);
    assert.equal(state.tabCount, 3);
    assert.equal(state.excessActive, true);
    assert.equal(state.drawdownActive, true);
    assert.equal(state.modalOpen, true);
    assert.equal(state.singlePointUnavailable, true);
    assert.equal(state.chartsReady, true);
    assert.equal(state.fundCount, 397);
    console.log(JSON.stringify(state));
  } finally {
    client.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
