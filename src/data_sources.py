"""Download e normalização de dados históricos gratuitos (football-data.co.uk).

Sem chave de API, sem login, sem custo. Os CSVs são cacheados em
data/cache/ para evitar downloads repetidos e permitir uso offline
com o último dado disponível.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_CACHE_AGE_HOURS = 6
N_SEASONS_FULL = 3  # quantas temporadas buscar para ligas com stats completas

CANON_COLS = [
    "date", "season", "league_code", "home_team", "away_team",
    "home_goals", "away_goals", "result",
    "home_ht_goals", "away_ht_goals", "result_ht",
    "home_shots", "away_shots", "home_shots_target", "away_shots_target",
    "home_corners", "away_corners", "home_fouls", "away_fouls",
    "home_yellow", "away_yellow", "home_red", "away_red", "referee",
]

NUMERIC_COLS = [
    "home_goals", "away_goals", "home_ht_goals", "away_ht_goals",
    "home_shots", "away_shots", "home_shots_target", "away_shots_target",
    "home_corners", "away_corners", "home_fouls", "away_fouls",
    "home_yellow", "away_yellow", "home_red", "away_red",
]


def _cast_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _current_season_start_year(today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return today.year if today.month >= 7 else today.year - 1


def _season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def _recent_season_codes(n: int = N_SEASONS_FULL) -> list[str]:
    start = _current_season_start_year()
    return [_season_code(start - i) for i in range(n)]


def _fetch(url: str, cache_path: Path) -> bytes | None:
    """Baixa `url`, cacheando em `cache_path`. Usa cache se offline ou 404."""
    fresh_enough = (
        cache_path.exists()
        and (dt.datetime.now().timestamp() - cache_path.stat().st_mtime) < MAX_CACHE_AGE_HOURS * 3600
    )
    if fresh_enough:
        return cache_path.read_bytes()
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            cache_path.write_bytes(resp.content)
            return resp.content
    except requests.RequestException:
        pass
    if cache_path.exists():
        return cache_path.read_bytes()
    return None


def _normalize_full(df: pd.DataFrame, code: str, season: str) -> pd.DataFrame:
    rename = {
        "Date": "date", "HomeTeam": "home_team", "AwayTeam": "away_team",
        "FTHG": "home_goals", "FTAG": "away_goals", "FTR": "result",
        "HTHG": "home_ht_goals", "HTAG": "away_ht_goals", "HTR": "result_ht",
        "HS": "home_shots", "AS": "away_shots",
        "HST": "home_shots_target", "AST": "away_shots_target",
        "HC": "home_corners", "AC": "away_corners",
        "HF": "home_fouls", "AF": "away_fouls",
        "HY": "home_yellow", "AY": "away_yellow",
        "HR": "home_red", "AR": "away_red",
        "Referee": "referee",
    }
    df = df.rename(columns=rename).copy()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["season"] = season
    df["league_code"] = code
    for col in CANON_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df.dropna(subset=["date", "home_team", "away_team", "home_goals", "away_goals"])
    return _cast_numeric(df[CANON_COLS].copy())


def _normalize_basic(df: pd.DataFrame, code: str) -> pd.DataFrame:
    rename = {
        "Date": "date", "Home": "home_team", "Away": "away_team",
        "HG": "home_goals", "AG": "away_goals", "Res": "result",
        "Season": "season",
    }
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["league_code"] = code
    for col in CANON_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df.dropna(subset=["date", "home_team", "away_team", "home_goals", "away_goals"])
    return _cast_numeric(df[CANON_COLS].copy())


def load_full_league(code: str) -> pd.DataFrame:
    frames = []
    for season in _recent_season_codes():
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
        cache_path = CACHE_DIR / f"{code}_{season}.csv"
        raw = _fetch(url, cache_path)
        if not raw:
            continue
        try:
            df = pd.read_csv(pd.io.common.BytesIO(raw))
        except Exception:
            continue
        if df.empty or "HomeTeam" not in df.columns:
            continue
        frames.append(_normalize_full(df, code, season))
    if not frames:
        return pd.DataFrame(columns=CANON_COLS)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values("date").reset_index(drop=True)


def load_basic_league(code: str) -> pd.DataFrame:
    url = f"https://www.football-data.co.uk/new/{code}.csv"
    cache_path = CACHE_DIR / f"{code}_all.csv"
    raw = _fetch(url, cache_path)
    if not raw:
        return pd.DataFrame(columns=CANON_COLS)
    try:
        df = pd.read_csv(pd.io.common.BytesIO(raw))
    except Exception:
        return pd.DataFrame(columns=CANON_COLS)
    out = _normalize_basic(df, code)
    return out.sort_values("date").reset_index(drop=True)


def load_league(code: str, kind: str) -> pd.DataFrame:
    if kind == "full":
        return load_full_league(code)
    if kind == "basic":
        return load_basic_league(code)
    raise ValueError(f"Tipo de liga desconhecido: {kind}")


def cache_status(code: str, kind: str) -> dt.datetime | None:
    """Data/hora do arquivo de cache mais recente para essa liga (para exibir
    'atualizado em' na interface). None se nunca foi baixado."""
    pattern = f"{code}_all.csv" if kind == "basic" else f"{code}_*.csv"
    files = list(CACHE_DIR.glob(pattern))
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    return dt.datetime.fromtimestamp(newest.stat().st_mtime)


def clear_cache(code: str, kind: str) -> None:
    """Apaga o cache local dessa liga, forçando um novo download na próxima carga."""
    pattern = f"{code}_all.csv" if kind == "basic" else f"{code}_*.csv"
    for f in CACHE_DIR.glob(pattern):
        f.unlink(missing_ok=True)


# --- Próximos confrontos (agenda futura) ---
#
# football-data.co.uk também publica um único CSV (compartilhado entre
# ligas) com os próximos jogos ainda não realizados — só cobre as ligas
# "completas" (as mesmas de FULL_STAT_LEAGUES), com poucos dias de agenda
# à frente (a própria fonte só disponibiliza isso). Ligas "básicas" não têm
# essa agenda disponível de graça.

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
FIXTURES_CACHE_FILE = CACHE_DIR / "fixtures_upcoming.csv"


def load_upcoming_fixtures(code: str) -> pd.DataFrame:
    """Próximos jogos ainda não realizados dessa liga (só ligas 'full').
    Retorna colunas: date, home_team, away_team. Vazio se a fonte não cobrir
    essa liga ou não houver jogos agendados nos próximos dias."""
    empty = pd.DataFrame(columns=["date", "home_team", "away_team"])
    raw = _fetch(FIXTURES_URL, FIXTURES_CACHE_FILE)
    if not raw:
        return empty
    try:
        df = pd.read_csv(pd.io.common.BytesIO(raw))
    except Exception:
        return empty
    if "Div" not in df.columns or code not in set(df["Div"].unique()):
        return empty

    sub = df[df["Div"] == code].copy()
    time_str = sub["Time"].fillna("00:00") if "Time" in sub.columns else "00:00"
    sub["date"] = pd.to_datetime(
        sub["Date"].astype(str) + " " + time_str.astype(str),
        dayfirst=True, errors="coerce",
    )
    sub = sub.rename(columns={"HomeTeam": "home_team", "AwayTeam": "away_team"})
    sub = sub.dropna(subset=["date", "home_team", "away_team"])
    sub = sub[sub["date"] >= pd.Timestamp.now() - pd.Timedelta(hours=3)]  # tira jogos já iniciados/velhos do arquivo
    return sub[["date", "home_team", "away_team"]].sort_values("date").reset_index(drop=True)
