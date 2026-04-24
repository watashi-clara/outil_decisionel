"""Coeur métier du comparateur de villes.

Ce module regroupe le chargement des données locales, les appels aux APIs
externes et les fonctions de préparation/formatage utilisées par l'interface
Streamlit.
"""

from __future__ import annotations

import logging
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. Emplacement des fichiers et variables globales
# -----------------------------------------------------------------------------
# Toutes les données locales sont rangées dans le dossier data/. Les chemins sont
# construits à partir du fichier actuel pour que l’application fonctionne même si
# le projet est déplacé dans un autre dossier.

DOSSIER_DONNEES = Path(__file__).resolve().parent / "data"
FICHIER_BASE = DOSSIER_DONNEES / "base_cc_comparateur.csv"
FICHIER_COMPLET = DOSSIER_DONNEES / "dossier_complet_light.csv"
FICHIER_VILLES = DOSSIER_DONNEES / "departement_codedepartement.xlsx"
AGENT_UTILISATEUR = "outil-decisionnel/1.0"
URL_LOYERS_APPARTEMENTS = "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv"
EN_TETES_HTTP = {"User-Agent": AGENT_UTILISATEUR}
SESSION_HTTP = requests.Session()
SESSION_HTTP.headers.update(EN_TETES_HTTP)
JOURNAL = logging.getLogger(__name__)
REMPLACEMENTS_CODES_COMMUNES = {
    **{f"751{i:02d}": "75056" for i in range(1, 21)},
    **{f"6938{i}": "69123" for i in range(1, 10)},
    **{f"132{i:02d}": "13055" for i in range(1, 17)},
}

# Colonnes lues dans la base principale. On ne charge que les colonnes utiles
# pour éviter de ralentir l’application avec des données non utilisées.
COLONNES_BASE = [
    "CODGEO",
    "P22_POP",
    "SUPERF",
    "P22_MEN",
    "NAISD24",
    "DECESD24",
    "MED21",
    "PIMP21",
    "P22_LOG",
    "P22_RP",
    "P22_LOGVAC",
    "P22_RP_PROP",
    "P22_POP1564",
    "P22_ACT1564",
    "P22_CHOM1564",
    "P22_EMPLT",
    "P22_EMPLT_SAL",
    "ETTOT24",
]

# Colonnes lues dans le fichier complémentaire : emploi, économie, tourisme, etc.
COLONNES_COMPLEMENTAIRES = [
    "CODGEO",
    "ENCTOT25",
    "ENCITOT25",
    "ETCTOT25",
    "SNEMM_23",
    "P22_ACT1524",
    "P22_ACT2554",
    "P22_ACT5564",
    "P22_CHOM1524",
    "P22_CHOM2554",
    "P22_CHOM5564",
    "ELECTEURSLP2024",
    "HT26",
    "CPG26",
    "VV26",
    "RT26",
    "AJCS26",
    "P22_POP0014",
    "P22_POP1529",
    "P22_POP3044",
    "P22_POP4559",
    "P22_POP6074",
    "P22_POP7589",
    "P22_POP90P",
    "P11_POP",
    "P16_POP",
    "C22_MENPSEUL",
    "C22_MENFAM",
    "C22_COUPSENF",
    "C22_COUPAENF",
    "C22_FAMMONO",
    "ENCTOT22",
    "ENCTOT23",
    "ENCTOT24",
    "BPE_2024_B105",
    "BPE_2024_B201",
    "BPE_2024_C201",
    "BPE_2024_C301",
    "BPE_2024_D307",
]

# Libellés des mois utilisés pour les graphiques de climat.
LIBELLES_MOIS = {
    1: "Jan",
    2: "Fév",
    3: "Mar",
    4: "Avr",
    5: "Mai",
    6: "Juin",
    7: "Juil",
    8: "Août",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Déc",
}

# Traduction des codes météo Open-Meteo en texte compréhensible.
LIBELLES_CODES_METEO = {
    0: "Ciel dégagé",
    1: "Peu nuageux",
    2: "Partiellement nuageux",
    3: "Couvert",
    45: "Brouillard",
    48: "Brouillard givrant",
    51: "Bruine légère",
    53: "Bruine",
    55: "Bruine forte",
    56: "Bruine verglaçante légère",
    57: "Bruine verglaçante forte",
    61: "Pluie faible",
    63: "Pluie",
    65: "Pluie forte",
    66: "Pluie verglaçante légère",
    67: "Pluie verglaçante forte",
    71: "Neige faible",
    73: "Neige",
    75: "Neige forte",
    77: "Grains de neige",
    80: "Averses faibles",
    81: "Averses",
    82: "Averses fortes",
    85: "Averses de neige faibles",
    86: "Averses de neige fortes",
    95: "Orage",
    96: "Orage + grêle faible",
    99: "Orage + grêle forte",
}


# -----------------------------------------------------------------------------
# 2. Configuration visuelle de Streamlit
# -----------------------------------------------------------------------------
# Ces fonctions s’occupent uniquement de la présentation : largeur de page, style
# CSS, cartes, tableaux et adaptation mobile.

def configurer_page(titre_page: str, icone_page: str | None = None) -> None:
    """Configure la page Streamlit et applique le thème graphique."""
    # Configuration générale de Streamlit avant d’afficher le moindre élément.
    st.set_page_config(
        page_title=titre_page,
        page_icon=icone_page,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    appliquer_theme()


def appliquer_theme() -> None:
    """Injecte le CSS personnalisé utilisé par toute l'application."""
    # Le CSS est injecté dans la page pour obtenir une interface plus propre
    # que le style Streamlit par défaut.
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&family=Source+Sans+3:wght@400;600;700&display=swap');

:root {
  --ink: #143047;
  --muted: #5d7385;
  --line: #d7e3ec;
  --paper: #ffffff;
  --surface: #f5f7fa;
  --navy: #173550;
  --accent: #d96a2b;
}

.stApp {
  color: var(--ink);
  background: var(--surface);
}

html, body, [class*="st-"], [class^="css"] {
  font-family: 'Source Sans 3', sans-serif;
}

h1, h2, h3 {
  font-family: 'Manrope', sans-serif;
  color: var(--ink);
  letter-spacing: -0.03em;
}

.block-container {
  max-width: 1220px;
  padding-top: 1.8rem;
  padding-bottom: 3rem;
}

section[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
  display: none;
}

.hero-shell {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 28px;
  padding: 1.45rem 1.55rem 1.25rem 1.55rem;
  box-shadow: 0 8px 24px rgba(20, 48, 71, 0.06);
  margin-bottom: 1rem;
}

.hero-kicker {
  display: inline-block;
  background: rgba(23, 53, 80, 0.08);
  color: var(--navy);
  border-radius: 999px;
  padding: 0.26rem 0.62rem;
  font-size: 0.82rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.hero-shell h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.04;
}

.hero-shell p {
  margin: 0.55rem 0 0 0;
  max-width: 760px;
  color: #415d73;
  font-size: 1.12rem;
}

.selection-note {
  color: var(--muted);
  margin: 0.2rem 0 0 0;
  font-size: 0.98rem;
}

.city-chip {
  display: inline-block;
  background: linear-gradient(90deg, #d96a2b 0%, #ef9f50 100%);
  color: white;
  border-radius: 999px;
  padding: 0.24rem 0.7rem;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.city-name {
  margin: 0.55rem 0 0.1rem 0;
  font-size: 1.8rem;
}

.city-meta {
  margin: 0;
  color: var(--muted);
  font-size: 1rem;
}

.photo-fallback {
  min-height: 188px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef3f7;
  border: 1px dashed #c8d8e3;
  border-radius: 18px;
  color: var(--muted);
  font-weight: 700;
}

.city-panel {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 1.2rem;
  min-height: 460px;
  height: 460px;
  box-shadow: 0 8px 24px rgba(20, 48, 71, 0.05);
}

.city-panel-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
  margin-top: 0.8rem;
}

.city-photo-box {
  width: 100%;
  height: 188px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: #eef3f7;
}

.city-photo-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.city-photo-caption {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--muted);
  font-weight: 700;
}

.city-title-wrap {
  min-width: 0;
}

div[data-testid="stImage"] img {
  border-radius: 18px;
  border: 1px solid var(--line);
  box-shadow: 0 10px 26px rgba(20, 48, 71, 0.08);
}

div[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 0.85rem 0.95rem;
  box-shadow: none;
}

div[data-testid="stMetricLabel"] {
  color: var(--muted);
}

div[data-testid="stMetricLabel"] p {
  white-space: normal;
}

div[data-testid="stMetricValue"] {
  font-size: 1.8rem;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

div[data-baseweb="select"] > div {
  border-radius: 16px;
  min-height: 3rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.95);
}

div.stButton > button {
  border-radius: 16px;
  min-height: 3rem;
  font-weight: 700;
  background: var(--navy);
  color: white;
  border: 1px solid var(--navy);
}

div.stButton > button:hover {
  background: #214261;
  color: white;
}

button[data-baseweb="tab"] {
  font-weight: 700;
}

div[data-testid="stTabs"] {
  margin-top: 0.4rem;
}

div[data-baseweb="tab-list"] {
  gap: 0.45rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0;
}

button[data-baseweb="tab"] {
  background: #eef3f7;
  color: #50697b;
  border: 1px solid var(--line);
  border-bottom: none;
  border-radius: 14px 14px 0 0;
  padding: 0.65rem 0.95rem 0.58rem 0.95rem;
}

button[data-baseweb="tab"]:hover {
  color: var(--ink);
  background: #f4f7fa;
}

button[data-baseweb="tab"][aria-selected="true"] {
  background: #ffffff;
  color: var(--ink);
  box-shadow: inset 0 -3px 0 var(--navy);
}

div[data-baseweb="tab-highlight"] {
  background: transparent !important;
}

.section-title-shell {
  margin-bottom: 0.9rem;
}

.section-title-bar {
  width: 68px;
  height: 6px;
  border-radius: 999px;
  margin-bottom: 0.55rem;
  background: var(--navy);
  display: block;
}

.section-title-text {
  font-family: 'Manrope', sans-serif;
  font-size: 2.15rem;
  font-weight: 800;
  color: var(--ink);
  line-height: 1.06;
  margin: 0;
}

.section-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1.1rem;
  margin-bottom: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-card h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.2rem;
}

.section-card p,
.section-card ul {
  color: var(--muted);
  margin-bottom: 0;
  line-height: 1.55;
}

.card-grid {
  display: grid;
  gap: 1rem;
  align-items: stretch;
  margin-bottom: 1rem;
}

.card-grid-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.card-grid-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.card-grid-4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.card-grid .section-card,
.card-grid .climate-kpi-card {
  margin-bottom: 0;
}

.climate-kpi-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1.05rem;
  margin-bottom: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.climate-kpi-title {
  color: var(--muted);
  font-weight: 800;
  font-size: 0.95rem;
  margin-bottom: 0.65rem;
}

.climate-kpi-values {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.climate-kpi-city {
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 700;
  margin-bottom: 0.15rem;
}

.climate-kpi-number {
  color: var(--ink);
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.climate-kpi-note {
  color: var(--muted);
  border-top: 1px solid var(--line);
  font-size: 0.88rem;
  margin-top: auto;
  padding-top: 0.65rem;
  line-height: 1.55;
}

.demography-kpi-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1.05rem;
  min-height: 132px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(20, 48, 71, 0.05);
}

.demography-kpi-card--left {
  border-top: 5px solid #5d84a8;
}

.demography-kpi-card--right {
  border-top: 5px solid #afc8db;
}

.demography-kpi-title {
  color: var(--muted);
  font-weight: 800;
  font-size: 0.95rem;
  margin-bottom: 0.7rem;
  line-height: 1.35;
}

.demography-kpi-number {
  color: var(--ink);
  font-family: 'Manrope', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.1;
  overflow-wrap: anywhere;
  margin-top: auto;
}

.employment-kpi-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1.05rem;
  min-height: 132px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(20, 48, 71, 0.05);
}

.employment-kpi-card--left {
  border-top: 5px solid #5c8f79;
}

.employment-kpi-card--right {
  border-top: 5px solid #bdd7cc;
}

.employment-kpi-title {
  color: var(--muted);
  font-weight: 800;
  font-size: 0.95rem;
  margin-bottom: 0.7rem;
  line-height: 1.35;
}

.employment-kpi-number {
  color: var(--ink);
  font-family: 'Manrope', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.1;
  overflow-wrap: anywhere;
  margin-top: auto;
}

.housing-kpi-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1.05rem;
  min-height: 132px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(20, 48, 71, 0.05);
}

.housing-kpi-card--left {
  border-top: 5px solid #b28661;
}

.housing-kpi-card--right {
  border-top: 5px solid #dec4af;
}

.housing-kpi-title {
  color: var(--muted);
  font-weight: 800;
  font-size: 0.95rem;
  margin-bottom: 0.7rem;
  line-height: 1.35;
}

.housing-kpi-number {
  color: var(--ink);
  font-family: 'Manrope', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.1;
  overflow-wrap: anywhere;
  margin-top: auto;
}

.detail-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: #ffffff;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.98rem;
}

.detail-table th,
.detail-table td {
  padding: 0.8rem 0.9rem;
  border-bottom: 1px solid #edf2f6;
  vertical-align: top;
  text-align: left;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.detail-table th {
  background: #f6f8fb;
  color: #3f586d;
  font-weight: 700;
}

.detail-table td:first-child {
  font-weight: 700;
  color: var(--ink);
}

.cell-a-soft {
  background: #fff9f3;
}

.cell-b-soft {
  background: #f7fbff;
}

.cell-pos-soft {
  background: #f4fbf4;
}

.cell-neg-soft {
  background: #fff6f4;
}

.city-quicklist {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.7rem 1rem;
  margin-top: 0.95rem;
}

.city-quickitem {
  border-top: 1px solid #e8eef3;
  padding-top: 0.55rem;
  min-width: 0;
}

.city-quicklabel {
  display: block;
  color: var(--muted);
  font-size: 0.94rem;
  margin-bottom: 0.2rem;
}

.city-quickvalue {
  display: block;
  color: var(--ink);
  font-family: 'Manrope', sans-serif;
  font-size: 1.22rem;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

div[data-testid="stExpander"] summary {
  min-height: 52px !important;
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
}

div[data-testid="stExpander"] summary p {
  margin: 0 !important;
  padding: 0 !important;
  line-height: 1.2 !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
}

@media (max-width: 980px) {
  .city-panel {
    height: auto;
    min-height: 0;
  }

  .city-panel-grid {
    grid-template-columns: 1fr;
  }

  .climate-kpi-values {
    grid-template-columns: 1fr;
  }

  .card-grid-2,
  .card-grid-3,
  .card-grid-4 {
    grid-template-columns: 1fr;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )



# -----------------------------------------------------------------------------
# 3. Helpers métier et formatage
# -----------------------------------------------------------------------------
# Ces fonctions préparent les valeurs réutilisées par l'interface : formatage,
# synthèses textuelles, tables longues pour les graphiques et petites règles métier.

def nombre_fr(value: Any, decimals: int = 0) -> str:
    """Formate un nombre selon l'écriture française."""
    if value is None or pd.isna(value):
        return "N/D"
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.replace(",", " ").replace(".", ",")


def formater_indicateur(value: Any, unit: str, decimals: int) -> str:
    """Formate une valeur avec son unité pour les cartes et tableaux."""
    if value is None or pd.isna(value):
        return "N/D"
    suffix = f" {unit}".strip()
    if suffix:
        return f"{nombre_fr(value, decimals)} {suffix}"
    return nombre_fr(value, decimals)


def numerique(value: Any) -> float | None:
    """Convertit une valeur en nombre ou renvoie None si elle est absente."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def flottant_securise(value: float | int | None) -> float | None:
    """Convertit une valeur en flottant quand elle est disponible."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def ecart_indicateur(valeur_gauche: float | int | None, valeur_droite: float | int | None, unit: str = "", decimals: int = 0) -> str:
    """Calcule l'écart absolu entre deux valeurs et le formate."""
    if pd.isna(valeur_gauche) or pd.isna(valeur_droite):
        return "N/D"
    delta = abs(float(valeur_droite) - float(valeur_gauche))
    formatted = f"{delta:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {unit}".strip()


def ecart_relatif_indicateur(reference_value: float | int | None, compared_value: float | int | None, decimals: int = 1) -> str:
    """Calcule un écart relatif en pourcentage par rapport à une référence."""
    if pd.isna(reference_value) or pd.isna(compared_value) or float(reference_value) == 0:
        return "N/D"
    delta = abs(float(compared_value) - float(reference_value)) / abs(float(reference_value)) * 100
    formatted = f"{delta:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} %"


def texte_comparaison(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    column: str,
    higher_is_better: bool,
    best_description: str,
    unit: str = "",
    decimals: int = 0,
) -> str:
    """Construit une phrase simple indiquant quelle ville est la mieux placée."""
    valeur_gauche = ville_gauche.get(column)
    valeur_droite = ville_droite.get(column)
    if pd.isna(valeur_gauche) or pd.isna(valeur_droite):
        return "Indicateur indisponible."
    if valeur_gauche == valeur_droite:
        return f"Les deux villes sont au même niveau pour {best_description}."

    if higher_is_better:
        winner = ville_gauche["LIBGEO"] if valeur_gauche > valeur_droite else ville_droite["LIBGEO"]
        other = ville_droite["LIBGEO"] if valeur_gauche > valeur_droite else ville_gauche["LIBGEO"]
    else:
        winner = ville_gauche["LIBGEO"] if valeur_gauche < valeur_droite else ville_droite["LIBGEO"]
        other = ville_droite["LIBGEO"] if valeur_gauche < valeur_droite else ville_gauche["LIBGEO"]

    return f"{winner} a {best_description}. Différence avec {other}: {ecart_indicateur(valeur_gauche, valeur_droite, unit, decimals)}."


def texte_synthese_previsions(tableau_previsions: pd.DataFrame) -> str:
    """Résume les prévisions météo sur sept jours dans une phrase courte."""

    def one_decimal(value: float) -> str:
        return f"{value:.1f}".replace(".", ",")

    avg_tmin = tableau_previsions["temperature_2m_min"].mean()
    avg_tmax = tableau_previsions["temperature_2m_max"].mean()
    total_rain = tableau_previsions["precipitation_sum"].sum()
    dominant_weather = tableau_previsions["meteo"].mode().iloc[0] if not tableau_previsions["meteo"].mode().empty else "N/D"
    rain_probability = tableau_previsions.get("precipitation_probability_max")
    wind_speed = tableau_previsions.get("wind_speed_10m_max")

    extra_parts: list[str] = []
    if rain_probability is not None and not rain_probability.dropna().empty:
        extra_parts.append(f"Risque de pluie maximal : {one_decimal(rain_probability.max())} %.")
    if wind_speed is not None and not wind_speed.dropna().empty:
        extra_parts.append(f"Vent maximal prévu : {one_decimal(wind_speed.max())} km/h.")

    return (
        f"Température moyenne prévue : {one_decimal(avg_tmin)} °C à {one_decimal(avg_tmax)} °C. "
        f"Pluie cumulée prévue : {one_decimal(total_rain)} mm. "
        f"Tendance dominante : {dominant_weather}. "
        + " ".join(extra_parts)
    )


def tableau_indicateur_previsions(
    previsions_gauche: pd.DataFrame,
    previsions_droite: pd.DataFrame,
    city_left_name: str,
    city_right_name: str,
    column: str,
) -> pd.DataFrame:
    """Prépare une mesure météo à sept jours pour un graphique comparatif."""
    if column not in previsions_gauche.columns or column not in previsions_droite.columns:
        return pd.DataFrame(columns=["Indicateur", "Ville", "Valeur"])

    libelles_gauche = previsions_gauche["date"].dt.strftime("%d/%m").tolist()
    libelles_droite = previsions_droite["date"].dt.strftime("%d/%m").tolist()
    return pd.DataFrame(
        {
            "Indicateur": libelles_gauche + libelles_droite,
            "Ville": [city_left_name] * len(libelles_gauche) + [city_right_name] * len(libelles_droite),
            "Valeur": previsions_gauche[column].tolist() + previsions_droite[column].tolist(),
        }
    )


def indicateurs_synthese_climat(
    tableau_temperature_climat: pd.DataFrame,
    tableau_pluie_climat: pd.DataFrame,
    city_left_name: str,
    city_right_name: str,
) -> list[dict[str, object]]:
    """Calcule les KPI lisibles à partir du climat des douze derniers mois."""
    temperature_gauche = tableau_temperature_climat[city_left_name].mean()
    temperature_droite = tableau_temperature_climat[city_right_name].mean()
    serie_temperature_gauche = tableau_temperature_climat[city_left_name].copy()
    serie_temperature_droite = tableau_temperature_climat[city_right_name].copy()
    total_pluie_gauche = tableau_pluie_climat[city_left_name].sum(min_count=1)
    total_pluie_droite = tableau_pluie_climat[city_right_name].sum(min_count=1)
    amplitude_gauche = serie_temperature_gauche.max() - serie_temperature_gauche.min()
    amplitude_droite = serie_temperature_droite.max() - serie_temperature_droite.min()

    return [
        {
            "title": "Température moyenne sur 12 mois",
            "valeur_gauche": temperature_gauche,
            "valeur_droite": temperature_droite,
            "unit": "°C",
            "decimals": 1,
            "leader_text": "Température moyenne la plus élevée",
        },
        {
            "title": "Précipitations cumulées sur 12 mois",
            "valeur_gauche": total_pluie_gauche,
            "valeur_droite": total_pluie_droite,
            "unit": "mm",
            "decimals": 0,
            "leader_text": "Cumul de pluie le plus élevé",
        },
        {
            "title": "Amplitude thermique sur 12 mois",
            "valeur_gauche": amplitude_gauche,
            "valeur_droite": amplitude_droite,
            "unit": "°C",
            "decimals": 1,
            "leader_text": "Écart chaud/froid le plus marqué",
            "help": "Écart entre le mois moyen le plus chaud et le mois moyen le plus froid.",
        },
    ]


def tableau_long_depuis_specs(ville_gauche: pd.Series, ville_droite: pd.Series, specs: list[dict[str, object]]) -> pd.DataFrame:
    """Transforme une liste d'indicateurs en tableau long utilisable par Altair."""
    rows: list[dict[str, object]] = []
    for index, spec in enumerate(specs):
        label = str(spec["label"])
        valeur_gauche = flottant_securise(ville_gauche.get(str(spec["column"])))
        valeur_droite = flottant_securise(ville_droite.get(str(spec["column"])))
        if valeur_gauche is not None:
            rows.append({"Indicateur": label, "Ville": ville_gauche["LIBGEO"], "Valeur": valeur_gauche, "Ordre": index})
        if valeur_droite is not None:
            rows.append({"Indicateur": label, "Ville": ville_droite["LIBGEO"], "Valeur": valeur_droite, "Ordre": index})
    return pd.DataFrame(rows)


def tableau_long_depuis_tableau_indexe(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit un tableau indexé en format long pour les graphiques de climat."""
    if df.empty:
        return pd.DataFrame(columns=["Indicateur", "Ville", "Valeur"])
    frame = df.reset_index()
    first_column = frame.columns[0]
    return frame.rename(columns={first_column: "Indicateur"}).melt(
        id_vars="Indicateur",
        var_name="Ville",
        value_name="Valeur",
    ).dropna()


def points_villes_selectionnees(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    contexte_gauche: dict[str, object] | None,
    contexte_droite: dict[str, object] | None,
) -> pd.DataFrame:
    """Prépare les coordonnées des deux villes sélectionnées pour la carte."""
    rows: list[dict[str, object]] = []
    for city, context in ((ville_gauche, contexte_gauche), (ville_droite, contexte_droite)):
        if context is None or context.get("lat") is None or context.get("lon") is None:
            continue
        rows.append(
            {
                "Ville": city["LIBGEO"],
                "Latitude": float(context["lat"]),
                "Longitude": float(context["lon"]),
            }
        )
    return pd.DataFrame(rows)


def age_moyen_estime(city: pd.Series) -> float | None:
    """Estime l'âge moyen à partir des tranches d'âge."""
    age_bins = [
        ("P22_POP0014", 7),
        ("P22_POP1529", 22),
        ("P22_POP3044", 37),
        ("P22_POP4559", 52),
        ("P22_POP6074", 67),
        ("P22_POP7589", 82),
        ("P22_POP90P", 95),
    ]

    total_pop = 0.0
    weighted_sum = 0.0

    for column, midpoint in age_bins:
        value = flottant_securise(city.get(column))
        if value is None:
            continue
        total_pop += value
        weighted_sum += value * midpoint

    if total_pop == 0:
        return None

    return weighted_sum / total_pop


def libelle_gagnant(ville_gauche: pd.Series, ville_droite: pd.Series, column: str, higher_is_better: bool) -> str:
    """Renvoie la ville gagnante sur un indicateur simple."""
    valeur_gauche = ville_gauche.get(column)
    valeur_droite = ville_droite.get(column)

    if pd.isna(valeur_gauche) or pd.isna(valeur_droite):
        return "Indisponible"
    if valeur_gauche == valeur_droite:
        return "Égalité"
    if higher_is_better:
        return ville_gauche["LIBGEO"] if valeur_gauche > valeur_droite else ville_droite["LIBGEO"]
    return ville_gauche["LIBGEO"] if valeur_gauche < valeur_droite else ville_droite["LIBGEO"]


def _convertir_serie_numerique(series: pd.Series) -> pd.Series:
    """Convertit une série texte en série numérique."""
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def _requete(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = 20, raise_for_status: bool = True) -> requests.Response | None:
    """Exécute une requête GET avec journalisation homogène des erreurs."""
    try:
        response = SESSION_HTTP.get(url, params=params, headers=headers, timeout=timeout)
        if raise_for_status:
            response.raise_for_status()
        return response
    except requests.RequestException as exc:
        JOURNAL.warning("HTTP request failed for %s: %s", url, exc)
        return None


def _reponse_json(response: requests.Response, url: str) -> Any | None:
    """Décode une réponse JSON et journalise les erreurs éventuelles."""
    try:
        return response.json()
    except ValueError as exc:
        JOURNAL.warning("Invalid JSON response for %s: %s", url, exc)
        return None


@st.cache_data(show_spinner=False)

# -----------------------------------------------------------------------------
# 4. Chargement et préparation des données locales
# -----------------------------------------------------------------------------
# Cette partie lit les fichiers fournis, fait les jointures avec CODGEO, convertit
# les colonnes numériques et crée les indicateurs calculés utilisés dans l’app.

def charger_noms_villes() -> pd.DataFrame:
    """Charge les noms de communes depuis le fichier Excel fourni."""
    # Sur OneDrive, le fichier Excel peut parfois être verrouillé. Dans ce cas,
    # on crée une copie temporaire pour réussir la lecture.
    copied_file: Path | None = None
    try:
        tableau_villes = pd.read_excel(FICHIER_VILLES, usecols=["CODGEO", "LIBGEO"])
    except PermissionError:
        copied_file = FICHIER_VILLES.with_name(f"{FICHIER_VILLES.stem}_copy.xlsx")
        shutil.copy(FICHIER_VILLES, copied_file)
        tableau_villes = pd.read_excel(copied_file, usecols=["CODGEO", "LIBGEO"])
    finally:
        if copied_file is not None and copied_file.exists():
            copied_file.unlink()

    tableau_villes["CODGEO"] = tableau_villes["CODGEO"].astype(str).str.zfill(5)
    tableau_villes["LIBGEO"] = tableau_villes["LIBGEO"].astype(str).str.strip()
    return tableau_villes


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def charger_indicateurs_loyer() -> pd.DataFrame:
    """Télécharge les loyers d'annonce au m² par commune depuis data.gouv.fr."""
    tableau_vide = pd.DataFrame(
        columns=["CODGEO", "loyer_m2_appartement", "loyer_m2_bas", "loyer_m2_haut", "nbobs_loyer"]
    )
    try:
        rent_df = pd.read_csv(
            URL_LOYERS_APPARTEMENTS,
            sep=";",
            encoding="latin1",
            usecols=["INSEE_C", "loypredm2", "lwr.IPm2", "upr.IPm2", "nbobs_com"],
            dtype={"INSEE_C": str},
            low_memory=False,
        )
    except Exception as exc:
        JOURNAL.warning("Unable to load rent indicators: %s", exc)
        return tableau_vide

    rent_df = rent_df.rename(
        columns={
            "INSEE_C": "CODGEO",
            "loypredm2": "loyer_m2_appartement",
            "lwr.IPm2": "loyer_m2_bas",
            "upr.IPm2": "loyer_m2_haut",
            "nbobs_com": "nbobs_loyer",
        }
    )
    rent_df["CODGEO"] = rent_df["CODGEO"].astype(str).str.zfill(5)
    rent_df["CODGEO"] = rent_df["CODGEO"].replace(REMPLACEMENTS_CODES_COMMUNES)

    for column in ["loyer_m2_appartement", "loyer_m2_bas", "loyer_m2_haut"]:
        rent_df[column] = _convertir_serie_numerique(rent_df[column])
    rent_df["nbobs_loyer"] = _convertir_serie_numerique(rent_df["nbobs_loyer"]).fillna(0)
    rent_df = rent_df.dropna(subset=["CODGEO", "loyer_m2_appartement"])
    if rent_df.empty:
        return tableau_vide

    rent_df["weighted_rent_value"] = rent_df["loyer_m2_appartement"] * rent_df["nbobs_loyer"]
    aggregated = rent_df.groupby("CODGEO", as_index=False).agg(
        weighted_rent_value=("weighted_rent_value", "sum"),
        loyer_m2_appartement_mean=("loyer_m2_appartement", "mean"),
        loyer_m2_bas=("loyer_m2_bas", "mean"),
        loyer_m2_haut=("loyer_m2_haut", "mean"),
        nbobs_loyer=("nbobs_loyer", "sum"),
    )
    weighted_rent = aggregated["weighted_rent_value"] / aggregated["nbobs_loyer"].where(aggregated["nbobs_loyer"] > 0)
    aggregated["loyer_m2_appartement"] = weighted_rent.fillna(aggregated["loyer_m2_appartement_mean"])

    return aggregated[["CODGEO", "loyer_m2_appartement", "loyer_m2_bas", "loyer_m2_haut", "nbobs_loyer"]]


@st.cache_data(show_spinner=False)
def charger_jeu_donnees_villes() -> pd.DataFrame:
    """Charge, joint et prépare toutes les données locales des villes."""
    base_df = pd.read_csv(
        FICHIER_BASE,
        sep=";",
        usecols=COLONNES_BASE,
        dtype={"CODGEO": str},
        low_memory=False,
    )
    base_df["CODGEO"] = base_df["CODGEO"].str.zfill(5)

    # Le fichier complémentaire peut varier : on vérifie d’abord quelles colonnes
    # existent réellement avant de les charger.
    colonnes_entete = pd.read_csv(FICHIER_COMPLET, sep=";", nrows=0).columns.tolist()
    colonnes_complementaires_disponibles = [col for col in COLONNES_COMPLEMENTAIRES if col in colonnes_entete]

    comp_df = pd.read_csv(
        FICHIER_COMPLET,
        sep=";",
        usecols=colonnes_complementaires_disponibles,
        dtype={"CODGEO": str},
        low_memory=False,
    )
    comp_df["CODGEO"] = comp_df["CODGEO"].str.zfill(5)

    noms_villes = charger_noms_villes()
    rent_df = charger_indicateurs_loyer()
    df = (
        base_df
        .merge(noms_villes, on="CODGEO", how="left")
        .merge(comp_df, on="CODGEO", how="left")
        .merge(rent_df, on="CODGEO", how="left")
    )

    df = df[df["LIBGEO"].notna()].copy()
    df = df[df["P22_POP"] >= 20000].copy()

    colonnes_numeriques = [col for col in df.columns if col not in {"CODGEO", "LIBGEO", "PIMP21"}]
    for col in colonnes_numeriques:
        df[col] = _convertir_serie_numerique(df[col])
    df["PIMP21"] = _convertir_serie_numerique(df["PIMP21"])

    df["densite_pop"] = df["P22_POP"] / df["SUPERF"]
    df["taille_menage"] = df["P22_POP"] / df["P22_MEN"]
    df["taux_activite"] = (df["P22_ACT1564"] / df["P22_POP1564"]) * 100
    df["taux_chomage"] = (df["P22_CHOM1564"] / df["P22_ACT1564"]) * 100
    df["taux_logements_vacants"] = (df["P22_LOGVAC"] / df["P22_LOG"]) * 100
    df["taux_proprietaires"] = (df["P22_RP_PROP"] / df["P22_RP"]) * 100
    df["part_emplois_salaries"] = (df["P22_EMPLT_SAL"] / df["P22_EMPLT"].where(df["P22_EMPLT"] != 0)) * 100
    df["city_label"] = df["LIBGEO"] + " (" + df["CODGEO"] + ")"

    return df.sort_values(["LIBGEO", "CODGEO"]).reset_index(drop=True)


@st.cache_data(ttl=24 * 3600, show_spinner=False)

# -----------------------------------------------------------------------------
# 5. Appels aux APIs externes
# -----------------------------------------------------------------------------
# Les fonctions suivantes récupèrent les informations qui ne sont pas dans les
# fichiers locaux : contexte géographique, images, météo et climat.

def recuperer_contexte_ville(codgeo: str) -> dict[str, Any] | None:
    """Récupère le département, la région et les coordonnées d'une commune."""
    url = f"https://geo.api.gouv.fr/communes/{codgeo}"
    params = {
        "fields": "nom,code,population,centre,departement,region",
        "format": "json",
        "geometry": "centre",
    }
    response = _requete(url, params=params, timeout=20)
    if response is None:
        return None
    payload = _reponse_json(response, url)
    if payload is None:
        return None

    coordinates = payload.get("centre", {}).get("coordinates", [None, None])
    lon, lat = coordinates[0], coordinates[1]
    if lat is None or lon is None:
        return None

    return {
        "lat": float(lat),
        "lon": float(lon),
        "departement": payload.get("departement", {}).get("nom"),
        "region": payload.get("region", {}).get("nom"),
        "population_api": payload.get("population"),
    }


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def recuperer_image_ville(city_name: str) -> dict[str, str] | None:
    """Récupère une image de la ville depuis Wikipédia quand elle existe."""
    summary_url = f"https://fr.wikipedia.org/api/rest_v1/page/summary/{quote(city_name.replace(' ', '_'))}"
    summary_response = _requete(summary_url, headers=EN_TETES_HTTP, timeout=20, raise_for_status=False)
    if summary_response is not None and summary_response.ok:
        payload = _reponse_json(summary_response, summary_url)
        if payload is not None:
            thumbnail = (payload.get("thumbnail") or {}).get("source")
            page_url = (payload.get("content_urls") or {}).get("desktop", {}).get("page", "")
            if thumbnail:
                return {"image_url": thumbnail, "page_url": page_url, "source": "Wikipedia"}

    params = {
        "action": "query",
        "format": "json",
        "redirects": 1,
        "prop": "pageimages|info",
        "piprop": "thumbnail",
        "pithumbsize": 640,
        "inprop": "url",
        "titles": city_name,
    }
    fallback_url = "https://fr.wikipedia.org/w/api.php"
    response = _requete(fallback_url, params=params, headers=EN_TETES_HTTP, timeout=20)
    if response is None:
        return None
    payload = _reponse_json(response, fallback_url)
    if payload is None:
        return None
    pages = payload.get("query", {}).get("pages", {})
    for page in pages.values():
        thumbnail = (page.get("thumbnail") or {}).get("source")
        page_url = page.get("fullurl", "")
        if thumbnail:
            return {"image_url": thumbnail, "page_url": page_url, "source": "Wikipedia"}

    return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def recuperer_previsions(lat: float, lon: float) -> pd.DataFrame | None:
    """Récupère les prévisions météo à sept jours avec Open-Meteo."""
    # Paramètres demandés à Open-Meteo pour la météo des sept prochains jours.
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,weathercode",
        "forecast_days": 7,
        "timezone": "Europe/Paris",
        "wind_speed_unit": "kmh",
    }
    url = "https://api.open-meteo.com/v1/forecast"
    response = _requete(url, params=params, timeout=25)
    if response is None:
        return None
    payload = _reponse_json(response, url)
    if payload is None:
        return None
    daily = payload.get("daily", {})

    if not daily:
        return None

    tableau_previsions = pd.DataFrame(daily)
    if tableau_previsions.empty:
        return None

    tableau_previsions["date"] = pd.to_datetime(tableau_previsions["time"])
    tableau_previsions["meteo"] = tableau_previsions["weathercode"].map(LIBELLES_CODES_METEO).fillna("N/D")
    return tableau_previsions


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def recuperer_climat_mensuel(lat: float, lon: float, reference_date: str | None = None) -> pd.DataFrame | None:
    """Calcule les valeurs mensuelles sur douze mois glissants jusqu'à aujourd'hui."""
    current_date = pd.to_datetime(reference_date).date() if reference_date else date.today()
    current_month_start = date(current_date.year, current_date.month, 1)
    start_date = (pd.Timestamp(current_month_start) - pd.DateOffset(months=11)).date()

    # L'archive Open-Meteo peut avoir un léger délai de disponibilité. On tente
    # donc aujourd'hui, puis quelques dates plus anciennes si l'API ne répond pas.
    candidate_end_dates = [
        current_date,
        current_date - timedelta(days=1),
        current_date - timedelta(days=3),
        current_date - timedelta(days=7),
        current_date - timedelta(days=14),
    ]

    tableau_climat = pd.DataFrame()
    for end_date in candidate_end_dates:
        if end_date < start_date:
            continue

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "Europe/Paris",
        }
        url = "https://archive-api.open-meteo.com/v1/archive"
        response = _requete(url, params=params, timeout=45)
        if response is None:
            continue
        payload = _reponse_json(response, url)
        if payload is None:
            continue
        daily = payload.get("daily", {})

        tableau_climat = pd.DataFrame(daily)
        if not tableau_climat.empty:
            break

    if tableau_climat.empty:
        return None

    tableau_climat["date"] = pd.to_datetime(tableau_climat["time"])
    tableau_climat["month_start"] = tableau_climat["date"].dt.to_period("M").dt.to_timestamp()
    tableau_climat["year"] = tableau_climat["date"].dt.year
    tableau_climat["month"] = tableau_climat["date"].dt.month

    # Les données sont agrégées mois par mois sur une fenêtre glissante de douze
    # mois. Le mois courant peut donc être partiel, car il s'arrête à aujourd'hui
    # ou à la dernière date disponible dans Open-Meteo.
    monthly_normals = (
        tableau_climat.groupby(["month_start", "month"], as_index=False)
        .agg(
            temperature_moyenne=("temperature_2m_mean", "mean"),
            precipitation_moyenne=("precipitation_sum", "sum"),
        )
        .copy()
    )
    monthly_normals["mois"] = monthly_normals["month"].map(LIBELLES_MOIS)
    return monthly_normals.sort_values("month_start")



# -----------------------------------------------------------------------------
# 6. Tableaux de comparaison et export
# -----------------------------------------------------------------------------
def construire_tableau_detail(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    metrics: list[dict[str, Any]],
) -> pd.DataFrame:
    """Construit le tableau détaillé de comparaison pour une liste d'indicateurs."""
    rows: list[dict[str, Any]] = []

    for metric in metrics:
        label = metric["label"]
        column = metric["column"]
        unit = metric.get("unit", "")
        decimals = metric.get("decimals", 0)
        prefer = metric.get("prefer")

        brut_gauche = ville_gauche.get(column)
        brut_droite = ville_droite.get(column)
        nombre_gauche = numerique(brut_gauche)
        nombre_droite = numerique(brut_droite)

        # _better est une information interne : elle sert seulement à colorer la
        # meilleure cellule du tableau, elle n’est pas affichée à l’utilisateur.
        better = None
        if nombre_gauche is not None and nombre_droite is not None and prefer in {"higher", "lower"} and nombre_gauche != nombre_droite:
            if prefer == "higher":
                better = "A" if nombre_gauche > nombre_droite else "B"
            else:
                better = "A" if nombre_gauche < nombre_droite else "B"

        # L’écart du tableau garde le sens B-A pour permettre une vérification
        # précise, alors que les cartes de synthèse affichent des écarts absolus.
        delta = None if nombre_gauche is None or nombre_droite is None else nombre_droite - nombre_gauche

        rows.append(
            {
                "Indicateur": label,
                ville_gauche["LIBGEO"]: formater_indicateur(brut_gauche, unit, decimals),
                ville_droite["LIBGEO"]: formater_indicateur(brut_droite, unit, decimals),
                "Écart (B-A)": formater_indicateur(delta, unit, decimals),
                "_better": better,
            }
        )

    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# 7. Préparation des données météo et climat pour l’affichage
# -----------------------------------------------------------------------------
# Ces fonctions transforment les données brutes Open-Meteo en tableaux lisibles
# pour Streamlit et en matrices faciles à convertir en graphiques.

def previsions_vers_tableau_affichage(tableau_previsions: pd.DataFrame) -> pd.DataFrame:
    """Prépare les prévisions météo dans un tableau lisible."""
    table = pd.DataFrame(
        {
            "Date": tableau_previsions["date"].dt.strftime("%d/%m/%Y"),
            "Tmin (°C)": tableau_previsions["temperature_2m_min"],
            "Tmax (°C)": tableau_previsions["temperature_2m_max"],
            "Pluie (mm)": tableau_previsions["precipitation_sum"],
            "Météo": tableau_previsions["meteo"],
        }
    )
    # Ces colonnes dépendent de l'API Open-Meteo. On les ajoute seulement si
    # elles sont présentes pour éviter de bloquer l'application.
    if "precipitation_probability_max" in tableau_previsions.columns:
        table["Risque de pluie (%)"] = tableau_previsions["precipitation_probability_max"]
    if "wind_speed_10m_max" in tableau_previsions.columns:
        table["Vent max (km/h)"] = tableau_previsions["wind_speed_10m_max"]
    return table


def tableaux_comparaison_climat(
    city_left_name: str,
    city_right_name: str,
    climat_gauche: pd.DataFrame,
    climat_droite: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prépare les tableaux mensuels de température et de précipitations."""
    # Les deux villes sont placées dans les colonnes d’un même tableau pour que
    # app.py puisse ensuite les convertir en graphique comparatif.
    month_order = climat_gauche.sort_values("month_start")["mois"].tolist()
    temp_df = pd.DataFrame(
        {
            city_left_name: climat_gauche.set_index("mois")["temperature_moyenne"],
            city_right_name: climat_droite.set_index("mois")["temperature_moyenne"],
        }
    ).reindex(month_order)

    rain_df = pd.DataFrame(
        {
            city_left_name: climat_gauche.set_index("mois")["precipitation_moyenne"],
            city_right_name: climat_droite.set_index("mois")["precipitation_moyenne"],
        }
    ).reindex(month_order)

    return temp_df, rain_df
