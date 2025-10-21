# ClinicPortable

Application de gestion de cabinet d'ostéopathie et de drainage lymphatique fonctionnant entièrement en local.

## Fonctionnalités principales

- Gestion des patients, rendez-vous, consultations et factures avec numérotation par activité (OST / DRL).
- Génération de PDF de factures avec modèles par activité.
- Gestion des paiements multiples, suivi des impayés, avoirs et acomptes.
- Tableaux de bord et exports comptables (CSV et XLSX) séparés par activité.
- Sauvegardes et restaurations chiffrées, export RGPD et journal d'audit.
- Notes patient chiffrées avec Fernet et mot de passe maître.

## Architecture

Le projet est découpé en modules :

- `app/` contient la logique applicative, l'UI QML et le bootstrap PySide6.
- `app/db/` définit les modèles SQLAlchemy, les migrations Alembic et les scripts d'initialisation.
- `app/domain/` regroupe les fonctions de domaine (numérotation, facturation, exports, RGPD...).
- `app/security/` gère l'authentification et le chiffrement des notes patient.
- `files/pdf_templates/` regroupe les fragments HTML utilisés par les modèles de facture.

## Installation pour le développement

### Prérequis

- Python 3.11+
- Poetry **ou** pip + virtualenv
- Outils system nécessaires à WeasyPrint (Cairo, Pango) si vous souhaitez générer des PDF en développement.

### Installation

```bash
python -m venv .venv
source .venv/bin/activate  # sous Windows : .venv\\Scripts\\activate
pip install -r requirements.txt
pre-commit install
```

### Base de données et données de démonstration

```bash
alembic upgrade head
python -m app.db.seed
```

### Lancement en mode développement

```bash
./scripts/dev_run.sh
```

## Mode portable (Windows et macOS)

L'application est conçue pour être exécutée sans installation. Les scripts PyInstaller fournis préparent les versions portables qui embarquent toutes les dépendances nécessaires.

### Emplacement des données

Au premier lancement, l'application tente de créer un dossier `data/` à côté de l'exécutable. En cas d'échec (droits insuffisants), un dossier par défaut est utilisé :

- **Windows** : `%LOCALAPPDATA%/ClinicPortable/`
- **macOS** : `~/Library/Application Support/ClinicPortable/`

Ce dossier contient :

- `db/clinic.sqlite`
- `files/invoices/<année>/`
- `logs/app.log`
- `backups/`
- `config.json`
- `crypto.key.enc`

### Première exécution

1. Au premier lancement, un assistant permet de créer le compte administrateur et de définir le mot de passe maître.
2. Des données de démonstration sont chargées automatiquement (activités OST/DRL, services, patients, consultations, factures).

### Build Windows (portable .exe)

```powershell
# Depuis la racine du projet
./scripts/build_win_portable.ps1
```

Le binaire `dist/ClinicPortable.exe` peut être lancé directement par double-clic. Les frameworks Qt et les ressources sont inclus via PyInstaller. Aucune installation ni privilège administrateur n'est nécessaire.

### Build macOS (bundle .app portable)

```bash
# Depuis la racine du projet
./scripts/build_mac_portable.sh
```

Un bundle `dist/ClinicPortable.app` est généré. Le script crée également une archive `.zip` prête à l'emploi. Au premier lancement sur macOS, maintenez `Ctrl` et cliquez sur l'application puis choisissez **Ouvrir** afin de contourner Gatekeeper.

### Exécution portable

- **Windows** : double-cliquez sur `ClinicPortable.exe`.
- **macOS** : double-cliquez sur `ClinicPortable.app`.

L'application se lance immédiatement en mode fenêtré Qt6 sans navigateur.

## Sauvegardes et restauration

Les sauvegardes créent une archive `.zip` contenant la base de données SQLite, les fichiers PDF générés, la configuration et la clé chiffrée. La restauration remplace les fichiers existants. Il est recommandé d'effectuer des sauvegardes régulières et de les stocker sur un support externe.

## RGPD

Pour chaque patient, il est possible d'exporter l'ensemble des données dans un fichier `.zip` (JSON + PDFs) ou de déclencher une anonymisation logique tout en conservant les pièces comptables.

## Qualité

```bash
pytest
flake8
isort --check-only .
black --check .
```

## Limites connues

- Les dépendances de rendu PDF (WeasyPrint) doivent être présentes sur le système lors du build.
- Les modules d'impression système ne sont pas intégrés par défaut.

## Licence

Ce projet est distribué sous licence MIT. Consultez le fichier `LICENSE` pour plus d'informations.
