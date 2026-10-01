const DashboardMetrics = (() => {
  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function geometricReturn(start, end) {
    if (!isFiniteNumber(start) || !isFiniteNumber(end) || start <= 0 || end <= 0) {
      return null;
    }
    return end / start - 1;
  }

  function calculate(navs, cumulativeExcess, weeklyReturns, startDate, endDate) {
    const validNavs = navs.filter(isFiniteNumber);
    const validExcess = cumulativeExcess.filter(isFiniteNumber);
    const returns = weeklyReturns.filter(isFiniteNumber);
    const elapsedDays = (
      new Date(`${endDate}T00:00:00Z`) - new Date(`${startDate}T00:00:00Z`)
    ) / 86400000;

    const totalReturn = validNavs.length >= 2
      ? geometricReturn(validNavs[0], validNavs[validNavs.length - 1])
      : null;
    const excessReturn = validExcess.length >= 2
      ? geometricReturn(1 + validExcess[0], 1 + validExcess[validExcess.length - 1])
      : null;
    const annualizedReturn = totalReturn !== null && elapsedDays > 0
      ? Math.pow(1 + totalReturn, 365.25 / elapsedDays) - 1
      : null;

    let annualizedVolatility = null;
    if (returns.length >= 2) {
      const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
      const variance = returns.reduce(
        (sum, value) => sum + Math.pow(value - mean, 2), 0,
      ) / returns.length;
      annualizedVolatility = Math.sqrt(Math.max(0, variance) * 52);
    }
    const sharpe = (
      annualizedReturn !== null
      && annualizedVolatility !== null
      && annualizedVolatility > 0
    ) ? annualizedReturn / annualizedVolatility : null;

    let peak = -Infinity;
    let maxDrawdown = null;
    validNavs.forEach((nav) => {
      peak = Math.max(peak, nav);
      const drawdown = nav / peak - 1;
      maxDrawdown = maxDrawdown === null ? drawdown : Math.min(maxDrawdown, drawdown);
    });

    return {
      totalReturn,
      annualizedReturn,
      excessReturn,
      annualizedVolatility,
      sharpe,
      maxDrawdown,
      winRate: returns.length
        ? returns.filter((value) => value > 0).length / returns.length
        : null,
      weekCount: returns.length,
    };
  }

  function excessDrawdownSeries(cumulativeExcess, dates) {
    let peakNav = -Infinity;
    const result = [];
    cumulativeExcess.forEach((value, index) => {
      if (!isFiniteNumber(value) || 1 + value <= 0) return;
      const nav = 1 + value;
      peakNav = Math.max(peakNav, nav);
      result.push([dates[index].slice(5), (nav / peakNav - 1) * 100]);
    });
    return result;
  }

  return {calculate, excessDrawdownSeries, geometricReturn, isFiniteNumber};
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DashboardMetrics;
}
