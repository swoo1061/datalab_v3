document.addEventListener("DOMContentLoaded", () => {
  const data = window.LLM_USAGE_DATA;
  if (!data) return;

  // =========================
  // 📈 일자별 비용
  // =========================
  const dailyCtx = document.getElementById("dailyCostChart");
  if (dailyCtx) {
    new Chart(dailyCtx, {
      type: "line",
      data: {
        labels: data.dailyLabels,
        datasets: [{
          label: "비용 (원)",
          data: data.dailyCosts,
          borderWidth: 2,
          tension: 0.3,
          fill: false
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            ticks: {
              callback: value => value.toLocaleString() + "원"
            }
          }
        }
      }
    });
  }

  // =========================
  // 📊 모델별 비용
  // =========================
  const modelCtx = document.getElementById("modelCostChart");
  if (modelCtx) {
    new Chart(modelCtx, {
      type: "bar",
      data: {
        labels: data.modelLabels,
        datasets: [{
          label: "비용 (원)",
          data: data.modelCosts
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            ticks: {
              callback: value => value.toLocaleString() + "원"
            }
          }
        }
      }
    });
  }
});