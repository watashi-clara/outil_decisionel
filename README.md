# Comparateur de villes françaises

Application web développée avec Streamlit pour comparer rapidement deux villes françaises de plus de 20 000 habitants à partir d'indicateurs socio-démographiques, économiques, immobiliers et climatiques.

Le projet a pour objectif de fournir un outil d'aide à la décision lisible et exploitable pour confronter plusieurs territoires selon différents critères : niveau de vie, emploi, logement, attractivité locale, météo et climat.

## Objectifs

- Comparer deux villes françaises sur une base homogène.
- Aider à la décision dans un contexte de mobilité résidentielle, professionnelle ou d'analyse territoriale.
- Rendre lisibles des jeux de données publics parfois techniques à travers une interface unique.
- Proposer à la fois une synthèse rapide et des niveaux de lecture plus détaillés.

## Aperçu fonctionnel

L'application permet de :

- sélectionner deux villes parmi les communes de plus de 20 000 habitants ;
- afficher une vue d'ensemble synthétique des principaux écarts ;
- comparer les villes sur les thèmes démographie, emploi, logement, météo, climat et attractivité locale ;
- visualiser les données sous forme de cartes, graphiques et tableaux détaillés ;
- exporter certains résultats au format CSV ;
- enrichir la comparaison avec des données externes en temps réel ou quasi temps réel.

## Technologies utilisées

- `Streamlit` pour l'interface web interactive
- `pandas` pour le chargement, la préparation et la transformation des données
- `requests` pour les appels HTTP vers les APIs externes
- `openpyxl` pour la lecture du fichier Excel de correspondance des communes
- `Altair` pour les graphiques comparatifs
- `Plotly` pour la carte de localisation des villes en France

## Structure du projet

```text
outil_decisionel/
├── app.py
├── app_core.py
├── requirements.txt
├── README.md
└── data/
    ├── base_cc_comparateur.csv
    ├── dossier_complet.csv
    └── departement_codedepartement.xlsx
```

### Rôle des fichiers

- `app.py`
  Interface Streamlit de l'application. Ce fichier gère l'affichage, les onglets, les graphiques, les cartes HTML, la navigation et l'orchestration générale de la page.

- `app_core.py`
  Coeur applicatif. Ce module centralise le chargement des données, les calculs, les transformations de tableaux, le formatage des indicateurs et les appels aux APIs externes.

- `data/`
  Dossier des données locales nécessaires au fonctionnement du comparateur.

- `requirements.txt`
  Dépendances Python du projet.

## Fonctionnalités principales

### 1. Comparaison de deux villes

- Sélection de deux communes via des listes déroulantes.
- Filtrage des villes sur les communes de plus de 20 000 habitants.
- Affichage d'un résumé de chaque ville en haut de l'application.

### 2. Vue d'ensemble

- Cartes de synthèse sur les grands écarts entre les deux villes.
- Carte de France simplifiée avec la position des villes sélectionnées.

### 3. Profil démographique

- Population, superficie, densité, ménages, revenu médian, naissances et décès.
- Répartition par âge.
- Structure des ménages.
- Évolution de population.

### 4. Emploi

- Taux d'activité et taux de chômage.
- Salaire net mensuel.
- Emplois au lieu de travail et emplois salariés.
- Répartition des actifs et des chômeurs par tranches d'âge.

### 5. Logement

- Loyer moyen d'appartement au m².
- Borne basse et borne haute des loyers observés.
- Nombre d'annonces utilisées.
- Structure du parc de logements.
- Taux de logements vacants et taux de propriétaires.

### 6. Météo et climat

- Prévisions météo sur 7 jours.
- Températures minimales et maximales.
- Précipitations, risque de pluie et vent maximal.
- Climat mensuel sur les 12 derniers mois disponibles.
- Indicateurs climatiques synthétiques.

### 7. Attractivité locale

- Dynamisme économique.
- Créations d'entreprises.
- Tourisme.
- Services de proximité.

### 8. Export

- Export CSV des tableaux détaillés.
- Export CSV des prévisions météo pour chaque ville.

## Données utilisées

L'application combine des fichiers locaux et des APIs publiques.

### Données locales

Les fichiers du dossier `data/` servent de base au comparateur.

- `base_cc_comparateur.csv`
  Base principale de comparaison des communes.

- `dossier_complet.csv`
  Données complémentaires utilisées notamment pour l'emploi, l'activité économique, le tourisme et certains équipements.

- `departement_codedepartement.xlsx`
  Correspondance permettant notamment de relier `CODGEO` aux noms de communes.

### Sources publiques mobilisées

#### INSEE

La majorité des indicateurs structurels utilisés dans le projet proviennent de données issues de traitements basés sur des sources INSEE, notamment :

- population ;
- ménages ;
- logement ;
- emploi ;
- salaires ;
- structure par âge.

#### data.gouv.fr

Le projet exploite également des données publiques diffusées via `data.gouv.fr`, notamment pour :

- les loyers d'annonce au m² par commune ;
- certaines données consolidées utilisées dans les fichiers du projet.

#### geo.api.gouv.fr

API utilisée pour récupérer :

- le département ;
- la région ;
- les coordonnées géographiques des communes.

Ces informations servent à l'affichage contextualisé des villes et à l'interrogation des APIs météo.

#### Open-Meteo

API utilisée pour :

- les prévisions météo à 7 jours ;
- les données climatiques historiques sur 12 mois glissants.

#### Wikipédia

API utilisée pour tenter de récupérer une image illustrant la ville lorsque celle-ci est disponible.

## Logique générale de l'application

1. Les données locales sont chargées et fusionnées à partir du code commune `CODGEO`.
2. Les communes sont filtrées pour ne conserver que celles de plus de 20 000 habitants.
3. Des indicateurs calculés sont préparés à partir des colonnes sources.
4. Au moment de la sélection des villes, des appels externes récupèrent le contexte géographique, les images et les données météo/climat.
5. L'interface affiche ensuite une comparaison structurée par thématique.

## Installation et lancement en local

### 1. Cloner le dépôt

```bash
git clone <url-du-depot>
cd outil_decisionel
```

### 2. Créer un environnement virtuel

Sous Windows :

```bash
python -m venv .venv
.venv\Scripts\activate
```

Sous macOS / Linux :

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Vérifier la présence des données

Le dossier `data/` doit contenir au minimum :

- `base_cc_comparateur.csv`
- `dossier_complet.csv`
- `departement_codedepartement.xlsx`

### 5. Lancer l'application

```bash
streamlit run app.py
```

Puis ouvrir l'URL locale affichée dans le terminal, généralement :

```text
http://localhost:8501
```

## Prérequis et remarques

- Une connexion Internet est nécessaire pour les appels vers :
  - `geo.api.gouv.fr`
  - `Open-Meteo`
  - `Wikipédia`
  - la source de loyers `data.gouv.fr`
- Si une API externe est indisponible, l'application reste conçue pour fonctionner avec des messages de repli plutôt que de bloquer brutalement.
- Les colonnes de données comme `P22_POP`, `MED21`, `P22_LOG`, `P22_CHOM1564`, etc. sont utilisées telles quelles dans le code et dans les fichiers sources.