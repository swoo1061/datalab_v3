document.addEventListener("DOMContentLoaded", () => {
  const data = window.LLM_USAGE_DATA;
  if (!data || typeof Chart === "undefined") return;

  const formatNumber = (value) => Number(value || 0).toLocaleString();
  const rootStyle = getComputedStyle(document.documentElement);
  const getVar = (name, fallback) =>
    rootStyle.getPropertyValue(name).trim() || fallback;

  const palette = [
    getVar("--data-1", "#0ea5a4"),
    getVar("--data-2", "#38bdf8"),
    getVar("--data-3", "#f59e0b"),
    getVar("--data-4", "#22c55e"),
    getVar("--data-5", "#f97316"),
  ];

  Chart.defaults.color = getVar("--muted", "#5b6675");
  Chart.defaults.font.family =
    "'Space Grotesk', 'Pretendard', system-ui, sans-serif";
  Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15, 23, 42, 0.9)";
  Chart.defaults.plugins.tooltip.titleColor = "#fff";
  Chart.defaults.plugins.tooltip.bodyColor = "#e2e8f0";
  Chart.defaults.plugins.tooltip.borderColor = "rgba(255,255,255,0.12)";
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.tooltip.padding = 10;

  const makeLineGradient = (ctx, color) => {
    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, `${color}55`);
    gradient.addColorStop(1, `${color}05`);
    return gradient;
  };

  const makeBarGradient = (ctx, color) => {
    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, `${color}cc`);
    gradient.addColorStop(1, `${color}55`);
    return gradient;
  };

  const axisOptions = {
    grid: {
      color: "rgba(15, 23, 42, 0.08)",
      drawBorder: false,
    },
    ticks: {
      padding: 8,
    },
  };

  // =========================
  // 일자별 토큰
  // =========================
  const dailyTokenEl = document.getElementById("dailyTokenChart");
  if (dailyTokenEl && data.dailyLabels) {
    const ctx = dailyTokenEl.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: data.dailyLabels,
        datasets: [
          {
            label: "전체",
            data: data.dailyTotalTokens || [],
            borderColor: palette[0],
            backgroundColor: makeLineGradient(ctx, palette[0]),
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
          {
            label: "Input",
            data: data.dailyInputTokens || [],
            borderColor: palette[1],
            backgroundColor: makeLineGradient(ctx, palette[1]),
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
          {
            label: "Output",
            data: data.dailyOutputTokens || [],
            borderColor: palette[2],
            backgroundColor: makeLineGradient(ctx, palette[2]),
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: {
            position: "top",
            labels: { usePointStyle: true, padding: 16 },
          },
        },
        scales: {
          x: axisOptions,
          y: {
            ...axisOptions,
            ticks: {
              ...axisOptions.ticks,
              callback: (value) => formatNumber(value),
            },
          },
        },
      },
    });
  }

  // =========================
  // 일자별 비용
  // =========================
  const dailyCostEl = document.getElementById("dailyCostChart");
  if (dailyCostEl && data.dailyLabels) {
    const ctx = dailyCostEl.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: data.dailyLabels,
        datasets: [
          {
            label: "비용 (원)",
            data: data.dailyCosts || [],
            borderColor: palette[3],
            backgroundColor: makeLineGradient(ctx, palette[3]),
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: axisOptions,
          y: {
            ...axisOptions,
            ticks: {
              ...axisOptions.ticks,
              callback: (value) => formatNumber(value) + "원",
            },
          },
        },
      },
    });
  }

  const makeBarChart = (canvas, labels, values, color, formatter) => {
    if (!canvas || !labels) return;
    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            data: values || [],
            backgroundColor: makeBarGradient(ctx, color),
            borderColor: color,
            borderWidth: 1,
            borderRadius: 10,
            hoverBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: {
            ...axisOptions,
            grid: { display: false },
          },
          y: {
            ...axisOptions,
            ticks: {
              ...axisOptions.ticks,
              callback: formatter,
            },
          },
        },
      },
    });
  };

  // =========================
  // 모델별 토큰/비용
  // =========================
  makeBarChart(
    document.getElementById("modelTokenChart"),
    data.modelLabels,
    data.modelTokens,
    palette[1],
    (value) => formatNumber(value)
  );

  makeBarChart(
    document.getElementById("modelCostChart"),
    data.modelLabels,
    data.modelCosts,
    palette[4],
    (value) => formatNumber(value) + "원"
  );

  // =========================
  // 유저별 토큰/비용
  // =========================
  makeBarChart(
    document.getElementById("userTokenChart"),
    data.userLabels,
    data.userTokens,
    palette[2],
    (value) => formatNumber(value)
  );

  makeBarChart(
    document.getElementById("userCostChart"),
    data.userLabels,
    data.userCosts,
    palette[0],
    (value) => formatNumber(value) + "원"
  );
});
