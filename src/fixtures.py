"""Próximos confrontos (agenda futura), unificando as duas fontes.

Cobertura real (gratuita):
- Ligas 'full' (football-data.co.uk): só os próprios dias — a fonte não
  disponibiliza uma agenda longa de graça, geralmente é a rodada mais
  próxima.
- Ligas 'api_football' (África/Sul-Americanas): próximos ~10 dias, via a
  mesma varredura por data usada para o histórico recente.
- Ligas 'basic' (Brasil Série A, Argentina, etc. via football-data.co.uk):
  sem fonte gratuita de agenda futura — retorna vazio.
"""
from __future__ import annotations

import pandas as pd

from . import data_sources, data_sources_api_football


def load_upcoming(code: str, kind: str, extra: str | None) -> pd.DataFrame:
    if kind == "full":
        return data_sources.load_upcoming_fixtures(code)
    if kind == "api_football":
        league_id = data_sources_api_football.find_league_id(code, extra)
        if league_id is None:
            return pd.DataFrame(columns=["date", "home_team", "away_team"])
        return data_sources_api_football.upcoming_fixtures(league_id, code)
    return pd.DataFrame(columns=["date", "home_team", "away_team"])
