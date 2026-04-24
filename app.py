"""Application principale Streamlit du comparateur de villes.

Ce fichier construit l'interface visible par l'utilisateur : choix des deux villes,
onglets d'analyse, graphiques, cartes de synthèse et tableaux détaillés.
Les calculs lourds, le chargement des données et les appels aux APIs sont placés
dans app_core.py pour garder cette page lisible.
"""

from __future__ import annotations

import html
from typing import Any

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_core import (
    construire_tableau_detail,
    tableaux_comparaison_climat,
    indicateurs_synthese_climat,
    texte_comparaison,
    age_moyen_estime,
    recuperer_contexte_ville,
    recuperer_image_ville,
    recuperer_previsions,
    recuperer_climat_mensuel,
    tableau_indicateur_previsions,
    texte_synthese_previsions,
    previsions_vers_tableau_affichage,
    formater_indicateur,
    charger_jeu_donnees_villes,
    tableau_long_depuis_specs,
    tableau_long_depuis_tableau_indexe,
    ecart_indicateur,
    ecart_relatif_indicateur,
    flottant_securise,
    points_villes_selectionnees,
    configurer_page,
    libelle_gagnant,
)


def afficher_hero(title: str, subtitle: str) -> None:
    """Affiche le bloc d'en-tête principal de l'application."""
    st.markdown(
        f"""
<div class="hero-shell">
  <div class="hero-kicker">Comparaison de villes françaises</div>
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(subtitle)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _resoudre_indice_defaut(options: list[str], key: str, fallback_label: str) -> int:
    """Retrouve l'indice par défaut d'une ville dans une liste de sélection."""
    current_value = st.session_state.get(key)
    if current_value in options:
        return options.index(current_value)
    if fallback_label in options:
        return options.index(fallback_label)
    return 0


def obtenir_villes_selectionnees(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, dict[str, Any] | None, dict[str, Any] | None]:
    """Affiche les sélecteurs de villes et renvoie les deux villes choisies."""
    libelles_villes = df["city_label"].tolist()
    indice_gauche = _resoudre_indice_defaut(libelles_villes, "city_left_label", "Paris (75056)")
    indice_droite = _resoudre_indice_defaut(libelles_villes, "city_right_label", "Lyon (69123)")

    with st.container(border=True):
        st.markdown("### Choisir les villes")
        col_left, col_right = st.columns(2)
        with col_left:
            st.selectbox("Ville A", libelles_villes, index=indice_gauche, key="city_left_label")
        with col_right:
            st.selectbox("Ville B", libelles_villes, index=indice_droite, key="city_right_label")

        st.markdown(
            f'<p class="selection-note">Filtre appliqué: communes de plus de 20 000 habitants. '
            f"{len(libelles_villes)} villes comparables disponibles.</p>",
            unsafe_allow_html=True,
        )

    libelle_gauche = st.session_state["city_left_label"]
    libelle_droite = st.session_state["city_right_label"]

    if libelle_gauche == libelle_droite:
        st.warning("Sélectionne deux villes différentes.")
        st.stop()

    ville_gauche = df.loc[df["city_label"] == libelle_gauche].iloc[0]
    ville_droite = df.loc[df["city_label"] == libelle_droite].iloc[0]
    contexte_gauche = recuperer_contexte_ville(ville_gauche["CODGEO"])
    contexte_droite = recuperer_contexte_ville(ville_droite["CODGEO"])

    return ville_gauche, ville_droite, contexte_gauche, contexte_droite


def afficher_tableau_detail_html(df: pd.DataFrame, city_left_name: str, city_right_name: str) -> str:
    """Transforme le tableau détaillé en HTML avec une mise en valeur douce."""
    headers = ["Indicateur", city_left_name, city_right_name, "Écart (B-A)"]
    lignes_html_liste: list[str] = []

    for _, row in df.iterrows():
        better = row["_better"]
        class_left = ""
        class_right = ""
        class_diff = ""

        if better == "A":
            class_left = ' class="cell-a-soft"'
        elif better == "B":
            class_right = ' class="cell-b-soft"'

        diff_value = str(row["Écart (B-A)"])
        if diff_value.startswith("+"):
            class_diff = ' class="cell-pos-soft"'
        elif diff_value.startswith("-"):
            class_diff = ' class="cell-neg-soft"'

        lignes_html_liste.append(
            "<tr>"
            f"<td>{html.escape(str(row['Indicateur']))}</td>"
            f"<td{class_left}>{html.escape(str(row[city_left_name]))}</td>"
            f"<td{class_right}>{html.escape(str(row[city_right_name]))}</td>"
            f"<td{class_diff}>{html.escape(str(row['Écart (B-A)']))}</td>"
            "</tr>"
        )

    entete_html = "".join(f"<th>{html.escape(col)}</th>" for col in headers)
    lignes_html = "".join(lignes_html_liste)

    return (
        '<div class="detail-table-wrap">'
        '<table class="detail-table">'
        f"<thead><tr>{entete_html}</tr></thead>"
        f"<tbody>{lignes_html}</tbody>"
        "</table>"
        "</div>"
    )


def afficher_carte_ville(city: pd.Series, context: dict[str, Any] | None, badge: str) -> None:
    """Affiche la carte visuelle d'une ville avec image et indicateurs rapides."""
    geography = "N/D"
    if context is not None:
        geography = f"{context.get('departement', 'N/D')} - {context.get('region', 'N/D')}"

    donnees_image = recuperer_image_ville(str(city["LIBGEO"]))
    if donnees_image is not None:
        marquage_image = (
            f'<div class="city-photo-box"><img src="{html.escape(donnees_image["image_url"])}" '
            f'alt="Photo de {html.escape(str(city["LIBGEO"]))}"></div>'
        )
    else:
        marquage_image = '<div class="city-photo-box"><div class="city-photo-caption">Image indisponible</div></div>'

    st.markdown(
        f"""
<div class="city-panel">
  <span class="city-chip">{html.escape(badge)}</span>
  <div class="city-panel-grid">
    <div>{marquage_image}</div>
    <div class="city-title-wrap">
      <h3 class="city-name">{html.escape(str(city["LIBGEO"]))}</h3>
      <p class="city-meta">{html.escape(geography)}</p>
      <p class="city-meta">Code INSEE: {html.escape(str(city["CODGEO"]))}</p>
      <div class="city-quicklist">
        <div class="city-quickitem">
          <span class="city-quicklabel">Population</span>
          <span class="city-quickvalue">{html.escape(formater_indicateur(city.get("P22_POP"), "hab", 0))}</span>
        </div>
        <div class="city-quickitem">
          <span class="city-quicklabel">Revenu médian</span>
          <span class="city-quickvalue">{html.escape(formater_indicateur(city.get("MED21"), "EUR", 0))}</span>
        </div>
        <div class="city-quickitem">
          <span class="city-quicklabel">Taux de chômage</span>
          <span class="city-quickvalue">{html.escape(formater_indicateur(city.get("taux_chomage"), "%", 1))}</span>
        </div>
        <div class="city-quickitem">
          <span class="city-quicklabel">Loyer moyen</span>
          <span class="city-quickvalue">{html.escape(formater_indicateur(city.get("loyer_m2_appartement"), "EUR/m²", 1))}</span>
        </div>
      </div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def afficher_duo_villes(ville_gauche: pd.Series, ville_droite: pd.Series, contexte_gauche: dict[str, Any] | None, contexte_droite: dict[str, Any] | None) -> None:
    """Affiche les deux cartes de villes en haut de l'application."""
    colonne_gauche, colonne_droite = st.columns(2)
    with colonne_gauche:
        afficher_carte_ville(ville_gauche, contexte_gauche, "Ville A")
    with colonne_droite:
        afficher_carte_ville(ville_droite, contexte_droite, "Ville B")


def carte_kpi_demographie_html(title: str, value: str, side: str) -> str:
    """Construit une carte KPI colorée pour l'onglet démographique."""
    side_class = "demography-kpi-card--left" if side == "left" else "demography-kpi-card--right"
    return f"""
<div class="demography-kpi-card {side_class}">
  <div class="demography-kpi-title">{html.escape(title)}</div>
  <div class="demography-kpi-number">{html.escape(value)}</div>
</div>
"""


def afficher_carte_kpi_demographie(title: str, value: str, side: str) -> None:
    """Affiche une carte KPI colorée pour l'onglet démographique."""
    st.markdown(
        carte_kpi_demographie_html(title, value, side),
        unsafe_allow_html=True,
    )


def carte_kpi_emploi_html(title: str, value: str, side: str) -> str:
    """Construit une carte KPI colorée pour l'onglet emploi."""
    side_class = "employment-kpi-card--left" if side == "left" else "employment-kpi-card--right"
    return f"""
<div class="employment-kpi-card {side_class}">
  <div class="employment-kpi-title">{html.escape(title)}</div>
  <div class="employment-kpi-number">{html.escape(value)}</div>
</div>
"""


def afficher_carte_kpi_emploi(title: str, value: str, side: str) -> None:
    """Affiche une carte KPI colorée pour l'onglet emploi."""
    st.markdown(
        carte_kpi_emploi_html(title, value, side),
        unsafe_allow_html=True,
    )


configurer_page("Comparateur de villes françaises")


# -----------------------------------------------------------------------------
# 1. Paramètres généraux de l’interface
# -----------------------------------------------------------------------------
# Cette partie ne lance aucun calcul : elle définit les couleurs, les mois et les
# indicateurs qui seront utilisés plus bas dans les onglets. Les dictionnaires
# permettent de changer facilement un libellé, une unité ou une couleur sans
# devoir modifier toute l’application.
# Couleurs utilisées par thème pour éviter que tous les onglets aient le même aspect.
THEMES_SECTIONS = {
    "overview": {"accent": "#5b7285", "pair": ["#5f7f97", "#d6a17f"], "ligne": "#d9e2ea"},
    "démographique": {"accent": "#5b84a6", "pair": ["#5d84a8", "#afc8db"], "ligne": "#d7e5ef"},
    "emploi": {"accent": "#5c8f79", "pair": ["#5c8f79", "#bdd7cc"], "ligne": "#d8ebe3"},
    "logement": {"accent": "#b28661", "pair": ["#b28661", "#dec4af"], "ligne": "#eee2d7"},
    "meteo": {"accent": "#4f87b3", "pair": ["#4f87b3", "#aecde4"], "ligne": "#d9e8f3"},
    "complements": {"accent": "#7b7491", "pair": ["#7b7491", "#cdc4db"], "ligne": "#e6e0ef"},
}
# Ordre imposé des mois : Altair l’utilise pour ne pas trier les mois par ordre alphabétique.
ORDRE_MOIS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

# -----------------------------------------------------------------------------
# Indicateurs de l’onglet "Profil démographique"
# -----------------------------------------------------------------------------

INDICATEURS_TABLEAU_DEMOGRAPHIQUES = [
    {"label": "Population (2022)", "column": "P22_POP", "unit": "hab", "decimals": 0, "prefer": "higher"},
    {"label": "Surface", "column": "SUPERF", "unit": "km2", "decimals": 1, "prefer": "higher"},
    {"label": "Densité", "column": "densite_pop", "unit": "hab/km2", "decimals": 1, "prefer": "neutral"},
    {"label": "Revenu médian", "column": "MED21", "unit": "EUR", "decimals": 0, "prefer": "higher"},
    {"label": "Ménages", "column": "P22_MEN", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Taille moyenne du ménage", "column": "taille_menage", "unit": "pers", "decimals": 2, "prefer": "neutral"},
    {"label": "Naissances (2024)", "column": "NAISD24", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Décès (2024)", "column": "DECESD24", "unit": "", "decimals": 0, "prefer": "lower"},
]

SPECS_MENAGES_DEMOGRAPHIQUES = [
    {"label": "Personnes seules", "column": "C22_MENPSEUL", "unit": "", "decimals": 0, "prefer": "neutral"},
    {"label": "Ménages familiaux", "column": "C22_MENFAM", "unit": "", "decimals": 0, "prefer": "neutral"},
    {"label": "Couples sans enfant", "column": "C22_COUPSENF", "unit": "", "decimals": 0, "prefer": "neutral"},
    {"label": "Couples avec enfant(s)", "column": "C22_COUPAENF", "unit": "", "decimals": 0, "prefer": "neutral"},
    {"label": "Familles monoparentales", "column": "C22_FAMMONO", "unit": "", "decimals": 0, "prefer": "neutral"},
]

SPECS_PROFIL_AGE_DEMOGRAPHIQUE = [
    {"label": "0-14 ans", "column": "P22_POP0014", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "15-29 ans", "column": "P22_POP1529", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "30-44 ans", "column": "P22_POP3044", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "45-59 ans", "column": "P22_POP4559", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "60-74 ans", "column": "P22_POP6074", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "75-89 ans", "column": "P22_POP7589", "unit": "hab", "decimals": 0, "prefer": "neutral"},
    {"label": "90 ans et +", "column": "P22_POP90P", "unit": "hab", "decimals": 0, "prefer": "neutral"},
]


ORDRE_EVOLUTION_POPULATION_DEMOGRAPHIQUE = ["2011", "2016", "2022"]

INDICATEURS_TABLEAU_DEMOGRAPHIQUES_FINAL = (
    INDICATEURS_TABLEAU_DEMOGRAPHIQUES
    + SPECS_MENAGES_DEMOGRAPHIQUES
    + SPECS_PROFIL_AGE_DEMOGRAPHIQUE
)
# -----------------------------------------------------------------------------
# Indicateurs de l’onglet "Emploi"
# -----------------------------------------------------------------------------

INDICATEURS_EMPLOI = [
    {"label": "Taux d'activité", "column": "taux_activite", "unit": "%", "decimals": 1, "prefer": "higher"},
    {"label": "Taux de chômage", "column": "taux_chomage", "unit": "%", "decimals": 1, "prefer": "lower"},
    {"label": "Salaire net mensuel", "column": "SNEMM_23", "unit": "EUR", "decimals": 0, "prefer": "higher"},
    {"label": "Part d'emplois salariés", "column": "part_emplois_salaries", "unit": "%", "decimals": 1, "prefer": "higher"},
    {"label": "Emplois au lieu de travail", "column": "P22_EMPLT", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Emplois salariés", "column": "P22_EMPLT_SAL", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Établissements actifs", "column": "ETTOT24", "unit": "", "decimals": 0, "prefer": "higher"},

    {"label": "Actifs 15-64 ans (total)", "column": "P22_ACT1564", "unit": "pers", "decimals": 0, "prefer": "higher"},
    {"label": "Actifs 15-24 ans", "column": "P22_ACT1524", "unit": "pers", "decimals": 0, "prefer": "higher"},
    {"label": "Actifs 25-54 ans", "column": "P22_ACT2554", "unit": "pers", "decimals": 0, "prefer": "higher"},
    {"label": "Actifs 55-64 ans", "column": "P22_ACT5564", "unit": "pers", "decimals": 0, "prefer": "higher"},

    {"label": "Chômeurs 15-64 ans (total)", "column": "P22_CHOM1564", "unit": "pers", "decimals": 0, "prefer": "lower"},
    {"label": "Chômeurs 15-24 ans", "column": "P22_CHOM1524", "unit": "pers", "decimals": 0, "prefer": "lower"},
    {"label": "Chômeurs 25-54 ans", "column": "P22_CHOM2554", "unit": "pers", "decimals": 0, "prefer": "lower"},
    {"label": "Chômeurs 55-64 ans", "column": "P22_CHOM5564", "unit": "pers", "decimals": 0, "prefer": "lower"},
]

# -----------------------------------------------------------------------------
# Indicateurs de l’onglet "Logement"
# -----------------------------------------------------------------------------

INDICATEURS_LOGEMENT = [
    {"label": "Loyer moyen appartement", "column": "loyer_m2_appartement", "unit": "EUR/m²", "decimals": 1, "prefer": "lower"},
    {"label": "Borne basse du loyer", "column": "loyer_m2_bas", "unit": "EUR/m²", "decimals": 1, "prefer": "lower"},
    {"label": "Borne haute du loyer", "column": "loyer_m2_haut", "unit": "EUR/m²", "decimals": 1, "prefer": "lower"},
    {"label": "Nombre d'annonces utilisées", "column": "nbobs_loyer", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Taux de logements vacants", "column": "taux_logements_vacants", "unit": "%", "decimals": 1, "prefer": "lower"},
    {"label": "Taux de propriétaires", "column": "taux_proprietaires", "unit": "%", "decimals": 1, "prefer": "higher"},
    {"label": "Logements au total", "column": "P22_LOG", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Résidences principales", "column": "P22_RP", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Logements vacants", "column": "P22_LOGVAC", "unit": "", "decimals": 0, "prefer": "lower"},
    {"label": "Résidences principales occupées par leur propriétaire", "column": "P22_RP_PROP", "unit": "", "decimals": 0, "prefer": "higher"},
]

# -----------------------------------------------------------------------------
# Indicateurs de l’onglet "Indicateurs complémentaires"
# -----------------------------------------------------------------------------

INDICATEURS_COMPLEMENTAIRES = [
    {"label": "Établissements actifs", "column": "ETTOT24", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Créations d'entreprises", "column": "ENCTOT25", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Entreprises individuelles", "column": "ENCITOT25", "unit": "", "decimals": 0, "prefer": "higher"},

    {"label": "Hôtels", "column": "HT26", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Campings", "column": "CPG26", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Résidences de tourisme", "column": "RT26", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Villages vacances", "column": "VV26", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Auberges / centres de séjour", "column": "AJCS26", "unit": "", "decimals": 0, "prefer": "higher"},

    {"label": "Boulangeries", "column": "BPE_2024_B105", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Supermarchés / supérettes", "column": "BPE_2024_B201", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Médecins généralistes", "column": "BPE_2024_C201", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Pharmacies", "column": "BPE_2024_C301", "unit": "", "decimals": 0, "prefer": "higher"},
    {"label": "Équipements sportifs", "column": "BPE_2024_D307", "unit": "", "decimals": 0, "prefer": "higher"},
]

SPECS_DYNAMIQUE_ECONOMIQUE = [
    {"label": "Établissements actifs", "column": "ETTOT24"},
    {"label": "Créations d'entreprises", "column": "ENCTOT25"},
    {"label": "Entreprises individuelles", "column": "ENCITOT25"},
]

SPECS_TOURISME = [
    {"label": "Hôtels", "column": "HT26"},
    {"label": "Campings", "column": "CPG26"},
    {"label": "Résidences de tourisme", "column": "RT26"},
    {"label": "Villages vacances", "column": "VV26"},
    {"label": "Auberges / centres de séjour", "column": "AJCS26"},
]

SPECS_SERVICES_PROXIMITE = [
    {"label": "Boulangeries", "column": "BPE_2024_B105"},
    {"label": "Supermarchés / supérettes", "column": "BPE_2024_B201"},
    {"label": "Médecins généralistes", "column": "BPE_2024_C201"},
    {"label": "Pharmacies", "column": "BPE_2024_C301"},
    {"label": "Équipements sportifs", "column": "BPE_2024_D307"},
]

SPECS_TENDANCE_CREATION_ENTREPRISES = [
    {"label": "2022", "column": "ENCTOT22"},
    {"label": "2023", "column": "ENCTOT23"},
    {"label": "2024", "column": "ENCTOT24"},
    {"label": "2025", "column": "ENCTOT25"},
]


# -----------------------------------------------------------------------------
# 2. Composants visuels de section
# -----------------------------------------------------------------------------
def afficher_titre_onglet(title: str, cle_section: str) -> None:
    """Affiche le titre d'un onglet sans sous-titre gris."""
    accent = THEMES_SECTIONS[cle_section]["accent"]
    st.markdown(
        f"""
<div class="section-title-shell">
  <div class="section-title-bar" style="background:{accent};"></div>
  <div class="section-title-text">{html.escape(title)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# 3. Fonctions de rendu des graphiques
# -----------------------------------------------------------------------------
# Chaque type de graphique a une fonction dédiée. Cela évite de répéter le même
# code dans chaque onglet et permet de garder une charte graphique cohérente.

def base_graphique(cle_section: str, df: pd.DataFrame, hauteur: int) -> alt.Chart:
    """Prépare la base commune des graphiques Altair."""
    theme_section = THEMES_SECTIONS[cle_section]
    ordre_villes = list(dict.fromkeys(df["Ville"].tolist()))
    return (
        alt.Chart(df)
        .properties(height=hauteur)
        .encode(
            color=alt.Color(
                "Ville:N",
                scale=alt.Scale(domain=ordre_villes, range=theme_section["pair"][: len(ordre_villes)]),
                legend=alt.Legend(
                    title=None,
                    orient="top",
                    direction="horizontal",
                    columns=min(len(ordre_villes), 2),
                    symbolSize=120,
                    labelLimit=1000,
                    offset=8,
                ),
            ),
            tooltip=[
                alt.Tooltip("Indicateur:N", title="Indicateur"),
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Valeur:Q", title="Valeur", format=",.1f"),
            ],
        )
    )


def afficher_graphique(chart: alt.Chart | alt.LayerChart) -> None:
    """Affiche un graphique Altair proprement."""
    st.altair_chart(
        chart.configure_view(strokeOpacity=0).configure_axis(
            labelLimit=1000,
            titleLimit=1000,
        ).configure_legend(
            labelLimit=1000,
            titleLimit=1000,
        ),
        width="stretch",
    )

def afficher_graphique_barres_groupees(
    df: pd.DataFrame,
    cle_section: str,
    horizontal: bool = True,
    hauteur: int = 300,
    ordre_tri: list[str] | None = None,
) -> None:
    """Affiche un graphique en barres groupées avec étiquettes."""
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    base = base_graphique(cle_section, df, hauteur)

    if horizontal:
        bars = base.mark_bar(size=18, cornerRadiusEnd=4).encode(
            y=alt.Y("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelLimit=1000)),
            x=alt.X("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.0f")),
            yOffset=alt.YOffset("Ville:N"),
        )

        labels = base.mark_text(
            align="left",
            dx=6,
            fontSize=12,
            color="#143047",
        ).encode(
            y=alt.Y("Indicateur:N", sort=ordre_tri, title=None),
            x=alt.X("Valeur:Q"),
            yOffset=alt.YOffset("Ville:N"),
            text=alt.Text("Valeur:Q", format=",.0f"),
        )

    else:
        bars = base.mark_bar(size=18, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelAngle=-20, labelLimit=1000)),
            y=alt.Y("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.0f")),
            xOffset=alt.XOffset("Ville:N"),
        )

        labels = base.mark_text(
            dy=-8,
            fontSize=12,
            color="#143047",
        ).encode(
            x=alt.X("Indicateur:N", sort=ordre_tri, title=None),
            y=alt.Y("Valeur:Q"),
            xOffset=alt.XOffset("Ville:N"),
            text=alt.Text("Valeur:Q", format=",.0f"),
        )

    afficher_graphique(bars + labels)

def afficher_graphique_profil_age_pourcentage(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    cle_section: str,
    hauteur: int = 260,
) -> None:
    """Affiche la structure d'âge en pourcentage dans la population totale."""
    specs_age = [
        ("0-14 ans", "P22_POP0014"),
        ("15-29 ans", "P22_POP1529"),
        ("30-44 ans", "P22_POP3044"),
        ("45-59 ans", "P22_POP4559"),
        ("60-74 ans", "P22_POP6074"),
        ("75-89 ans", "P22_POP7589"),
        ("90 ans et +", "P22_POP90P"),
    ]

    rows = []
    for city in [ville_gauche, ville_droite]:
        population_totale = flottant_securise(city.get("P22_POP"))
        if population_totale is None or population_totale == 0:
            continue

        for order, (label, column) in enumerate(specs_age):
            value = flottant_securise(city.get(column))
            if value is None:
                continue

            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Tranche": label,
                    "Pourcentage": (value / population_totale) * 100,
                    "Ordre": order,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    ordre_villes = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=ordre_villes),
            x=alt.X(
                "Pourcentage:Q",
                stack="normalize",
                title=None,
                axis=alt.Axis(format="%"),
            ),
            color=alt.Color(
                "Tranche:N",
                title="Tranche d'âge",
                sort=alt.EncodingSortField(field="Ordre", order="ascending"),
                scale=alt.Scale(
                    range=[
                        "#dce9f3",
                        "#bfd5e7",
                        "#9fc0db",
                        "#7da9cd",
                        "#5d92be",
                        "#3f7dad",
                        "#245f8c",
                    ]
                ),
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=4,
                    labelLimit=1000,
                    titleLimit=1000,
                ),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Tranche:N", title="Tranche d'âge"),
                alt.Tooltip("Pourcentage:Q", title="Part", format=".1f"),
            ],
        )
        .properties(height=hauteur)
    )

    afficher_graphique(chart)

def afficher_graphique_profil_menages_pourcentage(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    hauteur: int = 220,
) -> None:
    """Affiche la structure des ménages en pourcentage du total des ménages."""
    specs_menages = [
        ("Personnes seules", "C22_MENPSEUL"),
        ("Ménages familiaux", "C22_MENFAM"),
        ("Couples sans enfant", "C22_COUPSENF"),
        ("Couples avec enfant(s)", "C22_COUPAENF"),
        ("Familles monoparentales", "C22_FAMMONO"),
    ]

    rows = []
    for city in [ville_gauche, ville_droite]:
        menages_totaux = flottant_securise(city.get("P22_MEN"))
        if menages_totaux is None or menages_totaux == 0:
            continue

        for order, (label, column) in enumerate(specs_menages):
            value = flottant_securise(city.get(column))
            if value is None:
                continue

            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Type": label,
                    "Pourcentage": (value / menages_totaux) * 100,
                    "Ordre": order,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return
    
    ordre_villes = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]
    
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=ordre_villes),
            x=alt.X(
                "Pourcentage:Q",
                stack="normalize",
                title=None,
                axis=alt.Axis(format="%"),
            ),
            color=alt.Color(
                "Type:N",
                title="Type de ménage",
                sort=alt.EncodingSortField(field="Ordre", order="ascending"),
                scale=alt.Scale(
                    range=[
                        "#dce9f3",
                        "#bfd5e7",
                        "#9fc0db",
                        "#7da9cd",
                        "#5d92be",
                    ]
                ),
                legend=alt.Legend(orient="top", direction="horizontal", columns=3),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Type:N", title="Type de ménage"),
                alt.Tooltip("Pourcentage:Q", title="Part", format=".1f"),
            ],
        )
        .properties(height=hauteur)
    )

    st.altair_chart(chart.configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_actifs_age_pourcentage(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    hauteur: int = 180,
) -> None:
    """Affiche la structure des actifs par âge en pourcentage du total des actifs 15-64 ans."""
    specs = [
        ("15-24 ans", "P22_ACT1524"),
        ("25-54 ans", "P22_ACT2554"),
        ("55-64 ans", "P22_ACT5564"),
    ]

    rows = []
    for city in [ville_gauche, ville_droite]:
        actifs_totaux = flottant_securise(city.get("P22_ACT1564"))
        if actifs_totaux is None or actifs_totaux == 0:
            continue

        for order, (label, column) in enumerate(specs):
            value = flottant_securise(city.get(column))
            if value is None:
                continue
            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Tranche": label,
                    "Pourcentage": (value / actifs_totaux) * 100,
                    "Ordre": order,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    ordre_villes = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=ordre_villes),
            x=alt.X("Pourcentage:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
            color=alt.Color(
                "Tranche:N",
                title="Âge",
                sort=alt.EncodingSortField(field="Ordre", order="ascending"),
                scale=alt.Scale(range=["#d8ebe3", "#8db7a5", "#5c8f79"]),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Tranche:N", title="Tranche"),
                alt.Tooltip("Pourcentage:Q", title="Part", format=".1f"),
            ],
        )
        .properties(height=hauteur)
    )

    st.altair_chart(chart.configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_chomage_age_pourcentage(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    hauteur: int = 180,
) -> None:
    """Affiche la structure des chômeurs par âge en pourcentage du total des chômeurs 15-64 ans."""
    specs = [
        ("15-24 ans", "P22_CHOM1524"),
        ("25-54 ans", "P22_CHOM2554"),
        ("55-64 ans", "P22_CHOM5564"),
    ]

    rows = []
    for city in [ville_gauche, ville_droite]:
        chomeurs_totaux = flottant_securise(city.get("P22_CHOM1564"))
        if chomeurs_totaux is None or chomeurs_totaux == 0:
            continue

        for order, (label, column) in enumerate(specs):
            value = flottant_securise(city.get(column))
            if value is None:
                continue
            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Tranche": label,
                    "Pourcentage": (value / chomeurs_totaux) * 100,
                    "Ordre": order,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return
    
    ordre_villes = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]
    
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=ordre_villes),
            x=alt.X("Pourcentage:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
            color=alt.Color(
                "Tranche:N",
                title="Âge",
                sort=alt.EncodingSortField(field="Ordre", order="ascending"),
                scale=alt.Scale(range=["#d8ebe3", "#8db7a5", "#5c8f79"]),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Tranche:N", title="Tranche"),
                alt.Tooltip("Pourcentage:Q", title="Part", format=".1f"),
            ],
        )
        .properties(height=hauteur)
    )

    st.altair_chart(chart.configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_structure_logement_pourcentage(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    hauteur: int = 220,
) -> None:
    """Affiche la structure du parc de logements en pourcentage du total."""
    specs = [
        ("Résidences principales", "P22_RP"),
        ("Logements vacants", "P22_LOGVAC"),
    ]

    rows = []
    for city in [ville_gauche, ville_droite]:
        logements_totaux = flottant_securise(city.get("P22_LOG"))
        if logements_totaux is None or logements_totaux == 0:
            continue

        for order, (label, column) in enumerate(specs):
            value = flottant_securise(city.get(column))
            if value is None:
                continue
            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Type": label,
                    "Pourcentage": (value / logements_totaux) * 100,
                    "Ordre": order,
                }
            )

        secondaires = logements_totaux - (flottant_securise(city.get("P22_RP")) or 0) - (flottant_securise(city.get("P22_LOGVAC")) or 0)
        if secondaires >= 0:
            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Type": "Résidences secondaires / autres",
                    "Pourcentage": (secondaires / logements_totaux) * 100,
                    "Ordre": 2,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return
    
    ordre_villes = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]
    
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=ordre_villes),
            x=alt.X("Pourcentage:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
            color=alt.Color(
                "Type:N",
                title="Type de logement",
                sort=alt.EncodingSortField(field="Ordre", order="ascending"),
                scale=alt.Scale(range=["#f2e4d8", "#d6b399", "#b28661"]),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Type:N", title="Type"),
                alt.Tooltip("Pourcentage:Q", title="Part", format=".1f"),
            ],
        )
        .properties(height=hauteur)
    )

    st.altair_chart(chart.configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_observations_loyer(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    cle_section: str,
    hauteur: int = 240,
) -> None:
    """Affiche le nombre d'annonces utilisées pour estimer les loyers."""
    df = pd.DataFrame(
        {
            "Ville": [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]],
            "Valeur": [ville_gauche.get("nbobs_loyer"), ville_droite.get("nbobs_loyer")],
        }
    )

    df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce")
    df = df.dropna(subset=["Valeur"])

    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    couleurs = THEMES_SECTIONS[cle_section]["pair"]

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=6)
        .encode(
            x=alt.X("Ville:N", title=None),
            y=alt.Y("Valeur:Q", title=None),
            color=alt.Color(
                "Ville:N",
                scale=alt.Scale(domain=[ville_gauche["LIBGEO"], ville_droite["LIBGEO"]], range=couleurs),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Valeur:Q", title="Nombre d'annonces", format=",.0f"),
            ],
        )
        .properties(height=hauteur)
    )

    texte = chart.mark_text(
        dy=-10,
        fontSize=16,
        fontWeight="bold",
        color="#143047",
    ).encode(
        text=alt.Text("Valeur:Q", format=",.0f")
    )

    st.altair_chart((chart + texte).configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_fourchette_loyer(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    cle_section: str,
    hauteur: int = 220,
) -> None:
    """Affiche la borne basse, le loyer moyen et la borne haute pour chaque ville."""
    df = pd.DataFrame(
        [
            {
                "Ville": ville_gauche["LIBGEO"],
                "Bas": ville_gauche.get("loyer_m2_bas"),
                "Moyen": ville_gauche.get("loyer_m2_appartement"),
                "Haut": ville_gauche.get("loyer_m2_haut"),
            },
            {
                "Ville": ville_droite["LIBGEO"],
                "Bas": ville_droite.get("loyer_m2_bas"),
                "Moyen": ville_droite.get("loyer_m2_appartement"),
                "Haut": ville_droite.get("loyer_m2_haut"),
            },
        ]
    )

    for col in ["Bas", "Moyen", "Haut"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Bas", "Moyen", "Haut"])
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    couleurs = THEMES_SECTIONS[cle_section]["pair"]
    domaine = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]

    barres_plage = (
        alt.Chart(df)
        .mark_rule(strokeWidth=4)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=domaine),
            x=alt.X("Bas:Q", title="Loyer (EUR/m²)"),
            x2="Haut:Q",
            color=alt.Color(
                "Ville:N",
                scale=alt.Scale(domain=domaine, range=couleurs),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Bas:Q", title="Borne basse", format=".1f"),
                alt.Tooltip("Moyen:Q", title="Loyer moyen", format=".1f"),
                alt.Tooltip("Haut:Q", title="Borne haute", format=".1f"),
            ],
        )
    )

    points_moyens = (
        alt.Chart(df)
        .mark_circle(size=130)
        .encode(
            y=alt.Y("Ville:N", title=None, sort=domaine),
            x=alt.X("Moyen:Q", title="Loyer (EUR/m²)"),
            color=alt.Color(
                "Ville:N",
                scale=alt.Scale(domain=domaine, range=couleurs),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Moyen:Q", title="Loyer moyen", format=".1f"),
            ],
        )
    )

    etiquettes_basses = (
        alt.Chart(df)
        .mark_text(align="right", dx=-8, fontSize=13, color="#143047")
        .encode(
            y=alt.Y("Ville:N", title=None, sort=domaine),
            x="Bas:Q",
            text=alt.Text("Bas:Q", format=".1f"),
        )
    )

    etiquettes_moyennes = (
        alt.Chart(df)
        .mark_text(dy=-14, fontSize=13, fontWeight="bold", color="#143047")
        .encode(
            y=alt.Y("Ville:N", title=None, sort=domaine),
            x="Moyen:Q",
            text=alt.Text("Moyen:Q", format=".1f"),
        )
    )

    etiquettes_hautes = (
        alt.Chart(df)
        .mark_text(align="left", dx=8, fontSize=13, color="#143047")
        .encode(
            y=alt.Y("Ville:N", title=None, sort=domaine),
            x="Haut:Q",
            text=alt.Text("Haut:Q", format=".1f"),
        )
    )

    chart = (barres_plage + points_moyens + etiquettes_basses + etiquettes_moyennes + etiquettes_hautes).properties(height=hauteur)
    st.altair_chart(chart.configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_tendance_creation_entreprises(
    ville_gauche: pd.Series,
    ville_droite: pd.Series,
    cle_section: str,
    hauteur: int = 280,
) -> None:
    """Affiche l'évolution des créations d'entreprises sur 4 années."""
    rows = []
    for city in [ville_gauche, ville_droite]:
        for spec in SPECS_TENDANCE_CREATION_ENTREPRISES:
            value = flottant_securise(city.get(spec["column"]))
            if value is None:
                continue
            rows.append(
                {
                    "Ville": city["LIBGEO"],
                    "Année": spec["label"],
                    "Valeur": value,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    couleurs = THEMES_SECTIONS[cle_section]["pair"]
    domaine = [ville_gauche["LIBGEO"], ville_droite["LIBGEO"]]

    ligne = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("Année:N", title=None, sort=["2022", "2023", "2024", "2025"]),
            y=alt.Y("Valeur:Q", title=None),
            color=alt.Color(
                "Ville:N",
                scale=alt.Scale(domain=domaine, range=couleurs),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Ville:N", title="Ville"),
                alt.Tooltip("Année:N", title="Année"),
                alt.Tooltip("Valeur:Q", title="Créations", format=",.0f"),
            ],
        )
        .properties(height=hauteur)
    )

    texte = (
        alt.Chart(df)
        .mark_text(dy=-10, fontSize=12, color="#143047")
        .encode(
            x=alt.X("Année:N", sort=["2022", "2023", "2024", "2025"]),
            y="Valeur:Q",
            text=alt.Text("Valeur:Q", format=",.0f"),
            detail="Ville:N",
        )
    )

    st.altair_chart((ligne + texte).configure_view(strokeOpacity=0), width="stretch")

def afficher_graphique_haltere(
    df: pd.DataFrame,
    cle_section: str,
    hauteur: int = 300,
    ordre_tri: list[str] | None = None,
) -> None:
    """Affiche un graphique de comparaison avec deux points reliés par indicateur."""
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    zoom_graphique = alt.selection_interval(bind="scales", encodings=["x"])

    theme_section = THEMES_SECTIONS[cle_section]
    ordre_villes = list(dict.fromkeys(df["Ville"].tolist()))
    if len(ordre_villes) < 2:
        afficher_graphique_barres_groupees(df, cle_section, hauteur=hauteur, ordre_tri=ordre_tri)
        return

    ville_gauche_nom, ville_droite_nom = ordre_villes[:2]
    # Le dumbbell chart compare deux villes sur une même ligne : une règle relie
    # les deux valeurs, puis un point marque chaque ville.
    regles = (
        df.pivot_table(index="Indicateur", columns="Ville", values="Valeur", aggfunc="first")
        .reset_index()
        .dropna(subset=[ville_gauche_nom, ville_droite_nom], how="any")
    )
    if regles.empty:
        afficher_graphique_barres_groupees(df, cle_section, hauteur=hauteur, ordre_tri=ordre_tri)
        return

    regles["ValeurMin"] = regles[[ville_gauche_nom, ville_droite_nom]].min(axis=1)
    regles["ValeurMax"] = regles[[ville_gauche_nom, ville_droite_nom]].max(axis=1)

    ligne = (
        alt.Chart(regles)
        .mark_rule(strokeWidth=3, color=theme_section["ligne"])
        .encode(
            y=alt.Y("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelLimit=220)),
            x=alt.X("ValeurMin:Q", title=None, axis=alt.Axis(grid=True, format=",.1f")),
            x2="ValeurMax:Q",
        )
        .properties(height=hauteur)
    )
    points = (
        base_graphique(cle_section, df, hauteur)
        .mark_circle(size=180)
        .encode(
            y=alt.Y("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelLimit=220)),
            x=alt.X("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.1f")),
        )
    )
    afficher_graphique((ligne + points).add_params(zoom_graphique))


def afficher_graphique_ligne(
    df: pd.DataFrame,
    cle_section: str,
    hauteur: int = 280,
    ordre_tri: list[str] | None = None,
) -> None:
    """Affiche une courbe pour suivre une évolution dans le temps."""
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    chart = (
        base_graphique(cle_section, df, hauteur)
        .mark_line(point=alt.OverlayMarkDef(size=80), strokeWidth=3)
        .encode(
            x=alt.X("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelAngle=-25, labelLimit=130)),
            y=alt.Y("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.1f")),
        )
    )
    afficher_graphique(chart)


def afficher_graphique_points(
    df: pd.DataFrame,
    cle_section: str,
    hauteur: int = 280,
    ordre_tri: list[str] | None = None,
) -> None:
    """Affiche un graphique en points pour comparer des valeurs mensuelles."""
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    chart = (
        base_graphique(cle_section, df, hauteur)
        .mark_circle(size=170, opacity=0.92)
        .encode(
            x=alt.X("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelAngle=-25, labelLimit=130)),
            y=alt.Y("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.1f")),
        )
    )
    afficher_graphique(chart)


def afficher_graphique_aire(
    df: pd.DataFrame,
    cle_section: str,
    hauteur: int = 280,
    ordre_tri: list[str] | None = None,
) -> None:
    """Affiche un graphique en aire pour visualiser une quantité dans le temps."""
    if df.empty:
        st.info("Aucune donnée disponible pour ce graphique.")
        return

    base = base_graphique(cle_section, df, hauteur).encode(
        x=alt.X("Indicateur:N", sort=ordre_tri, title=None, axis=alt.Axis(labelAngle=-25, labelLimit=130)),
        y=alt.Y("Valeur:Q", title=None, axis=alt.Axis(grid=True, format=",.1f")),
    )
    chart = base.mark_area(opacity=0.2) + base.mark_line(strokeWidth=2.5) + base.mark_circle(size=55)
    afficher_graphique(chart)


def afficher_carte_localisation_france(tableau_points: pd.DataFrame) -> None:
    """Affiche la France vide avec uniquement les points des villes sélectionnées."""
    if tableau_points.empty:
        st.warning("Impossible d'afficher la carte : coordonnées indisponibles pour les villes sélectionnées.")
        return

    fig = go.Figure()

    # Fond : contour de la France uniquement
    fig.add_trace(
        go.Choropleth(
            locations=["FRA"],
            z=[1],
            locationmode="ISO-3",
            colorscale=[[0, "#f8fafc"], [1, "#f8fafc"]],
            showscale=False,
            marker_line_color="#143047",
            marker_line_width=1.8,
            hoverinfo="skip",
        )
    )

    # Points des villes
    fig.add_trace(
        go.Scattergeo(
            lon=tableau_points["Longitude"],
            lat=tableau_points["Latitude"],
            text=tableau_points["Ville"] ,
            mode="markers+text",
            textposition="top center",
            hovertemplate="<b>%{text}</b><extra></extra>",
            marker=dict(
                size=12,
                color="#e30613",
                line=dict(color="#ffffff", width=2),
            ),
        )
    )

    fig.update_geos(
        scope="europe",
        fitbounds="locations",
        visible=False,
        showcountries=False,
        showcoastlines=False,
        showframe=False,
        showland=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        height=490,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False, "staticPlot": True},)


# -----------------------------------------------------------------------------
# 4. Composants d’affichage réutilisables
# -----------------------------------------------------------------------------
# Ces fonctions affichent les cartes de synthèse et les tableaux. Elles sont
# utilisées dans plusieurs onglets pour garder une présentation homogène.

def carte_recit_html(title: str, body: str, cle_section: str) -> str:
    """Construit le HTML d'une carte de synthèse."""
    accent = THEMES_SECTIONS[cle_section]["accent"]
    return f"""
<div class="section-card" style="border-top:4px solid {accent};">
  <h4 style="color:{accent};">{html.escape(title)}</h4>
  <p>{html.escape(body)}</p>
</div>
"""


def afficher_grille_cartes_recit(cards: list[tuple[str, str]], cle_section: str, columns: int) -> None:
    """Affiche plusieurs cartes dans une grille avec hauteur égale par ligne."""
    cards_html = "\n".join(carte_recit_html(title, body, cle_section) for title, body in cards)
    st.markdown(
        f"""
<div class="card-grid card-grid-{columns}">
{cards_html}
</div>
""",
        unsafe_allow_html=True,
    )


def carte_kpi_climat_html(
    title: str,
    city_left_name: str,
    city_right_name: str,
    valeur_gauche: float | int | None,
    valeur_droite: float | int | None,
    unit: str,
    decimals: int,
    leader_text: str,
    help_text: str = "",
) -> str:
    """Construit le HTML d'une carte KPI climat."""
    accent = THEMES_SECTIONS["meteo"]["accent"]
    left_display = formater_indicateur(valeur_gauche, unit, decimals)
    right_display = formater_indicateur(valeur_droite, unit, decimals)

    if pd.isna(valeur_gauche) or pd.isna(valeur_droite):
        note = "Donnée indisponible pour au moins une ville."
    elif float(valeur_gauche) == float(valeur_droite):
        note = "Les deux villes sont au même niveau."
    else:
        leader = city_left_name if float(valeur_gauche) > float(valeur_droite) else city_right_name
        note = f"{leader_text} : {leader}. Écart : {ecart_indicateur(valeur_gauche, valeur_droite, unit, decimals)}."
    if help_text:
        note = f"{help_text} {note}"

    return f"""
<div class="climate-kpi-card" style="border-top:4px solid {accent};">
  <div class="climate-kpi-title">{html.escape(title)}</div>
  <div class="climate-kpi-values">
    <div>
      <div class="climate-kpi-city">{html.escape(city_left_name)}</div>
      <div class="climate-kpi-number">{html.escape(left_display)}</div>
    </div>
    <div>
      <div class="climate-kpi-city">{html.escape(city_right_name)}</div>
      <div class="climate-kpi-number">{html.escape(right_display)}</div>
    </div>
  </div>
  <div class="climate-kpi-note">{html.escape(note)}</div>
</div>
"""


def afficher_grille_kpi_climat(metrics: list[dict[str, object]], city_left_name: str, city_right_name: str) -> None:
    """Affiche les KPI climat dans une grille à hauteur égale par ligne."""
    cards_html = "\n".join(
        carte_kpi_climat_html(
            str(metric["title"]),
            city_left_name,
            city_right_name,
            metric["valeur_gauche"],
            metric["valeur_droite"],
            str(metric["unit"]),
            int(metric["decimals"]),
            str(metric["leader_text"]),
            str(metric.get("help", "")),
        )
        for metric in metrics
    )
    st.markdown(
        f"""
<div class="card-grid card-grid-3">
{cards_html}
</div>
""",
        unsafe_allow_html=True,
    )


def afficher_bloc_detail(ville_gauche: pd.Series, ville_droite: pd.Series, metrics: list[dict[str, object]], key_prefix: str) -> None:
    """Affiche le tableau détaillé dans un bloc repliable avec téléchargement CSV."""
    tableau_detail = construire_tableau_detail(ville_gauche, ville_droite, metrics)
    tableau_export = tableau_detail.drop(columns=["_better"], errors="ignore")

    with st.expander("", expanded=False):
        st.markdown(
            afficher_tableau_detail_html(tableau_detail, ville_gauche["LIBGEO"], ville_droite["LIBGEO"]),
            unsafe_allow_html=True,
        )
        st.download_button(
            "Télécharger le tableau CSV",
            tableau_export.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{key_prefix}_{ville_gauche['CODGEO']}_{ville_droite['CODGEO']}.csv",
            mime="text/csv",
            key=f"download_{key_prefix}",
        )


def carte_conclusion(title: str, winner: str, detail: str, cle_section: str = "overview") -> str:
    accent = THEMES_SECTIONS[cle_section]["accent"]
    return f"""
<div class="section-card" style="border-top:4px solid {accent};">
  <h4 style="color:{accent};">{html.escape(title)}</h4>
  <p><strong>{html.escape(winner)}</strong></p>
  <p>{html.escape(detail)}</p>
</div>
"""

# -----------------------------------------------------------------------------
# 5. Construction de la page Streamlit
# -----------------------------------------------------------------------------
#  chargement des données, choix des villes, création des onglets et affichage des analyses.

afficher_hero(
    "Comparateur de villes françaises",
    "Comparez rapidement deux villes françaises : niveau de vie, emploi, logement et climat.",
)

# Chargement et préparation de toutes les données locales avant affichage.
data_df = charger_jeu_donnees_villes()
if data_df.empty:
    st.error("Aucune ville disponible après chargement des données.")
    st.stop()

# Sélection des deux villes dans l’interface, puis récupération de leur contexte
# géographique pour la météo, le climat et les cartes de ville.
ville_gauche, ville_droite, contexte_gauche, contexte_droite = obtenir_villes_selectionnees(data_df)
afficher_duo_villes(ville_gauche, ville_droite, contexte_gauche, contexte_droite)

# Les onglets organisent l’analyse sans multiplier les pages Streamlit.
tabs = st.tabs(
    [
        "Vue d'ensemble",
        "Profil démographique",
        "Emploi",
        "Logement",
        "Météo et climat",
        "Données complémentaires",
        "Conclusion",
    ]
)

# Onglet 1 : résumé global pour comprendre rapidement les grands écarts.
with tabs[0]:
    afficher_titre_onglet(
        "Vue d'ensemble",
        "overview",
    )

    afficher_grille_cartes_recit(
        [
            ("Niveau de vie",texte_comparaison(ville_gauche,ville_droite,"MED21",True,"le revenu médian le plus élevé","EUR",0,),),
            ("Emploi",texte_comparaison(ville_gauche,ville_droite,"taux_chomage",False,"le taux de chômage le plus faible","%",1,),),
            ("Coût du logement",texte_comparaison(ville_gauche,ville_droite,"loyer_m2_appartement",False,"le loyer moyen au m² le plus faible","EUR/m²",1,)+ " ("+ ecart_relatif_indicateur(ville_gauche["loyer_m2_appartement"],ville_droite["loyer_m2_appartement"],1,)+ ")",),
            ("Logement",texte_comparaison(ville_gauche,ville_droite,"taux_logements_vacants",False,"le taux de logements vacants le plus faible","%",1,),),
        ],
        "overview",
        4,
    )


    st.markdown("#### Localisation des villes sélectionnées")
    afficher_carte_localisation_france(points_villes_selectionnees(ville_gauche, ville_droite, contexte_gauche, contexte_droite))


# Onglet 2 : Profil démographique de population, revenu et démographie.
with tabs[1]:
    afficher_titre_onglet(
        "Profil démographique",
        "démographique",
    )

    afficher_grille_cartes_recit(
        [
            ("Poids démographique",texte_comparaison(ville_gauche,ville_droite,"P22_POP",True,"la population la plus élevée","hab",0,),),
            ("Taille du territoire",texte_comparaison(ville_gauche,ville_droite,"SUPERF",True,"la superficie la plus élevée","km²",1,),),
        ],
        "démographique",
        2,
    )

    st.markdown("#### Répartition par âge")

    col_age_gauche, col_age_droite = st.columns([1.25, 1])

    with col_age_gauche:
        st.markdown("##### Effectifs par tranche d'âge")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                SPECS_PROFIL_AGE_DEMOGRAPHIQUE,
            ),
            "démographique",
            horizontal=True,
            hauteur=420,
            ordre_tri=[
                "0-14 ans",
                "15-29 ans",
                "30-44 ans",
                "45-59 ans",
                "60-74 ans",
                "75-89 ans",
                "90 ans et +",
            ],
        )

    with col_age_droite:
        st.markdown("##### Structure d'âge dans la population totale")
        afficher_graphique_profil_age_pourcentage(
            ville_gauche,
            ville_droite,
            "démographique",
            hauteur=220,
        )

        age_moyen_gauche = age_moyen_estime(ville_gauche)
        age_moyen_droite = age_moyen_estime(ville_droite)

        col_indicateur_1, col_indicateur_2 = st.columns(2)

        with col_indicateur_1:
            afficher_carte_kpi_demographie(
                f"Âge moyen estimé {ville_gauche['LIBGEO']}",
                formater_indicateur(age_moyen_gauche, "ans", 1),
                "left",
            )

        with col_indicateur_2:
            afficher_carte_kpi_demographie(
                f"Âge moyen estimé {ville_droite['LIBGEO']}",
                formater_indicateur(age_moyen_droite, "ans", 1),
                "right",
            )

        left_base_pop = ville_gauche["P11_POP"]
        right_base_pop = ville_droite["P11_POP"]

        population_evolution_df = pd.DataFrame(
            {
                "Indicateur": ["2011", "2016", "2022", "2011", "2016", "2022"],
                "Ville": [ville_gauche["LIBGEO"]] * 3 + [ville_droite["LIBGEO"]] * 3,
                "Valeur": [
                    0,
                    ((ville_gauche["P16_POP"] - left_base_pop) / left_base_pop) * 100,
                    ((ville_gauche["P22_POP"] - left_base_pop) / left_base_pop) * 100,
                    0,
                    ((ville_droite["P16_POP"] - right_base_pop) / right_base_pop) * 100,
                    ((ville_droite["P22_POP"] - right_base_pop) / right_base_pop) * 100,
                ],
            }
        )

    st.markdown("#### Évolution de la population depuis 2011 (en %)")
    afficher_graphique_ligne(
        population_evolution_df,
        "démographique",
        hauteur=300,
        ordre_tri=ORDRE_EVOLUTION_POPULATION_DEMOGRAPHIQUE,
    )

    st.markdown("#### Structure des ménages")

    col_menages_gauche, col_menages_droite = st.columns([1.25, 1])

    with col_menages_gauche:
        st.markdown("##### Effectifs par type de ménage")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                SPECS_MENAGES_DEMOGRAPHIQUES,
            ),
            "démographique",
            horizontal=True,
            hauteur=360,
            ordre_tri=[
                "Personnes seules",
                "Ménages familiaux",
                "Couples sans enfant",
                "Couples avec enfant(s)",
                "Familles monoparentales",
            ],
        )

    with col_menages_droite:
        st.markdown("##### Structure des ménages dans le total")
        afficher_graphique_profil_menages_pourcentage(
            ville_gauche,
            ville_droite,
            hauteur=220,
        )

    afficher_bloc_detail(
        ville_gauche,
        ville_droite,
        INDICATEURS_TABLEAU_DEMOGRAPHIQUES_FINAL,
        "profil_demographique",
    )


# Onglet 3 : emploi, en séparant les taux et les volumes pour éviter les confusions.
with tabs[2]:
    afficher_titre_onglet(
        "Emploi",
        "emploi",
    )

    afficher_grille_cartes_recit(
        [
            ("Taux de chômage", texte_comparaison(ville_gauche, ville_droite, "taux_chomage", False, "le taux de chômage le plus faible", "%", 1)),
            ("Salaire net mensuel", texte_comparaison(ville_gauche, ville_droite, "SNEMM_23", True, "le salaire net mensuel moyen le plus élevé", "EUR")),
        ],
        "emploi",
        2,
    )

    col_graphique_emploi_1, col_graphique_emploi_2 = st.columns(2)

    with col_graphique_emploi_1:
        st.markdown("#### Taux clés")
        afficher_graphique_haltere(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                [
                    {"label": "Taux d'activité", "column": "taux_activite"},
                    {"label": "Taux de chômage", "column": "taux_chomage"},
                    {"label": "Part d'emplois salariés", "column": "part_emplois_salaries"},
                ],
            ),
            "emploi",
            hauteur=300,
            ordre_tri=["Taux d'activité", "Taux de chômage", "Part d'emplois salariés"],
        )

    with col_graphique_emploi_2:
        st.markdown("#### Base économique locale")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                [
                    {"label": "Emplois au lieu de travail", "column": "P22_EMPLT"},
                    {"label": "Emplois salariés", "column": "P22_EMPLT_SAL"},
                    {"label": "Établissements actifs", "column": "ETTOT24"},
                ],
            ),
            "emploi",
            horizontal=True,
            hauteur=300,
            ordre_tri=["Emplois au lieu de travail", "Emplois salariés", "Établissements actifs"],
        )

    st.markdown("#### Salaire net mensuel moyen")
    salary_col_1, salary_col_2 = st.columns(2)

    with salary_col_1:
        afficher_carte_kpi_emploi(
            f"Salaire net mensuel {ville_gauche['LIBGEO']}",
            formater_indicateur(ville_gauche.get("SNEMM_23"), "EUR", 0),
            "left",
        )

    with salary_col_2:
        afficher_carte_kpi_emploi(
            f"Salaire net mensuel {ville_droite['LIBGEO']}",
            formater_indicateur(ville_droite.get("SNEMM_23"), "EUR", 0),
            "right",
        )

    st.markdown("#### Actifs et chômeurs par âge")

    col_emploi_age_gauche, col_emploi_age_droite = st.columns([1.25, 1])

    with col_emploi_age_gauche:
        st.markdown("##### Effectifs par âge")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                [
                    {"label": "Actifs 15-24 ans", "column": "P22_ACT1524"},
                    {"label": "Actifs 25-54 ans", "column": "P22_ACT2554"},
                    {"label": "Actifs 55-64 ans", "column": "P22_ACT5564"},
                    {"label": "Chômeurs 15-24 ans", "column": "P22_CHOM1524"},
                    {"label": "Chômeurs 25-54 ans", "column": "P22_CHOM2554"},
                    {"label": "Chômeurs 55-64 ans", "column": "P22_CHOM5564"},
                ],
            ),
            "emploi",
            horizontal=True,
            hauteur=360,
            ordre_tri=[
                "Actifs 15-24 ans",
                "Actifs 25-54 ans",
                "Actifs 55-64 ans",
                "Chômeurs 15-24 ans",
                "Chômeurs 25-54 ans",
                "Chômeurs 55-64 ans",
            ],
        )

    with col_emploi_age_droite:
        st.markdown("##### Structure des actifs")
        afficher_graphique_actifs_age_pourcentage(
            ville_gauche,
            ville_droite,
            hauteur=150,
        )

        st.markdown("##### Structure des chômeurs")
        afficher_graphique_chomage_age_pourcentage(
            ville_gauche,
            ville_droite,
            hauteur=150,
        )

    afficher_bloc_detail(ville_gauche, ville_droite, INDICATEURS_EMPLOI, "emploi")

# Onglet 4 : logement, avec une distinction entre nombre de logements et taux.
with tabs[3]:
    afficher_titre_onglet(
        "Logement",
        "logement",
    )

    afficher_grille_cartes_recit(
        [
            ("Logements vacants", texte_comparaison(ville_gauche, ville_droite, "taux_logements_vacants", False, "le taux de logements vacants le plus faible", "%", 1)),
            ("Propriété", texte_comparaison(ville_gauche, ville_droite, "taux_proprietaires", True, "la part de propriétaires la plus élevée", "%", 1)),
        ],
        "logement",
        2,
    )

    col_logement_1, col_logement_2 = st.columns([1.25, 1])

    with col_logement_1:
        st.markdown("#### Volumes du parc résidentiel")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                [
                    {"label": "Logements au total", "column": "P22_LOG"},
                    {"label": "Résidences principales", "column": "P22_RP"},
                    {"label": "Logements vacants", "column": "P22_LOGVAC"},
                ],
            ),
            "logement",
            horizontal=True,
            hauteur=320,
            ordre_tri=["Logements au total", "Résidences principales", "Logements vacants"],
        )

    with col_logement_2:
        st.markdown("#### Structure du parc")
        afficher_graphique_structure_logement_pourcentage(
            ville_gauche,
            ville_droite,
            hauteur=220,
        )

    col_logement_3, col_logement_4 = st.columns(2)

    with col_logement_3:
        st.markdown("#### Loyers des appartements (EUR/m²)")
        afficher_graphique_fourchette_loyer(
            ville_gauche,
            ville_droite,
            "logement",
            hauteur=220,
        )

    with col_logement_4:
        st.markdown("#### Nombre d'annonces")
        afficher_graphique_observations_loyer(
            ville_gauche,
            ville_droite,
            "logement",
            hauteur=220,
        )

    afficher_bloc_detail(ville_gauche, ville_droite, INDICATEURS_LOGEMENT, "logement")

# Onglet 5 : météo à court terme et climat moyen sur l’année.
with tabs[4]:
    afficher_titre_onglet(
        "Météo et climat",
        "meteo",
    )

    if contexte_gauche is None or contexte_droite is None:
        st.warning("Impossible de récupérer les coordonnées géographiques pour au moins une ville.")
    else:
        previsions_gauche = recuperer_previsions(contexte_gauche["lat"], contexte_gauche["lon"])
        previsions_droite = recuperer_previsions(contexte_droite["lat"], contexte_droite["lon"])
        climat_gauche = recuperer_climat_mensuel(contexte_gauche["lat"], contexte_gauche["lon"])
        climat_droite = recuperer_climat_mensuel(contexte_droite["lat"], contexte_droite["lon"])

        st.markdown("### Météo des 7 prochains jours")

        # Si les prévisions sont disponibles pour les deux villes, on construit
        # un résumé, plusieurs graphiques et les tableaux quotidiens détaillés.
        if previsions_gauche is not None and previsions_droite is not None:
            libelles_previsions = previsions_gauche["date"].dt.strftime("%d/%m").tolist()
            tableau_previsions_temp_max = tableau_indicateur_previsions(
                previsions_gauche,
                previsions_droite,
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                "temperature_2m_max",
            )
            tableau_previsions_temp_min = tableau_indicateur_previsions(
                previsions_gauche,
                previsions_droite,
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                "temperature_2m_min",
            )
            tableau_previsions_pluie = tableau_indicateur_previsions(
                previsions_gauche,
                previsions_droite,
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                "precipitation_sum",
            )
            tableau_previsions_risque_pluie = tableau_indicateur_previsions(
                previsions_gauche,
                previsions_droite,
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                "precipitation_probability_max",
            )
            tableau_previsions_vent = tableau_indicateur_previsions(
                previsions_gauche,
                previsions_droite,
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                "wind_speed_10m_max",
            )

            afficher_grille_cartes_recit(
                [
                    (f"Prévisions pour {ville_gauche['LIBGEO']}", texte_synthese_previsions(previsions_gauche)),
                    (f"Prévisions pour {ville_droite['LIBGEO']}", texte_synthese_previsions(previsions_droite)),
                ],
                "meteo",
                2,
            )

            col_meteo_1, col_meteo_2 = st.columns(2)
            with col_meteo_1:
                st.markdown("#### Température maximale sur 7 jours")
                afficher_graphique_ligne(tableau_previsions_temp_max, "meteo", hauteur=280, ordre_tri=libelles_previsions)
            with col_meteo_2:
                st.markdown("#### Température minimale sur 7 jours")
                afficher_graphique_ligne(tableau_previsions_temp_min, "meteo", hauteur=280, ordre_tri=libelles_previsions)

            col_meteo_3, col_meteo_4 = st.columns(2)
            with col_meteo_3:
                st.markdown("#### Précipitations sur 7 jours")
                afficher_graphique_aire(tableau_previsions_pluie, "meteo", hauteur=280, ordre_tri=libelles_previsions)
            with col_meteo_4:
                st.markdown("#### Risque de pluie sur 7 jours")
                afficher_graphique_barres_groupees(tableau_previsions_risque_pluie, "meteo", horizontal=False, hauteur=280, ordre_tri=libelles_previsions)

            if not tableau_previsions_vent.empty:
                st.markdown("#### Vent maximal prévu sur 7 jours")
                afficher_graphique_barres_groupees(tableau_previsions_vent, "meteo", horizontal=False, hauteur=260, ordre_tri=libelles_previsions)

            st.markdown("#### Prévisions quotidiennes")
            col_tableau_1, col_tableau_2 = st.columns(2)
            with col_tableau_1:
                export_gauche = previsions_vers_tableau_affichage(previsions_gauche)
                st.markdown(f"##### {ville_gauche['LIBGEO']}")
                st.dataframe(export_gauche, width="stretch", hide_index=True)
                st.download_button(
                    f"Télécharger les prévisions de {ville_gauche['LIBGEO']}",
                    export_gauche.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"previsions_{ville_gauche['CODGEO']}.csv",
                    mime="text/csv",
                    key="download_forecast_left",
                )
            with col_tableau_2:
                export_droite = previsions_vers_tableau_affichage(previsions_droite)
                st.markdown(f"##### {ville_droite['LIBGEO']}")
                st.dataframe(export_droite, width="stretch", hide_index=True)
                st.download_button(
                    f"Télécharger les prévisions de {ville_droite['LIBGEO']}",
                    export_droite.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"previsions_{ville_droite['CODGEO']}.csv",
                    mime="text/csv",
                    key="download_forecast_right",
                )
        else:
            st.warning("Les prévisions météo sur 7 jours sont indisponibles pour au moins une des deux villes.")

        st.markdown("### Climat des 12 derniers mois")

        # Le climat mensuel est affiché séparément des prévisions, car il décrit
        # une période glissante d'un an, pas uniquement la météo de la semaine.
        if climat_gauche is not None and climat_droite is not None:
            tableau_temperature_climat, tableau_pluie_climat = tableaux_comparaison_climat(
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
                climat_gauche,
                climat_droite,
            )
            climat_temperature_long = tableau_long_depuis_tableau_indexe(tableau_temperature_climat)
            climat_pluie_long = tableau_long_depuis_tableau_indexe(tableau_pluie_climat)
            ordre_mois_glissants = tableau_temperature_climat.index.tolist()

            afficher_grille_kpi_climat(
                indicateurs_synthese_climat(tableau_temperature_climat, tableau_pluie_climat, ville_gauche["LIBGEO"], ville_droite["LIBGEO"]),
                ville_gauche["LIBGEO"],
                ville_droite["LIBGEO"],
            )

            col_climat_1, col_climat_2 = st.columns(2)
            with col_climat_1:
                st.markdown("#### Température moyenne mensuelle sur 12 mois")
                afficher_graphique_points(climat_temperature_long, "meteo", hauteur=280, ordre_tri=ordre_mois_glissants)
            with col_climat_2:
                st.markdown("#### Précipitations mensuelles sur 12 mois")
                afficher_graphique_barres_groupees(climat_pluie_long, "meteo", horizontal=False, hauteur=280, ordre_tri=ordre_mois_glissants)
        else:
            st.warning("Les données de climat sur 12 mois sont indisponibles pour au moins une des deux villes.")

# Onglet 6 : indicateurs complémentaires pour enrichir la comparaison.
with tabs[5]:
    afficher_titre_onglet(
        "Attractivité locale",
        "complements",
    )

    afficher_grille_cartes_recit(
        [
            (
                "Dynamisme économique",
                texte_comparaison(
                    ville_gauche,
                    ville_droite,
                    "ENCTOT25",
                    True,
                    "le plus grand nombre de créations d'entreprises",
                    "",
                    0,
                ),
            ),
            (
                "Capacité touristique",
                texte_comparaison(
                    ville_gauche,
                    ville_droite,
                    "HT26",
                    True,
                    "le plus grand nombre d'hôtels",
                    "",
                    0,
                ),
            ),
        ],
        "complements",
        2,
    )

    extra_col_1, extra_col_2 = st.columns(2)

    with extra_col_1:
        st.markdown("#### Dynamisme économique")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                SPECS_DYNAMIQUE_ECONOMIQUE,
            ),
            "complements",
            horizontal=True,
            hauteur=300,
            ordre_tri=[
                "Établissements actifs",
                "Créations d'entreprises",
                "Entreprises individuelles",
            ],
        )

    with extra_col_2:
        st.markdown("#### Capacité d'accueil touristique")
        afficher_graphique_barres_groupees(
            tableau_long_depuis_specs(
                ville_gauche,
                ville_droite,
                SPECS_TOURISME,
            ),
            "complements",
            horizontal=True,
            hauteur=300,
            ordre_tri=[
                "Hôtels",
                "Campings",
                "Résidences de tourisme",
                "Villages vacances",
                "Auberges / centres de séjour",
            ],
        )

    st.markdown("#### Évolution des créations d'entreprises")
    afficher_graphique_tendance_creation_entreprises(
        ville_gauche,
        ville_droite,
        "complements",
        hauteur=260,
    )

    st.markdown("#### Services de proximité")
    afficher_graphique_barres_groupees(
        tableau_long_depuis_specs(
            ville_gauche,
            ville_droite,
            SPECS_SERVICES_PROXIMITE,
        ),
        "complements",
        horizontal=True,
        hauteur=300,
        ordre_tri=[
            "Boulangeries",
            "Supermarchés / supérettes",
            "Médecins généralistes",
            "Pharmacies",
            "Équipements sportifs",
        ],
    )

    afficher_bloc_detail(ville_gauche, ville_droite, INDICATEURS_COMPLEMENTAIRES, "complements")

    
# Onglet 7 : conclusion générale de la comparaison.
with tabs[6]:
    afficher_titre_onglet(
        "Conclusion",
        "overview",
    )

    gagnant_demographique = libelle_gagnant(ville_gauche, ville_droite, "P22_POP", True)
    gagnant_emploi = libelle_gagnant(ville_gauche, ville_droite, "taux_chomage", False)
    gagnant_revenu = libelle_gagnant(ville_gauche, ville_droite, "MED21", True)
    gagnant_logement = libelle_gagnant(ville_gauche, ville_droite, "loyer_m2_appartement", False)
    gagnant_climat = "À interpréter selon les préférences"
    gagnant_attractivite = libelle_gagnant(ville_gauche, ville_droite, "ENCTOT25", True)

    st.markdown("### Synthèse finale")

    st.markdown(
        f"""
<div class="card-grid card-grid-3">
  {carte_conclusion(
      "Profil démographique",
      gagnant_demographique,
      "Ville la plus importante en population parmi les deux villes comparées.",
      "démographique",
  )}
  {carte_conclusion(
      "Emploi",
      gagnant_emploi,
      "Ville la plus favorable selon le taux de chômage le plus faible.",
      "emploi",
  )}
  {carte_conclusion(
      "Niveau de vie",
      gagnant_revenu,
      "Ville avec le revenu médian le plus élevé.",
      "overview",
  )}
  {carte_conclusion(
      "Logement",
      gagnant_logement,
      "Ville la plus accessible selon le loyer moyen au m² le plus faible.",
      "logement",
  )}
  {carte_conclusion(
      "Météo et climat",
      gagnant_climat,
      "Le choix dépend du climat recherché : températures, pluie, vent ou météo à court terme.",
      "meteo",
  )}
  {carte_conclusion(
      "Attractivité locale",
      gagnant_attractivite,
      "Ville avec le plus grand nombre de créations d'entreprises.",
      "complements",
  )}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Lecture globale")

    st.markdown(
        f"""
<div class="section-card" style="border-top:4px solid {THEMES_SECTIONS["overview"]["accent"]};">
  <h4 style="color:{THEMES_SECTIONS["overview"]["accent"]};">Bilan de la comparaison</h4>
  <p>
    Cette comparaison montre que <strong>{html.escape(ville_gauche["LIBGEO"])}</strong> et
    <strong>{html.escape(ville_droite["LIBGEO"])}</strong> ne se distinguent pas sur les mêmes dimensions.
    Une ville peut être plus attractive économiquement, tandis que l'autre peut être plus avantageuse
    sur le logement, le cadre de vie ou certains indicateurs sociaux.
  </p>
  <p>
    Le choix final dépend donc du profil de l'utilisateur : privilégier l'emploi, le coût du logement,
    le niveau de vie, le climat ou les services disponibles.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )
