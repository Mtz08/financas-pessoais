from django.shortcuts import render

from apps.lancamentos.services.recorrencias import gerar_todas
from apps.lancamentos.services.saldos import saldos_das_contas
from apps.orcamentos.services import alertas_do_mes
from core import dates
from core.money import centavos_para_reais

from .services import contas_a_vencer, evolucao_mensal, gastos_por_categoria, resumo_do_mes

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def index(request):
    gerar_todas()  # materializa as recorrências do mês (idempotente)
    hoje = dates.hoje()
    mes = dates.parse_mes(request.GET.get("mes"), hoje)
    saldos = saldos_das_contas()
    gastos = gastos_por_categoria(mes)
    evolucao = evolucao_mensal(mes)
    return render(request, "dashboard/index.html", {
        "mes": mes,
        "mes_anterior": dates.somar_meses(mes, -1),
        "mes_seguinte": dates.somar_meses(mes, 1),
        "saldo_disponivel": sum(s for c, s in saldos if not c.eh_cartao),
        "saldos": saldos,
        "resumo": resumo_do_mes(mes),
        "gastos": gastos,
        "evolucao": evolucao,
        "a_vencer": contas_a_vencer(hoje=hoje),
        "alertas": alertas_do_mes(mes),
        "hoje": hoje,
        # Dados dos gráficos: vão para o template via json_script (sem script inline).
        "grafico_categorias": {
            "rotulos": [g["grupo"] for g in gastos],
            "valores": [g["total"] / 100 for g in gastos],
            "textos": [centavos_para_reais(g["total"]) for g in gastos],
        },
        "grafico_evolucao": {
            "rotulos": [f"{MESES[e['mes'].month - 1]}/{e['mes']:%y}" for e in evolucao],
            "receitas": [e["receitas"] / 100 for e in evolucao],
            "despesas": [e["despesas"] / 100 for e in evolucao],
        },
    })
