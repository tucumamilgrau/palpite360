"""Palpite 360 — plataforma de análise de futebol, versão gratuita, sem assinaturas.

Gera relatórios comparativos entre duas equipes com base em dados
históricos reais (últimos jogos), sem indicadores ao vivo.
Fontes de dados: football-data.co.uk (Europa e outras, gratuita, sem chave)
e API-Football (África, Sul-Americanas, gratuita, exige chave própria — ver README.md).
"""
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

from src import betting, config, crossing, data_sources, data_sources_api_football, elo, poisson_model, stats
from src.leagues import all_leagues

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"

st.set_page_config(
    page_title="Palpite 360",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "⚽",
    layout="wide",
)

LEAGUES = all_leagues()

# Paleta extraída da logo (verde-limão sobre preto).
CUSTOM_CSS = """
<style>
:root {
    --accent: #96cd14;
    --accent-dark: #6fa00e;
    --bg-card: #111111;
}
.stApp { background-color: #000000; }
h1, h2, h3 { color: #f5f5f5 !important; letter-spacing: -0.02em; }
[data-testid="stMetricValue"] { color: var(--accent) !important; font-weight: 700; }
[data-testid="stMetricLabel"] { color: #9a9a9a !important; }
.stButton > button {
    background-color: var(--accent);
    color: #060a02;
    border: none;
    font-weight: 700;
    border-radius: 6px;
}
.stButton > button:hover { background-color: var(--accent-dark); color: white; }
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--bg-card);
    border-radius: 10px;
}
hr { border-color: #262626 !important; }
.brand-tagline { color: #cfcfcf; font-weight: 600; letter-spacing: 0.04em; }
.brand-tagline .accent { color: var(--accent); }

/* Nunca deixa nada forçar rolagem horizontal, celular ou não. */
.stApp, .stMainBlockContainer { overflow-x: hidden; }
[data-testid="stTable"] { overflow-x: auto; }

/* Toque confortável e menos espaço em branco em telas pequenas. */
@media (max-width: 640px) {
    .stMainBlockContainer { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1.5rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    .stButton > button, .stSelectbox div[data-baseweb="select"] > div, [data-baseweb="radio"] {
        min-height: 44px;
    }
    .stButton > button { width: 100%; font-size: 1rem; }
    h1 { font-size: 1.7rem !important; }
    [data-testid="stVerticalBlock"] { gap: 0.5rem; }

    /* Streamlit empilha colunas em 1 por linha nessa largura por padrão;
    força as grades de métricas a ficarem 2 por linha (menos rolagem). */
    div[class*="st-key-metricgrid"] [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 0.75rem !important;
    }
    div[class*="st-key-metricgrid"] [data-testid="stColumn"] {
        flex: 1 1 44% !important;
        min-width: 44% !important;
        width: 44% !important;
    }
}
</style>
"""

_metric_grid_seq = [0]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_league_cached(code: str, kind: str, extra: str | None):
    if kind == "api_football":
        return data_sources_api_football.load_league(code, extra)
    return data_sources.load_league(code, kind)


def team_list(df):
    return sorted(set(df["home_team"]).union(df["away_team"]))


def render_metric_grid(items: list[tuple[str, str]], cols: int = 2):
    """Mostra métricas em grade de `cols` colunas por linha (em vez de uma
    linha só com muitas colunas) — no celular, o Streamlit empilha qualquer
    st.columns em 1 por linha por padrão, deixando a página comprida; o CSS
    em `st-key-metricgrid-*` força 2 por linha só nessas grades."""
    _metric_grid_seq[0] += 1
    with st.container(key=f"metricgrid-{_metric_grid_seq[0]}"):
        for i in range(0, len(items), cols):
            row = items[i:i + cols]
            row_cols = st.columns(cols)
            for c, (label, value) in zip(row_cols, row):
                c.metric(label, value)


def render_team_card(col, report: dict, elo_rating: float | None):
    with col:
        st.subheader(report["team"])
        if report.get("n_games", 0) == 0:
            st.warning("Sem jogos suficientes nesse recorte.")
            return
        render_metric_grid([
            ("Aproveitamento", f"{report['aproveitamento_pct']}%"),
            ("Gols marcados/jogo", report["gols_marcados_media"]),
            ("Gols sofridos/jogo", report["gols_sofridos_media"]),
        ])
        st.caption(
            f"{report['n_games']} jogos · {report['vitorias']}V {report['empates']}E {report['derrotas']}D · "
            f"sequência recente: {report['sequencia_recente']}"
        )
        if elo_rating is not None:
            st.caption(f"Elo (período carregado): {round(elo_rating)}")

        st.markdown("**Mercados (% dos jogos recentes)**")
        render_metric_grid([
            ("Over 1.5", f"{report['over_15_pct']}%"),
            ("Over 2.5", f"{report['over_25_pct']}%"),
            ("Ambas marcam", f"{report['ambas_marcam_pct']}%"),
            ("Sem sofrer", f"{report['jogos_sem_sofrer_pct']}%"),
        ])

        if "escanteios_media" in report:
            st.markdown("**Estatísticas de jogo (disponível para esta liga)**")
            render_metric_grid([
                ("Finalizações", report["finalizacoes_media"]),
                ("No alvo", report["finalizacoes_no_alvo_media"]),
                ("Escanteios a favor", report["escanteios_media"]),
                ("Cartões", report["cartoes_media"]),
            ])
        else:
            st.caption("Esta liga só disponibiliza dados de placar gratuitamente (sem chutes/escanteios/cartões).")


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    logo_col, title_col = st.columns([1, 5])
    if LOGO_PATH.exists():
        logo_col.image(str(LOGO_PATH), width=110)
    with title_col:
        st.title("PALPITE 360")
        st.markdown(
            '<span class="brand-tagline">SEU PALPITE. <span class="accent">NOSSO JOGO.</span></span>',
            unsafe_allow_html=True,
        )
    st.caption(
        "Sem assinaturas, sem cobrança, sem indicadores ao vivo. "
        "Relatórios comparativos com base em dados históricos reais das duas equipes."
    )
    st.info(
        "As previsões abaixo são **estimativas estatísticas**, não certezas. "
        "Nenhum modelo garante o resultado de uma partida.",
        icon="ℹ️",
    )

    st.subheader("Configuração")
    regions = ["Todas", "Europa", "Sul-Americanas", "África", "Outras"]
    region = st.radio("Região", regions, horizontal=True, index=0)

    names = sorted(
        name for name, (_, _, _, r) in LEAGUES.items()
        if region == "Todas" or r == region
    )

    cfg1, cfg2 = st.columns(2)
    league_name = cfg1.selectbox("Campeonato", names)
    code, kind, extra, _ = LEAGUES[league_name]
    window_label = cfg2.selectbox("Janela de jogos", ["Últimos 5", "Últimos 10", "Últimos 15", "Últimos 20", "Temporada(s) carregada(s)"], index=1)
    window_map = {"Últimos 5": 5, "Últimos 10": 10, "Últimos 15": 15, "Últimos 20": 20, "Temporada(s) carregada(s)": None}
    last_n = window_map[window_label]

    if kind == "api_football" and not config.has_api_football_key():
        st.warning(
            "Esta competição usa a API-Football (África / Sul-Americanas), que exige uma "
            "chave gratuita própria. Crie uma conta grátis em api-football.com, copie sua "
            "chave e salve em `config/api_football_key.txt` (veja o README.md). Sem isso, "
            "apenas as ligas 'Europa' e 'Outras' funcionam.",
            icon="🔑",
        )
        return

    with st.spinner(f"Carregando dados de {league_name}..."):
        df = load_league_cached(code, kind, extra)

    status_col1, status_col2 = st.columns([4, 1])
    updated_at = (
        data_sources_api_football.cache_status(code, extra) if kind == "api_football"
        else data_sources.cache_status(code, kind)
    )
    if updated_at:
        coverage_note = ""
        if kind == "api_football":
            days = data_sources_api_football.day_scan_coverage_days()
            coverage_note = f" · varredura de jogos recentes cobre os últimos {days} dias (cresce a cada uso)."
        status_col1.caption(
            f"Dados de {league_name} atualizados em {updated_at.strftime('%d/%m/%Y %H:%M')} "
            f"· atualiza sozinho a cada 6h enquanto o app estiver em uso.{coverage_note}"
        )
    if status_col2.button("🔄 Atualizar agora"):
        if kind == "api_football":
            data_sources_api_football.clear_cache(code, extra)
        else:
            data_sources.clear_cache(code, kind)
        load_league_cached.clear()
        st.rerun()

    if df.empty:
        st.error(
            "Não foi possível carregar dados para este campeonato agora "
            "(sem conexão, sem cache local, ou liga/temporada indisponível na fonte). "
            "Tente novamente mais tarde ou escolha outro campeonato."
        )
        return

    if kind == "api_football" and not df.empty:
        latest_date = df["date"].max()
        days_since_last_match = (dt.datetime.now() - latest_date).days if pd.notna(latest_date) else None
        if days_since_last_match is not None and days_since_last_match > 20:
            st.warning(
                f"O jogo mais recente nesta amostra é de {latest_date.strftime('%d/%m/%Y')} "
                f"({days_since_last_match} dias atrás) — o plano gratuito da API-Football não libera "
                f"temporadas recentes por completo, então a varredura de jogos atuais (ver nota acima) "
                f"ainda não tem histórico suficiente para esta competição. Ela cresce sozinha a cada "
                f"uso do app; enquanto isso, complementamos com temporadas antigas (2022-2024) para "
                f"não ficar com amostra pequena demais.",
                icon="📅",
            )

    teams = team_list(df)
    col_a, col_b = st.columns(2)
    team_a = col_a.selectbox("Time mandante (Time A)", teams, index=0)
    team_b = col_b.selectbox("Time visitante (Time B)", teams, index=min(1, len(teams) - 1))

    if team_a == team_b:
        st.warning("Selecione dois times diferentes.")
        return

    if st.button("Gerar relatório", type="primary"):
        report_a_all = stats.team_report(df, team_a, last_n=last_n, venue="all")
        report_b_all = stats.team_report(df, team_b, last_n=last_n, venue="all")
        report_a_home = stats.team_report(df, team_a, last_n=last_n, venue="home")
        report_b_away = stats.team_report(df, team_b, last_n=last_n, venue="away")
        league_avg = stats.league_averages(df)
        ratings = elo.compute_ratings(df)

        st.divider()
        st.header(f"{team_a} × {team_b}")
        col1, col2 = st.columns(2)
        render_team_card(col1, report_a_all, ratings.get(team_a))
        render_team_card(col2, report_b_all, ratings.get(team_b))

        st.divider()
        st.subheader("Cruzamento de dados")
        findings = crossing.cross_analysis(report_a_all, report_b_all)
        if not findings:
            st.write("Dados insuficientes para cruzamento nesta janela.")
        for f in findings:
            tag = ""
            if f.get("favor_a"):
                tag = f"🟢 favorece {team_a}"
            elif f.get("favor_b"):
                tag = f"🟢 favorece {team_b}"
            st.markdown(f"**{f['indicador']}** — {team_a}: `{f['time_a']}` · {team_b}: `{f['time_b']}` {tag}")
            st.caption(f["explicacao"])

        if report_a_home.get("n_games") and report_b_away.get("n_games"):
            st.divider()
            st.subheader("Estimativa de placar (Poisson)")
            pred = poisson_model.predict(report_a_home, report_b_away, league_avg)

            st.caption(
                f"Gols esperados: {team_a} {pred['xg_casa']} × {pred['xg_fora']} {team_b} "
                f"(baseado no ataque de {team_a} em casa e defesa de {team_b} fora, e vice-versa)."
            )
            render_metric_grid([
                (f"Vitória {team_a}", f"{pred['vitoria_casa_pct']}%"),
                ("Empate", f"{pred['empate_pct']}%"),
                (f"Vitória {team_b}", f"{pred['vitoria_fora_pct']}%"),
            ])

            st.markdown("**Gols (Over)**")
            render_metric_grid([(f"Over {line}", f"{val}%") for line, val in pred["over_pct"].items()])

            st.metric("Ambas marcam", f"{pred['ambas_marcam_pct']}%")

            st.markdown("**Placares mais prováveis**")
            st.table(pred["placares_provaveis"])

            st.markdown("**Por que o modelo chegou nesses números?**")
            st.markdown(
                f"- {team_a} marca em média **{report_a_home.get('gols_marcados_media')}** gols/jogo em casa "
                f"(recorte: {report_a_home.get('n_games')} jogos).\n"
                f"- {team_b} sofre em média **{report_b_away.get('gols_sofridos_media')}** gols/jogo fora "
                f"(recorte: {report_b_away.get('n_games')} jogos).\n"
                f"- {team_b} marca em média **{report_b_away.get('gols_marcados_media')}** gols/jogo fora.\n"
                f"- {team_a} sofre em média **{report_a_home.get('gols_sofridos_media')}** gols/jogo em casa.\n"
                f"- Médias da liga usadas como referência: {round(league_avg.get('gols_casa_media', 0), 2)} "
                f"gols/jogo em casa e {round(league_avg.get('gols_fora_media', 0), 2)} gols/jogo fora."
            )

            st.divider()
            st.subheader("💰 Recomendações de apostas")
            st.caption(
                "Classificação por confiança estatística do modelo, não por retorno financeiro. "
                "Aposte com responsabilidade: isso não é garantia de ganho, apenas uma leitura "
                "probabilística dos dados recentes."
            )
            market_data = betting.build_markets(team_a, team_b, report_a_home, report_b_away, league_avg)
            markets = market_data["mercados"]

            tier_groups = {betting.TIER_GREEN: [], betting.TIER_YELLOW: [], betting.TIER_RED: []}
            for m in markets:
                tier_groups.setdefault(m["tier"], []).append(m)

            for tier_name, items in tier_groups.items():
                if not items:
                    continue
                st.markdown(f"**{tier_name}**")
                for m in items[:6]:
                    st.markdown(f"- {m['categoria']}: **{m['mercado']}** — {m['probabilidade_pct']}%")

            combo = betting.best_combination(markets, n=3)
            if combo:
                st.markdown("**🔥 Melhor combinação (múltipla) sugerida**")
                for leg in combo["pernas"]:
                    st.markdown(f"- {leg['categoria']}: {leg['mercado']} ({leg['probabilidade_pct']}%)")
                st.markdown(
                    f"Probabilidade combinada aproximada: **{combo['probabilidade_combinada_pct']}%** "
                    f"— cálculo assume que os mercados são independentes entre si, o que é uma "
                    f"simplificação; mercados correlacionados (ex.: over gols e ambas marcam) tendem "
                    f"a ter chance conjunta real menor que esse produto simples."
                )

            st.caption(
                "Fora do alcance deste sistema por falta de dado gratuito confiável: mercados de "
                "jogadores, impacto de escalação/desfalques confirmados no dia, e cash-out (depende "
                "da odd ao vivo da própria casa de apostas, que não temos acesso)."
            )
        else:
            st.info("Sem jogos suficientes em casa/fora para calcular a estimativa de placar nesta janela.")

    st.divider()
    st.caption(
        "Fontes: football-data.co.uk (Europa e outras, gratuita) e API-Football (África e Sul-Americanas, gratuita com chave própria). "
        "Ligas 'básicas' (ex.: Brasil, África, Libertadores) só têm placar disponível de graça, sem chutes/escanteios/cartões. "
        "Este sistema não processa apostas nem dinheiro — apenas estima probabilidades com base em dados "
        "históricos. Nenhuma probabilidade aqui é garantia de resultado. Se apostar, aposte com "
        "responsabilidade e dentro do que você pode perder. +18."
    )


if __name__ == "__main__":
    main()
