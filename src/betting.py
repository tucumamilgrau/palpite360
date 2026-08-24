"""Classificação de mercados por nível de confiança e sugestão de combinações.

Importante: isto NÃO é uma garantia de acerto. São probabilidades estatísticas
com base no desempenho recente das equipes. O usuário decide se, como e se
aposta — este projeto não processa apostas nem dinheiro.

Fora do escopo por falta de dado gratuito confiável: mercados de jogadores,
impacto de escalação/desfalques confirmados, e cash-out (que depende da odd
ao vivo da casa de apostas, algo que não temos acesso).
"""
from __future__ import annotations

from . import poisson_model

TIER_GREEN = "🟢 Mais segura"
TIER_YELLOW = "🟡 Boa para valor"
TIER_RED = "🔴 Arriscada"

GREEN_MIN = 75.0
YELLOW_MIN = 55.0
RED_MIN = 35.0


def tier(prob_pct: float) -> str | None:
    if prob_pct >= GREEN_MIN:
        return TIER_GREEN
    if prob_pct >= YELLOW_MIN:
        return TIER_YELLOW
    if prob_pct >= RED_MIN:
        return TIER_RED
    return None  # abaixo de 35%: não entra na lista de sugestões


def _add(markets: list, categoria: str, nome: str, prob: float | None):
    if prob is None:
        return
    t = tier(prob)
    if t is None:
        return
    markets.append({"categoria": categoria, "mercado": nome, "probabilidade_pct": round(prob, 1), "tier": t})


def build_markets(team_a: str, team_b: str, report_a_home: dict, report_b_away: dict, league_avg: dict) -> dict:
    """Monta a lista de mercados avaliados para o confronto, já com o
    modelo de Poisson para gols e (quando a liga tiver o dado) escanteios
    e cartões."""
    gols = poisson_model.predict(report_a_home, report_b_away, league_avg)
    dc = poisson_model.double_chance_and_dnb(gols["vitoria_casa_pct"], gols["empate_pct"], gols["vitoria_fora_pct"])

    corners = poisson_model.predict_metric(
        report_a_home.get("escanteios_media"), report_b_away.get("escanteios_sofridos_media"),
        report_b_away.get("escanteios_media"), report_a_home.get("escanteios_sofridos_media"),
        league_avg.get("escanteios_casa_media"), league_avg.get("escanteios_fora_media"),
        max_count=16, over_lines=(6.5, 7.5, 8.5, 9.5, 10.5, 11.5),
    )

    # Cartões não têm um "adversário que reduz cartão do rival" claro como
    # gols/escanteios têm defesa — usamos a média da liga no lugar da defesa,
    # de forma que o resultado reflita principalmente a média de cada equipe.
    base_home = league_avg.get("cartoes_casa_media")
    base_away = league_avg.get("cartoes_fora_media")
    cards = poisson_model.predict_metric(
        report_a_home.get("cartoes_media"), base_away,
        report_b_away.get("cartoes_media"), base_home,
        base_home, base_away,
        max_count=10, over_lines=(1.5, 2.5, 3.5, 4.5, 5.5),
    )

    markets: list[dict] = []

    # Resultado / dupla chance / empate anula aposta
    result_options = [
        (f"Vitória {team_a}", gols["vitoria_casa_pct"]),
        ("Empate", gols["empate_pct"]),
        (f"Vitória {team_b}", gols["vitoria_fora_pct"]),
    ]
    best_result = max(result_options, key=lambda x: x[1])
    _add(markets, "Resultado", best_result[0], best_result[1])
    _add(markets, "Dupla chance", f"{team_a} ou empate (1X)", dc["dupla_chance_1x_pct"])
    _add(markets, "Dupla chance", f"Empate ou {team_b} (X2)", dc["dupla_chance_x2_pct"])
    _add(markets, "Dupla chance", f"{team_a} ou {team_b} (12)", dc["dupla_chance_12_pct"])
    if dc["empate_anula_casa_pct"] is not None:
        _add(markets, "Empate anula aposta", f"{team_a} (DNB)", dc["empate_anula_casa_pct"])
        _add(markets, "Empate anula aposta", f"{team_b} (DNB)", dc["empate_anula_fora_pct"])

    # Gols / BTTS
    for line, prob in gols["over_pct"].items():
        _add(markets, "Gols", f"Mais de {line} gols", prob)
        _add(markets, "Gols", f"Menos de {line} gols", 100 - prob)
    _add(markets, "Ambas marcam", "Sim", gols["ambas_marcam_pct"])
    _add(markets, "Ambas marcam", "Não", 100 - gols["ambas_marcam_pct"])

    # Escanteios
    if corners is not None:
        for line, prob in corners["over_pct"].items():
            _add(markets, "Escanteios", f"Mais de {line} escanteios", prob)
        favor_a = corners["vitoria_casa_pct"]
        favor_b = corners["vitoria_fora_pct"]
        if favor_a >= favor_b:
            _add(markets, "Escanteios", f"{team_a} tem mais escanteios", favor_a)
        else:
            _add(markets, "Escanteios", f"{team_b} tem mais escanteios", favor_b)

    # Cartões
    if cards is not None:
        for line, prob in cards["over_pct"].items():
            _add(markets, "Cartões", f"Mais de {line} cartões", prob)

    markets.sort(key=lambda m: m["probabilidade_pct"], reverse=True)
    return {"mercados": markets, "gols": gols, "escanteios": corners, "cartoes": cards}


def best_combination(markets: list[dict], n: int = 3) -> dict | None:
    """Combina as `n` melhores dicas de categorias diferentes (para reduzir
    correlação óbvia, ex.: não combina 'mais de 1.5 gols' com 'mais de 2.5 gols').
    A probabilidade combinada assume independência — é uma aproximação
    otimista: mercados correlacionados tendem a ter chance conjunta menor."""
    chosen = []
    used_categories = set()
    for m in markets:
        if m["categoria"] in used_categories:
            continue
        chosen.append(m)
        used_categories.add(m["categoria"])
        if len(chosen) == n:
            break
    if len(chosen) < 2:
        return None
    combined_prob = 1.0
    for m in chosen:
        combined_prob *= m["probabilidade_pct"] / 100
    return {
        "pernas": chosen,
        "probabilidade_combinada_pct": round(combined_prob * 100, 1),
    }
