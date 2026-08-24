"""Configuração de chaves de API opcionais (nenhuma é obrigatória para as
ligas europeias — só é necessária para habilitar as ligas africanas).

Três formas de configurar a chave, nessa ordem de prioridade:
1. Streamlit Secrets (`st.secrets`) — usado no Streamlit Community Cloud.
2. Variável de ambiente `API_FOOTBALL_KEY`.
3. Arquivo local `config/api_football_key.txt` (uso na sua máquina).
"""
from __future__ import annotations

import os
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
API_FOOTBALL_KEY_FILE = CONFIG_DIR / "api_football_key.txt"


def _from_streamlit_secrets() -> str | None:
    try:
        import streamlit as st
        key = st.secrets.get("API_FOOTBALL_KEY")
        return key.strip() if key and key.strip() else None
    except Exception:
        # Sem st.secrets configurado (ou nem rodando dentro do Streamlit) — tudo bem.
        return None


def get_api_football_key() -> str | None:
    key = _from_streamlit_secrets()
    if key:
        return key
    key = os.environ.get("API_FOOTBALL_KEY")
    if key and key.strip():
        return key.strip()
    if API_FOOTBALL_KEY_FILE.exists():
        content = API_FOOTBALL_KEY_FILE.read_text(encoding="utf-8").strip()
        if content:
            return content
    return None


def has_api_football_key() -> bool:
    return get_api_football_key() is not None
