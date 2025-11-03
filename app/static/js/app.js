document.addEventListener("DOMContentLoaded", async () => {
  // Инициализация графика
  const el = document.getElementById("chart");
  if (!el) return;
  try {
    const resp = await fetch("/chart-data");
    const data = await resp.json();
    const ctx = el.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: data,
      options: {
        responsive: true,
        maintainAspectRatio: false
      }
    });
    el.parentElement.style.height = "320px";
  } catch (e) {
    console.warn("Chart init error", e);
  }
});
