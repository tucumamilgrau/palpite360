"""Ligas e competições não cobertas por football-data.co.uk, via API-Football
(api-sports.io): campeonatos africanos, Série B do Brasil, Libertadores e
Sul-Americana.

Diferente de football-data.co.uk, essa fonte exige uma chave de API própria
(gratuita, plano free = 100 requisições/dia). Sem chave configurada, as
funções deste módulo retornam vazio — a interface explica ao usuário como
obter a chave gratuita (ver README.md).

Só buscamos o endpoint /fixtures (placar), nunca /fixtures/statistics: esse
segundo custaria 1 requisição por partida, o que estouraria a cota gratuita
em poucos jogos. Por isso essas competições sempre entram como "básicas"
(sem chutes/escanteios/cartões), igual às ligas fora da Europa em
football-data.co.uk.

O plano Free da API-Football bloqueia buscar fixtures por liga+temporada
fora de 2022-2024 (`load_league` detecta isso automaticamente via
`_plan_range`/`_try_seasons`). Para ter dados atuais mesmo assim, também
varremos `/fixtures?date=AAAA-MM-DD` dia a dia (não tem esse bloqueio) —
ver `advance_day_scan` — aos poucos, sem travar a interface nem gastar a
cota diária de uma vez. O histórico "atual" recuperado dessa forma cresce
a cada uso do app.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import requests

from . import config
from .data_sources import CANON_COLS, _cast_numeric

BASE_URL = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "api_football"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LEAGUE_ID_CACHE_HOURS = 24 * 30  # ids de liga quase nunca mudam
FIXTURES_CACHE_HOURS = 12


def _headers() -> dict:
    return {"x-apisports-key": config.get_api_football_key()}


def _cache_get(path: Path, max_age_hours: float) -> dict | None:
    if not path.exists():
        return None
    age_h = (dt.datetime.now().timestamp() - path.stat().st_mtime) / 3600
    if age_h > max_age_hours:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_set(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _api_get(endpoint: str, params: dict) -> dict | None:
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=_headers(), params=params, timeout=20)
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.RequestException:
        return None


def _slug(*parts: str) -> str:
    return "_".join(p.replace(" ", "-") for p in parts)


def find_league_id(country: str, name_hint: str) -> int | None:
    cache_path = CACHE_DIR / f"league_id_{_slug(country, name_hint)}.json"
    cached = _cache_get(cache_path, LEAGUE_ID_CACHE_HOURS)
    if cached is not None:
        return cached.get("id")

    data = _api_get("leagues", {"country": country} if country != "World" else {"search": name_hint})
    if not data or "response" not in data:
        return None

    league_id = None
    for item in data["response"]:
        league = item.get("league", {})
        if league.get("type") != "League" and country != "World":
            continue
        if name_hint.lower() in (league.get("name") or "").lower():
            league_id = league.get("id")
            break
    if league_id is None and data["response"]:
        league_id = data["response"][0].get("league", {}).get("id")

    _cache_set(cache_path, {"id": league_id})
    return league_id


def _current_season_start_year(today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return today.year if today.month >= 7 else today.year - 1


PLAN_RANGE_CACHE = CACHE_DIR / "plan_season_range.json"


def _plan_range() -> tuple[int, int] | None:
    """Faixa de temporadas liberada pelo plano da chave configurada (o plano
    Free costuma travar temporadas recentes). Descoberta na primeira tentativa
    que falhar por restrição de plano, depois fica em cache por 30 dias — assim
    não desperdiçamos requisições repetindo uma tentativa que sabemos que vai
    falhar."""
    cached = _cache_get(PLAN_RANGE_CACHE, 24 * 30)
    if cached and cached.get("max"):
        return cached["min"], cached["max"]
    return None


def _save_plan_range(lo: int, hi: int) -> None:
    _cache_set(PLAN_RANGE_CACHE, {"min": lo, "max": hi})


def _parse_plan_range(message: str) -> tuple[int, int] | None:
    m = re.search(r"from (\d{4}) to (\d{4})", message or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _season_candidates() -> list[int]:
    known_range = _plan_range()
    if known_range:
        lo, hi = known_range
        return [y for y in (hi, hi - 1, hi - 2) if y >= lo]
    # Sem faixa conhecida ainda: tenta a temporada mais provável primeiro.
    start = _current_season_start_year()
    calendar_year = dt.date.today().year
    return sorted({start, calendar_year}, reverse=True)


def _fetch_fixtures_raw(league_id: int, season: int) -> dict | None:
    cache_path = CACHE_DIR / f"fixtures_{league_id}_{season}.json"
    cached = _cache_get(cache_path, FIXTURES_CACHE_HOURS)
    if cached is not None:
        return cached

    data = _api_get("fixtures", {"league": league_id, "season": season})
    if data is None:
        return None
    _cache_set(cache_path, data)
    return data


def _normalize(fixtures: list[dict], country: str) -> pd.DataFrame:
    rows = []
    for fx in fixtures:
        if fx.get("fixture", {}).get("status", {}).get("short") != "FT":
            continue
        home = fx.get("teams", {}).get("home", {}).get("name")
        away = fx.get("teams", {}).get("away", {}).get("name")
        gh = fx.get("goals", {}).get("home")
        ga = fx.get("goals", {}).get("away")
        date_str = fx.get("fixture", {}).get("date")
        if home is None or away is None or gh is None or ga is None or date_str is None:
            continue
        result = "H" if gh > ga else ("A" if ga > gh else "D")
        rows.append({
            "date": pd.to_datetime(date_str, errors="coerce", utc=True).tz_localize(None),
            "season": fx.get("league", {}).get("season"),
            "league_code": country,
            "home_team": home,
            "away_team": away,
            "home_goals": gh,
            "away_goals": ga,
            "result": result,
        })
    df = pd.DataFrame(rows)
    for col in CANON_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    if df.empty:
        return pd.DataFrame(columns=CANON_COLS)
    return _cast_numeric(df[CANON_COLS].copy())


def _cached_league_id(country: str, name_hint: str) -> int | None:
    id_cache = CACHE_DIR / f"league_id_{_slug(country, name_hint)}.json"
    if not id_cache.exists():
        return None
    try:
        return json.loads(id_cache.read_text(encoding="utf-8")).get("id")
    except Exception:
        return None


def cache_status(country: str, name_hint: str) -> dt.datetime | None:
    league_id = _cached_league_id(country, name_hint)
    candidates = []
    if league_id is not None:
        candidates += list(CACHE_DIR.glob(f"fixtures_{league_id}_*.json"))
    today_file = CACHE_DIR / f"day_{dt.date.today().isoformat()}.json"
    if today_file.exists():
        candidates.append(today_file)
    elif SCAN_PROGRESS_FILE.exists():
        candidates.append(SCAN_PROGRESS_FILE)
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return dt.datetime.fromtimestamp(newest.stat().st_mtime)


def clear_cache(country: str, name_hint: str) -> None:
    league_id = _cached_league_id(country, name_hint)
    if league_id is None:
        return
    for f in CACHE_DIR.glob(f"fixtures_{league_id}_*.json"):
        f.unlink(missing_ok=True)


def _try_seasons(league_id: int, country: str, seasons: list[int]) -> tuple[list[pd.DataFrame], bool]:
    """Busca fixtures para cada temporada da lista. Retorna os dataframes
    obtidos e se aprendemos (pela primeira vez) a faixa de temporadas que o
    plano da chave realmente libera."""
    frames = []
    learned = False
    for season in seasons:
        raw = _fetch_fixtures_raw(league_id, season)
        if not raw:
            continue
        if raw.get("response"):
            frames.append(_normalize(raw["response"], country))
        elif not learned:
            errors = raw.get("errors")
            plan_msg = errors.get("plan") if isinstance(errors, dict) else None
            parsed = _parse_plan_range(plan_msg) if plan_msg else None
            if parsed:
                _save_plan_range(*parsed)
                learned = True
    return frames, learned


SCAN_PROGRESS_FILE = CACHE_DIR / "day_scan_progress.json"
SCAN_BATCH_DAYS = 6          # dias novos por execução (+ hoje/ontem sempre atualizados)
SCAN_MAX_DAYS = 150          # até onde recuar no total
DAY_CACHE_RECENT_HOURS = 6         # hoje/ontem: placar pode mudar, cache curto
DAY_CACHE_STABLE_HOURS = 24 * 365  # dias já encerrados não mudam mais

# A API bloqueia buscar por liga+temporada fora de 2022-2024 no plano Free,
# mas /fixtures?date=AAAA-MM-DD (sem liga nem temporada) devolve os jogos
# REAIS daquele dia em TODAS as ligas, incluindo a temporada atual — sem
# cair nesse bloqueio. Varremos esse endpoint dia a dia, aos poucos (poucas
# chamadas por execução, para não travar a interface nem estourar a cota
# diária), e indexamos localmente por liga. Isso é o que permite ter dados
# atuais de Libertadores/Série B/ligas africanas de graça, sem plano pago.


def _fetch_day(date_str: str, is_recent: bool) -> bool:
    """Garante que o dia está em cache. Retorna True se conseguiu (cache ou rede)."""
    cache_path = CACHE_DIR / f"day_{date_str}.json"
    ttl = DAY_CACHE_RECENT_HOURS if is_recent else DAY_CACHE_STABLE_HOURS
    if _cache_get(cache_path, ttl) is not None:
        return True
    data = _api_get("fixtures", {"date": date_str})
    if data is None:
        return False
    _cache_set(cache_path, data)
    return True


def _scan_progress() -> str | None:
    cached = _cache_get(SCAN_PROGRESS_FILE, 24 * 365)
    return cached.get("oldest_scanned") if cached else None


def _save_scan_progress(date_str: str) -> None:
    _cache_set(SCAN_PROGRESS_FILE, {"oldest_scanned": date_str})


def advance_day_scan(batch_days: int = SCAN_BATCH_DAYS, max_days: int = SCAN_MAX_DAYS) -> int:
    """Avança a varredura por data um pouco mais (gratuito). Chamado a cada
    carregamento de uma liga via API-Football — poucas chamadas de rede por
    vez, então não trava a tela nem consome a cota toda de uma só execução."""
    today = dt.date.today()
    calls = 0

    for delta in (0, 1):  # hoje e ontem sempre revalidados (placar pode mudar)
        d = today - dt.timedelta(days=delta)
        cache_path = CACHE_DIR / f"day_{d.isoformat()}.json"
        if _cache_get(cache_path, DAY_CACHE_RECENT_HOURS) is None:
            if _fetch_day(d.isoformat(), is_recent=True):
                calls += 1

    oldest = _scan_progress()
    frontier = (dt.date.fromisoformat(oldest) - dt.timedelta(days=1)) if oldest else (today - dt.timedelta(days=2))

    if (today - frontier).days >= max_days:
        return calls

    for i in range(batch_days):
        d = frontier - dt.timedelta(days=i)
        if (today - d).days > max_days:
            break
        cache_path = CACHE_DIR / f"day_{d.isoformat()}.json"
        already_cached = _cache_get(cache_path, DAY_CACHE_STABLE_HOURS) is not None
        ok = already_cached or _fetch_day(d.isoformat(), is_recent=False)
        if not already_cached and ok:
            calls += 1
        if ok:
            _save_scan_progress(d.isoformat())
        else:
            break  # falhou (rede/limite) — tenta esse mesmo dia na próxima vez
    return calls


def day_scan_coverage_days() -> int:
    """Quantos dias corridos já foram varridos (0 se ainda não começou)."""
    oldest = _scan_progress()
    if not oldest:
        return 0
    return (dt.date.today() - dt.date.fromisoformat(oldest)).days + 1


def _fixtures_from_day_scan(league_id: int, country: str) -> pd.DataFrame:
    oldest = _scan_progress()
    if not oldest:
        return pd.DataFrame(columns=CANON_COLS)
    today = dt.date.today()
    start_date = dt.date.fromisoformat(oldest)
    n_days = (today - start_date).days + 1

    fixtures = []
    for i in range(n_days):
        d = today - dt.timedelta(days=i)
        cache_path = CACHE_DIR / f"day_{d.isoformat()}.json"
        cached = _cache_get(cache_path, DAY_CACHE_STABLE_HOURS * 2)  # aceita mesmo se o TTL "recente" já passou
        if not cached:
            continue
        for fx in cached.get("response", []):
            if fx.get("league", {}).get("id") == league_id:
                fixtures.append(fx)
    return _normalize(fixtures, country)


FORWARD_SCAN_DAYS = 10  # quantos dias à frente varremos para achar próximos confrontos


def advance_forward_scan(days: int = FORWARD_SCAN_DAYS) -> int:
    """Varre alguns dias à frente de hoje (mesmo endpoint /fixtures?date=,
    sem bloqueio de plano) para descobrir próximos confrontos agendados.
    Gratuito, poucas chamadas — só roda quando a tela de 'próximos
    confrontos' é aberta, não em toda carga de liga."""
    today = dt.date.today()
    calls = 0
    for i in range(1, days + 1):
        d = today + dt.timedelta(days=i)
        cache_path = CACHE_DIR / f"day_{d.isoformat()}.json"
        if _cache_get(cache_path, DAY_CACHE_RECENT_HOURS) is not None:
            continue
        if _fetch_day(d.isoformat(), is_recent=True):
            calls += 1
        else:
            break
    return calls


def upcoming_fixtures(league_id: int, country: str, days_ahead: int = FORWARD_SCAN_DAYS) -> pd.DataFrame:
    """Próximos confrontos ainda não realizados dessa liga, varrendo os
    próximos `days_ahead` dias (inclui hoje, caso ainda tenha jogo por vir)."""
    advance_forward_scan(days_ahead)
    today = dt.date.today()
    rows = []
    for i in range(0, days_ahead + 1):
        d = today + dt.timedelta(days=i)
        cache_path = CACHE_DIR / f"day_{d.isoformat()}.json"
        cached = _cache_get(cache_path, DAY_CACHE_RECENT_HOURS * 2)
        if not cached:
            continue
        for fx in cached.get("response", []):
            if fx.get("league", {}).get("id") != league_id:
                continue
            status = fx.get("fixture", {}).get("status", {}).get("short")
            if status in ("FT", "AET", "PEN", "PST", "CANC", "ABD"):
                continue
            home = fx.get("teams", {}).get("home", {}).get("name")
            away = fx.get("teams", {}).get("away", {}).get("name")
            date_str = fx.get("fixture", {}).get("date")
            if not home or not away or not date_str:
                continue
            rows.append({
                "date": pd.to_datetime(date_str, errors="coerce", utc=True).tz_localize(None),
                "home_team": home,
                "away_team": away,
            })
    if not rows:
        return pd.DataFrame(columns=["date", "home_team", "away_team"])
    return pd.DataFrame(rows).drop_duplicates().sort_values("date").reset_index(drop=True)


MIN_RECENT_MATCHES = 15  # abaixo disso, complementa com as temporadas antigas (2022-2024)


def load_league(country: str, name_hint: str) -> pd.DataFrame:
    if not config.has_api_football_key():
        return pd.DataFrame(columns=CANON_COLS)

    league_id = find_league_id(country, name_hint)
    if league_id is None:
        return pd.DataFrame(columns=CANON_COLS)

    advance_day_scan()
    recent_df = _fixtures_from_day_scan(league_id, country)

    frames = [recent_df] if not recent_df.empty else []

    if len(recent_df) < MIN_RECENT_MATCHES:
        # Ainda não varremos dias suficientes para essa liga: complementa com
        # as temporadas antigas (2022-2024, as únicas liberadas por temporada
        # no plano Free) para não ficar com uma amostra pequena demais.
        old_frames, learned = _try_seasons(league_id, country, _season_candidates())
        if not old_frames and learned:
            old_frames, _ = _try_seasons(league_id, country, _season_candidates())
        frames.extend(old_frames)

    if not frames:
        return pd.DataFrame(columns=CANON_COLS)
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["date", "home_team", "away_team"])
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
