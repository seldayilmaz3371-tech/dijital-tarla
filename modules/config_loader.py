"""
config_loader.py
-----------------
config.json dosyasını okur ve st.secrets'a GÜVENLİ şekilde erişim sağlar.
secrets.toml henüz oluşturulmamışsa uygulama çökmez; sadece ilgili
özellik "yapılandırılmamış" olarak işaretlenir.
"""

from __future__ import annotations
import json
from pathlib import Path

import streamlit as st


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_secret(key_name: str) -> str | None:
    """st.secrets içinden anahtarı okur. Bulunamazsa None döner (asla hata fırlatmaz)."""
    try:
        return st.secrets.get(key_name)
    except Exception:
        return None


def get_active_ai_settings(config: dict) -> dict:
    """config.json -> ai bölümünden aktif sağlayıcının model ve secret key adını döner."""
    ai_cfg = config["ai"]
    provider = ai_cfg["active_provider"]
    provider_cfg = ai_cfg["providers"][provider]
    return {
        "provider": provider,
        "model": provider_cfg["model"],
        "api_key": get_secret(provider_cfg["secret_key_name"]),
    }


def get_active_search_settings(config: dict) -> dict:
    search_cfg = config["search"]
    provider = search_cfg["active_provider"]
    provider_cfg = search_cfg["providers"][provider]
    return {
        "provider": provider,
        "api_key": get_secret(provider_cfg["secret_key_name"]),
        "max_results": search_cfg.get("max_results", 5),
    }