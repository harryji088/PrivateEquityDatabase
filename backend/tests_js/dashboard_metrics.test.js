const test = require("node:test");
const assert = require("node:assert/strict");
const metrics = require("../dashboard_metrics.js");

test("uses geometric interval excess and drawdown", () => {
  const result = metrics.calculate(
    [1, 1.1], [0.2, 0.1], [0.1], "2026-01-01", "2026-01-08",
  );
  assert.ok(Math.abs(result.excessReturn - (1.1 / 1.2 - 1)) < 1e-12);
  assert.deepEqual(
    metrics.excessDrawdownSeries([0.2, 0.1], ["2026-01-01", "2026-01-08"]),
    [["01-01", 0], ["01-08", (1.1 / 1.2 - 1) * 100]],
  );
});

test("single-point ranges and insufficient volatility are unavailable", () => {
  const result = metrics.calculate([1.05], [0.02], [], "2026-01-08", "2026-01-08");
  assert.equal(result.totalReturn, null);
  assert.equal(result.annualizedReturn, null);
  assert.equal(result.excessReturn, null);
  assert.equal(result.annualizedVolatility, null);
  assert.equal(result.sharpe, null);
  assert.equal(result.winRate, null);
  assert.equal(result.weekCount, 0);
});

test("ignores null and non-finite weekly returns", () => {
  const result = metrics.calculate(
    [1, 1.01, 1.03], [0, 0.005, 0.01], [null, 0.01, Number.NaN, -0.005],
    "2026-01-01", "2026-01-15",
  );
  assert.equal(result.weekCount, 2);
  assert.equal(result.winRate, 0.5);
  assert.ok(result.annualizedVolatility > 0);
});
