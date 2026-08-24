"""Indicadores históricos por equipe (seções 5-9 e 12 do escopo)."""
from __future__ import annotations

import numpy as np
import pandas as pd

RECENCY_DECAY = 0.9  # peso do jogo mais antigo cai ~10% a cada jogo mais recente


def team_matches(df: pd.DataFrame, team: str, venue: str = "all", last_n: int | None = None) -> pd.DataFrame:
    """Jogos de `team`, mais recentes primeiro. venue: 'all' | 'home' | 'away'."""
    if venue == "home":
        sub = df[df["home_team"] == team]
    elif venue == "away":
        sub = df[df["away_team"] == team]
    else:
        sub = df[(df["home_team"] == team) | (df["away_team"] == team)]
    sub = sub.sort_values("date", ascending=False)
    if last_n:
        sub = sub.head(last_n)
    return sub


def _perspective(row: pd.Series, team: str) -> dict:
    """Normaliza uma linha de jogo para o ponto de vista de `team`."""
    is_home = row["home_team"] == team
    gf = row["home_goals"] if is_home else row["away_goals"]
    ga = row["away_goals"] if is_home else row["home_goals"]
    res = row["result"]
    if res == "H":
        outcome = "V" if is_home else "D"
    elif res == "A":
        outcome = "D" if is_home else "V"
    else:
        outcome = "E"
    return {
        "date": row["date"],
        "is_home": is_home,
        "gf": gf,
        "ga": ga,
        "outcome": outcome,
        "shots_for": row["home_shots"] if is_home else row["away_shots"],
        "shots_against": row["away_shots"] if is_home else row["home_shots"],
        "shots_target_for": row["home_shots_target"] if is_home else row["away_shots_target"],
        "corners_for": row["home_corners"] if is_home else row["away_corners"],
        "corners_against": row["away_corners"] if is_home else row["home_corners"],
        "cards_for": np.nansum([row["home_yellow"] if is_home else row["away_yellow"],
                                 row["home_red"] if is_home else row["away_red"]]),
        "ht_gf": row["home_ht_goals"] if is_home else row["away_ht_goals"],
        "ht_ga": row["away_ht_goals"] if is_home else row["home_ht_goals"],
    }


def team_report(df: pd.DataFrame, team: str, last_n: int = 10, venue: str = "all") -> dict:
    """Relatório estatístico de `team` nos últimos `last_n` jogos (ou todos, se None)."""
    matches = team_matches(df, team, venue=venue, last_n=last_n)
    n = len(matches)
    if n == 0:
        return {"team": team, "n_games": 0}

    persp = [_perspective(r, team) for _, r in matches.iterrows()]
    weights = np.array([RECENCY_DECAY ** i for i in range(n)])  # jogo 0 = mais recente
    w_sum = weights.sum()

    outcomes = [p["outcome"] for p in persp]
    wins = outcomes.count("V")
    draws = outcomes.count("E")
    losses = outcomes.count("D")
    points = wins * 3 + draws

    gf = np.array([p["gf"] for p in persp], dtype=float)
    ga = np.array([p["ga"] for p in persp], dtype=float)
    total_goals = gf + ga

    def pct(mask):
        return round(100 * np.average(mask.astype(float), weights=weights), 1)

    def safe_avg(values):
        arr = np.array(values, dtype=float)
        mask = ~np.isnan(arr)
        if not mask.any():
            return None
        return round(np.average(arr[mask], weights=weights[mask]), 2)

    report = {
        "team": team,
        "n_games": n,
        "venue": venue,
        "vitorias": wins,
        "empates": draws,
        "derrotas": losses,
        "pontos": points,
        "aproveitamento_pct": round(100 * points / (n * 3), 1),
        "sequencia_recente": "".join(outcomes[:5]),
        "gols_marcados_media": safe_avg(gf),
        "gols_sofridos_media": safe_avg(ga),
        "saldo_medio": round(safe_avg(gf) - safe_avg(ga), 2),
        "jogos_sem_sofrer_pct": pct(ga == 0),
        "jogos_sem_marcar_pct": pct(gf == 0),
        "over_05_pct": pct(total_goals > 0.5),
        "over_15_pct": pct(total_goals > 1.5),
        "over_25_pct": pct(total_goals > 2.5),
        "over_35_pct": pct(total_goals > 3.5),
        "ambas_marcam_pct": pct((gf > 0) & (ga > 0)),
    }

    ht_gf = [p["ht_gf"] for p in persp]
    if any(v is not None and not (isinstance(v, float) and np.isnan(v)) for v in ht_gf):
        ht_total = np.array([p["ht_gf"] + p["ht_ga"] for p in persp], dtype=float)
        mask = ~np.isnan(ht_total)
        if mask.any():
            report["gol_1_tempo_pct"] = round(100 * np.average((ht_total[mask] > 0.5).astype(float), weights=weights[mask]), 1)

    shots_for = [p["shots_for"] for p in persp]
    if safe_avg(shots_for) is not None:
        report["finalizacoes_media"] = safe_avg(shots_for)
        report["finalizacoes_no_alvo_media"] = safe_avg([p["shots_target_for"] for p in persp])
        report["escanteios_media"] = safe_avg([p["corners_for"] for p in persp])
        report["escanteios_sofridos_media"] = safe_avg([p["corners_against"] for p in persp])
        report["cartoes_media"] = safe_avg([p["cards_for"] for p in persp])

    return report


def league_averages(df: pd.DataFrame) -> dict:
    """Médias da liga usadas como referência para forças de ataque/defesa (Poisson)."""
    if df.empty:
        return {}
    has_cards = df["home_yellow"].notna().any()
    home_cards = (df["home_yellow"].fillna(0) + df["home_red"].fillna(0)) if has_cards else None
    away_cards = (df["away_yellow"].fillna(0) + df["away_red"].fillna(0)) if has_cards else None
    return {
        "gols_casa_media": df["home_goals"].mean(),
        "gols_fora_media": df["away_goals"].mean(),
        "escanteios_casa_media": df["home_corners"].mean() if df["home_corners"].notna().any() else None,
        "escanteios_fora_media": df["away_corners"].mean() if df["away_corners"].notna().any() else None,
        "cartoes_casa_media": home_cards.mean() if has_cards else None,
        "cartoes_fora_media": away_cards.mean() if has_cards else None,
    }
