"""Cruzamento inteligente entre duas equipes (seção 11 do escopo)."""
from __future__ import annotations


def _fmt(v):
    return "N/D" if v is None else v


def cross_analysis(report_a: dict, report_b: dict) -> list[dict]:
    """Compara o ataque de A com a defesa de B (e vice-versa) e sinaliza
    combinações estatisticamente favoráveis. Retorna uma lista de achados
    prontos para exibição, cada um com um rótulo e uma explicação curta.
    """
    findings = []

    def add(label, value_a, value_b, explain, favor_a=None, favor_b=None):
        findings.append({
            "indicador": label,
            "time_a": _fmt(value_a),
            "time_b": _fmt(value_b),
            "explicacao": explain,
            "favor_a": favor_a,
            "favor_b": favor_b,
        })

    gm_a, gs_b = report_a.get("gols_marcados_media"), report_b.get("gols_sofridos_media")
    if gm_a is not None and gs_b is not None:
        favor = gm_a > 1.3 and gs_b > 1.3
        add(
            f"Gols: ataque de {report_a['team']} x defesa de {report_b['team']}",
            gm_a, gs_b,
            f"{report_a['team']} marca em média {gm_a} gols/jogo; {report_b['team']} sofre em média {gs_b} gols/jogo.",
            favor_a=favor,
        )

    gm_b, gs_a = report_b.get("gols_marcados_media"), report_a.get("gols_sofridos_media")
    if gm_b is not None and gs_a is not None:
        favor = gm_b > 1.3 and gs_a > 1.3
        add(
            f"Gols: ataque de {report_b['team']} x defesa de {report_a['team']}",
            gs_a, gm_b,
            f"{report_b['team']} marca em média {gm_b} gols/jogo; {report_a['team']} sofre em média {gs_a} gols/jogo.",
            favor_b=favor,
        )

    ca = report_a.get("escanteios_media")
    csb = report_b.get("escanteios_sofridos_media")
    if ca is not None and csb is not None:
        favor = ca > 5.5 and csb > 5.5
        add(
            f"Escanteios: {report_a['team']} força x {report_b['team']} cede",
            ca, csb,
            f"{report_a['team']} tem em média {ca} escanteios a favor; {report_b['team']} cede em média {csb}.",
            favor_a=favor,
        )

    cb = report_b.get("escanteios_media")
    csa = report_a.get("escanteios_sofridos_media")
    if cb is not None and csa is not None:
        favor = cb > 5.5 and csa > 5.5
        add(
            f"Escanteios: {report_b['team']} força x {report_a['team']} cede",
            csa, cb,
            f"{report_b['team']} tem em média {cb} escanteios a favor; {report_a['team']} cede em média {csa}.",
            favor_b=favor,
        )

    for metric, label in [("over_25_pct", "Over 2.5 gols"), ("ambas_marcam_pct", "Ambas marcam")]:
        va, vb = report_a.get(metric), report_b.get(metric)
        if va is not None and vb is not None:
            add(
                f"Tendência combinada: {label}",
                f"{va}%", f"{vb}%",
                f"{report_a['team']} teve {label.lower()} em {va}% dos jogos recentes; "
                f"{report_b['team']} em {vb}% dos jogos recentes.",
            )

    return findings
