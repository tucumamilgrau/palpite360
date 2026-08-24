"""Catálogo de campeonatos disponíveis gratuitamente.

Quatro categorias:
- FULL_STAT_LEAGUES: football-data.co.uk, arquivo por temporada, com
  estatísticas completas (chutes, escanteios, cartões, faltas, árbitro).
  Cobre os principais campeonatos europeus.
- BASIC_STAT_LEAGUES: football-data.co.uk, um único arquivo com todas as
  temporadas, contendo apenas placar (sem chutes/escanteios/cartões).
  Cobre outros campeonatos europeus e não europeus.
- AFRICAN_LEAGUES / SOUTH_AMERICA_EXTRA: via API-Football (api-sports.io),
  que exige uma chave gratuita própria (ver README). Sem essa chave não há
  dados históricos gratuitos e sem cadastro para essas competições —
  football-data.co.uk não as cobre (confirmado: só tem Brasileirão Série A,
  não tem Série B, Libertadores nem Sul-Americana).
"""

FULL_STAT_LEAGUES = {
    "Inglaterra - Premier League": "E0",
    "Inglaterra - Championship": "E1",
    "Inglaterra - League One": "E2",
    "Inglaterra - League Two": "E3",
    "Inglaterra - National League": "EC",
    "Escócia - Premiership": "SC0",
    "Escócia - Championship": "SC1",
    "Escócia - League One": "SC2",
    "Escócia - League Two": "SC3",
    "Alemanha - Bundesliga": "D1",
    "Alemanha - 2. Bundesliga": "D2",
    "Itália - Serie A": "I1",
    "Itália - Serie B": "I2",
    "Espanha - La Liga": "SP1",
    "Espanha - La Liga 2": "SP2",
    "França - Ligue 1": "F1",
    "França - Ligue 2": "F2",
    "Holanda - Eredivisie": "N1",
    "Bélgica - Pro League": "B1",
    "Portugal - Primeira Liga": "P1",
    "Turquia - Süper Lig": "T1",
    "Grécia - Super League": "G1",
}

# Todos europeus, exceto Argentina/China/Japão/México/EUA — mantidos porque
# usam a mesma fonte e o mesmo formato "básico" (só placar).
BASIC_STAT_LEAGUES = {
    "Áustria - Bundesliga": "AUT",
    "Dinamarca - Superliga": "DNK",
    "Finlândia - Veikkausliiga": "FIN",
    "Irlanda - Premier Division": "IRL",
    "Noruega - Eliteserien": "NOR",
    "Polônia - Ekstraklasa": "POL",
    "Romênia - Liga I": "ROU",
    "Rússia - Premier League": "RUS",
    "Suécia - Allsvenskan": "SWE",
    "Suíça - Super League": "SWZ",
    "Brasil - Série A": "BRA",
    "Argentina - Liga Profesional": "ARG",
    "China - Super League": "CHN",
    "Japão - J1 League": "JPN",
    "México - Liga MX": "MEX",
    "EUA - MLS": "USA",
}

# name: (país na API-Football, trecho do nome da liga para identificar a
# divisão principal entre as competições daquele país)
AFRICAN_LEAGUES = {
    "Egito - Premier League": ("Egypt", "Premier League"),
    "África do Sul - Premiership": ("South Africa", "Premiership"),
    "Marrocos - Botola Pro": ("Morocco", "Botola Pro"),
    "Tunísia - Ligue Professionnelle 1": ("Tunisia", "Ligue 1"),
    "Argélia - Ligue 1": ("Algeria", "Ligue 1"),
    "Nigéria - NPFL": ("Nigeria", "NPFL"),
    "Gana - Premier League": ("Ghana", "Premier League"),
    "Quênia - Premier League": ("Kenya", "Premier League"),
    "Angola - Girabola": ("Angola", "Girabola"),
    "Costa do Marfim - Ligue 1": ("Ivory Coast", "Ligue 1"),
    "Camarões - Elite One": ("Cameroon", "Elite One"),
    "Tanzânia - Premier League": ("Tanzania", "Premier League"),
    "Zâmbia - Super League": ("Zambia", "Super League"),
    "CAF - Champions League": ("World", "CAF Champions League"),
}

# Competições sul-americanas não cobertas por football-data.co.uk, também
# via API-Football (mesma chave gratuita das ligas africanas).
SOUTH_AMERICA_EXTRA = {
    "Brasil - Série B": ("Brazil", "Serie B"),
    "Libertadores": ("World", "Libertadores"),
    "Sul-Americana": ("World", "Sudamericana"),
}


NON_EUROPEAN_BASIC = {"Brasil - Série A", "Argentina - Liga Profesional", "China - Super League", "Japão - J1 League", "México - Liga MX", "EUA - MLS"}


def all_leagues() -> dict:
    """Retorna {nome_exibido: (identificador, tipo, extra, regiao)}.

    tipo 'full'/'basic' -> identificador é o código football-data.co.uk, extra=None.
    tipo 'api_football'  -> identificador é o país (ou 'World' para
    competições continentais), extra é a dica do nome da liga usada para
    encontrar o id certo dinamicamente.
    """
    out = {}
    for name, code in FULL_STAT_LEAGUES.items():
        out[name] = (code, "full", None, "Europa")
    for name, code in BASIC_STAT_LEAGUES.items():
        region = "Outras" if name in NON_EUROPEAN_BASIC else "Europa"
        out[name] = (code, "basic", None, region)
    for name, (country, hint) in AFRICAN_LEAGUES.items():
        out[name] = (country, "api_football", hint, "África")
    for name, (country, hint) in SOUTH_AMERICA_EXTRA.items():
        out[name] = (country, "api_football", hint, "Sul-Americanas")
    return out
