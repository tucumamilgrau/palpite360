"""Rating Elo simplificado (seção 14 do escopo).

Limitação importante: como só carregamos as últimas temporadas disponíveis
gratuitamente (não o histórico completo do clube), este Elo é relativo ao
período carregado, útil para comparar as duas equipes entre si, não como
rating absoluto e definitivo.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

K_FACTOR = 20
HOME_ADVANTAGE = 60
INITIAL_RATING = 1500


def compute_ratings(df: pd.DataFrame) -> dict:
    ratings = defaultdict(lambda: float(INITIAL_RATING))
    for _, row in df.sort_values("date").iterrows():
        home, away, result = row["home_team"], row["away_team"], row["result"]
        rh, ra = ratings[home], ratings[away]
        expected_home = 1 / (1 + 10 ** (-((rh + HOME_ADVANTAGE) - ra) / 400))
        if result == "H":
            score_home = 1.0
        elif result == "A":
            score_home = 0.0
        else:
            score_home = 0.5
        ratings[home] = rh + K_FACTOR * (score_home - expected_home)
        ratings[away] = ra + K_FACTOR * ((1 - score_home) - (1 - expected_home))
    return dict(ratings)
