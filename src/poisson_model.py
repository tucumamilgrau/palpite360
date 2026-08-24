"""Modelo estatístico de gols esperados via distribuição de Poisson
(seção 20 do escopo, versão simplificada — sem Dixon-Coles/ML por enquanto).

Não é garantia de resultado: é uma estimativa probabilística baseada no
desempenho recente das duas equipes frente à média da liga.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

MAX_GOALS = 7


def expected_metric(attack_avg: float | None, defense_avg: float | None, league_base: float | None) -> float | None:
    """Valor esperado genérico (gols, escanteios ou cartões) via força
    relativa de ataque x defesa frente à média da liga."""
    if attack_avg is None or defense_avg is None or not league_base:
        return None
    attack = attack_avg / league_base
    defense = defense_avg / league_base
    return round(max(league_base * attack * defense, 0.05), 3)


def expected_goals(attack_report: dict, defense_report: dict, league_avg: dict, attack_side: str) -> float:
    league_base = league_avg.get("gols_casa_media" if attack_side == "home" else "gols_fora_media") or 1.3
    attack = attack_report.get("gols_marcados_media") or league_base
    defense = defense_report.get("gols_sofridos_media") or league_base
    return expected_metric(attack, defense, league_base)


def score_matrix(xg_home: float, xg_away: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    home_probs = poisson.pmf(np.arange(max_goals + 1), xg_home)
    away_probs = poisson.pmf(np.arange(max_goals + 1), xg_away)
    return np.outer(home_probs, away_probs)


def market_probabilities(matrix: np.ndarray, over_lines=(0.5, 1.5, 2.5, 3.5, 4.5)) -> dict:
    n = matrix.shape[0]
    idx = np.arange(n)
    home_win = matrix[np.greater.outer(idx, idx)].sum()
    draw = np.trace(matrix)
    away_win = matrix[np.less.outer(idx, idx)].sum()

    total_grid = idx[:, None] + idx[None, :]
    over = {line: matrix[total_grid > line].sum() for line in over_lines}

    btts = matrix[1:, 1:].sum()

    scorelines = [((i, j), matrix[i, j]) for i in range(n) for j in range(n)]
    scorelines.sort(key=lambda x: x[1], reverse=True)
    top_scorelines = [{"placar": f"{i}x{j}", "probabilidade": round(p * 100, 1)} for (i, j), p in scorelines[:5]]

    return {
        "vitoria_casa_pct": round(home_win * 100, 1),
        "empate_pct": round(draw * 100, 1),
        "vitoria_fora_pct": round(away_win * 100, 1),
        "over_pct": {line: round(v * 100, 1) for line, v in over.items()},
        "ambas_marcam_pct": round(btts * 100, 1),
        "placares_provaveis": top_scorelines,
    }


def predict(report_home: dict, report_away: dict, league_avg: dict) -> dict:
    """`report_home`/`report_away` devem vir de stats.team_report com o
    filtro de mando correto (venue='home' para o mandante, 'away' para o visitante)."""
    xg_home = expected_goals(report_home, report_away, league_avg, "home")
    xg_away = expected_goals(report_away, report_home, league_avg, "away")
    matrix = score_matrix(xg_home, xg_away)
    result = market_probabilities(matrix)
    result["xg_casa"] = xg_home
    result["xg_fora"] = xg_away
    return result


def predict_metric(
    attack_home_avg: float | None, defense_away_avg: float | None,
    attack_away_avg: float | None, defense_home_avg: float | None,
    league_base_home: float | None, league_base_away: float | None,
    max_count: int = MAX_GOALS, over_lines=(0.5, 1.5, 2.5, 3.5, 4.5),
) -> dict | None:
    """Versão genérica de `predict` para outras contagens de eventos por
    partida (escanteios, cartões), reaproveitando o mesmo modelo de Poisson."""
    x_home = expected_metric(attack_home_avg, defense_away_avg, league_base_home)
    x_away = expected_metric(attack_away_avg, defense_home_avg, league_base_away)
    if x_home is None or x_away is None:
        return None
    matrix = score_matrix(x_home, x_away, max_goals=max_count)
    result = market_probabilities(matrix, over_lines=over_lines)
    result["esperado_casa"] = x_home
    result["esperado_fora"] = x_away
    return result


def double_chance_and_dnb(vitoria_casa_pct: float, empate_pct: float, vitoria_fora_pct: float) -> dict:
    """Dupla chance e empate anula aposta (draw no bet), derivados do 1X2."""
    dnb_base = vitoria_casa_pct + vitoria_fora_pct
    return {
        "dupla_chance_1x_pct": round(vitoria_casa_pct + empate_pct, 1),
        "dupla_chance_x2_pct": round(empate_pct + vitoria_fora_pct, 1),
        "dupla_chance_12_pct": round(vitoria_casa_pct + vitoria_fora_pct, 1),
        "empate_anula_casa_pct": round(100 * vitoria_casa_pct / dnb_base, 1) if dnb_base else None,
        "empate_anula_fora_pct": round(100 * vitoria_fora_pct / dnb_base, 1) if dnb_base else None,
    }
