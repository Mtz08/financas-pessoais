// Gráficos do dashboard. Dados vêm de <script type="application/json"> (json_script).
document.addEventListener("DOMContentLoaded", () => {
  if (!window.Chart) return;

  const css = getComputedStyle(document.documentElement);
  const cor = (nome) => css.getPropertyValue(nome).trim();
  const ler = (id) => {
    const elemento = document.getElementById(id);
    return elemento ? JSON.parse(elemento.textContent) : null;
  };
  const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const reaisCurto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

  Chart.defaults.font.family = '"Inter", "Segoe UI", system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cor("--texto-mudo");
  Chart.defaults.borderColor = cor("--grade");

  const barra = { borderRadius: 4, borderSkipped: "start", maxBarThickness: 22 };

  // Gastos por categoria: barras horizontais, uma cor (série única = sem legenda).
  const categorias = ler("dados-categorias");
  const canvasCategorias = document.getElementById("grafico-categorias");
  if (categorias && canvasCategorias) {
    canvasCategorias.parentElement.style.height = `${Math.max(160, categorias.rotulos.length * 34 + 40)}px`;
    new Chart(canvasCategorias, {
      type: "bar",
      data: {
        labels: categorias.rotulos,
        datasets: [{ label: "Gasto", data: categorias.valores, backgroundColor: cor("--serie-1"), ...barra }],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => categorias.textos[ctx.dataIndex] } },
        },
        scales: {
          x: { beginAtZero: true, ticks: { callback: (v) => `R$ ${reaisCurto.format(v)}` } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  // Receitas x despesas: barras agrupadas, 2 séries, um único eixo.
  const evolucao = ler("dados-evolucao");
  const canvasEvolucao = document.getElementById("grafico-evolucao");
  if (evolucao && canvasEvolucao) {
    new Chart(canvasEvolucao, {
      type: "bar",
      data: {
        labels: evolucao.rotulos,
        datasets: [
          { label: "Receitas", data: evolucao.receitas, backgroundColor: cor("--serie-1"), ...barra },
          { label: "Despesas", data: evolucao.despesas, backgroundColor: cor("--serie-2"), ...barra },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", align: "start", labels: { boxWidth: 12, color: cor("--texto-mudo"), usePointStyle: true, pointStyle: "rectRounded" } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${reais.format(ctx.parsed.y)}` } },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: (v) => `R$ ${reaisCurto.format(v)}` } },
        },
      },
    });
  }
});
