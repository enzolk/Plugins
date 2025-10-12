# Clinic Local – Gestion d'un cabinet d'ostéopathie et de drainage lymphatique

Clinic Local est une application web 100 % locale destinée aux cabinets mixtes (Ostéopathie et Drainage lymphatique). Elle fonctionne sans aucune dépendance cloud et tourne sur macOS (Intel ou Apple Silicon) avec une interface web locale (`http://localhost:8000`).

## Fonctionnalités principales

- Gestion des utilisateurs avec rôles (admin, praticien, assistant) et mots de passe chiffrés (Argon2).
- Paramétrage complet du cabinet : coordonnées, informations fiscales, logo, comptes bancaires, activités, modèles PDF.
- Activités Ostéopathie et Drainage lymphatique créées par défaut avec séquences de facturation séparées.
- Gestion des actes/services par activité.
- Base patients avec notes chiffrées, tags, consentement RGPD et historiques de consultations.
- Agenda minimal (hebdomadaire/mensuel) avec création/modification/suppression des rendez-vous.
- Consultations, actes et liaisons aux factures.
- Facturation PDF avec WeasyPrint, gestion de la TVA, acomptes, avoirs, paiements multiples et suivi des impayés.
- Rapports comptables et exports CSV/XLSX.
- Sauvegardes locales (ZIP) incluant base de données, fichiers PDF et configuration.
- Page RGPD : export des données patient, anonymisation.
- Journal d’audit des actions importantes.
- Interface en français (fichiers `locales/fr.json`).
- Tests unitaires et d’intégration (pytest) couvrant les modules critiques (numérotation, facturation, API).

## Architecture

- **Backend** : FastAPI, SQLAlchemy, Alembic, Pydantic, Typer.
- **Base de données** : SQLite (fichier local `data/db.sqlite`).
- **Frontend** : Templates Jinja2, HTMX, TailwindCSS (build local sans CDN).
- **PDF** : WeasyPrint avec fonts locales.
- **Exports** : CSV natif, XLSX via OpenPyXL.

L'application est packagée pour rester entièrement locale : aucune ressource externe n'est chargée, toutes les polices, scripts et feuilles de style sont fournies.

## Installation (macOS)

### 1. Prérequis

- Python 3.11 ou supérieur (installé via Homebrew ou pyenv).
- `git` (pour cloner ce dépôt).
- Outil de virtualisation Python (`venv`).
- `node` **facultatif** si vous souhaitez régénérer Tailwind (un binaire pré-compilé est inclus sinon).
- `brew install weasyprint` installe les dépendances système nécessaires (pango, cairo, gdk-pixbuf). Sur Apple Silicon, exécutez également `brew install libffi` puis `export LDFLAGS="-L/opt/homebrew/opt/libffi/lib"` avant d’installer les dépendances Python.

### 2. Clonage

```bash
git clone https://example.com/clinic-local.git
cd clinic-local
```

### 3. Configuration de l’environnement

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copiez le fichier `.env.example` vers `.env` puis ajustez les valeurs selon votre environnement (clé de chiffrement, secrets, chemins). Les chemins sont relatifs au répertoire du projet.

### 4. Base de données et données de démo

Initialisez la base et chargez les données de démonstration :

```bash
alembic upgrade head
python -m app.cli seed
```

### 5. Lancement

#### Option la plus simple (double clic)

1. Dans le Finder, ouvrez le dossier du projet puis double-cliquez sur `Launch.command`.
2. Au premier lancement, macOS peut afficher un avertissement. Faites un clic droit → **Ouvrir** → **Ouvrir** pour autoriser l’exécution.
3. Le terminal affiche la progression (création/activation de l’environnement virtuel, installation des dépendances, migrations, données de démo) puis démarre le serveur Uvicorn.
4. Dès que le serveur répond, le navigateur par défaut s’ouvre automatiquement sur `http://localhost:8000`.

Le terminal reste ouvert et diffuse les logs. Pour arrêter l’application, revenez dans la fenêtre Terminal et pressez `Ctrl+C`. En cas d’erreur au démarrage, un message explicite s’affiche et il suffit d’appuyer sur Entrée pour fermer la fenêtre.

#### Option ligne de commande

```bash
./run.sh
```

Vous pouvez également utiliser `make dev` pour lancer le serveur en mode développement ou `make start` pour un lancement standard.

### 6. Identifiants de démonstration

- **Admin** : `admin@example.com` / `admin123`
- **Praticien** : `praticien@example.com` / `demo123`
- **Assistant** : `assistant@example.com` / `demo123`

Vous pouvez réinitialiser les mots de passe via l’interface d’administration.

## Construction de TailwindCSS

Le fichier `app/static/css/tailwind.css` est fourni précompilé. Pour le reconstruire :

```bash
npm install
npm run build:css
```

ou, sans Node.js, utilisez le binaire `tailwindcss` présent dans `bin/` :

```bash
./bin/tailwindcss -i app/static/css/input.css -o app/static/css/tailwind.css
```

## Sauvegardes & restauration

Utilisez les commandes Typer :

```bash
python -m app.cli backup --output backups/backup-$(date +%Y%m%d).zip
python -m app.cli restore backups/backup-20250101.zip
```

La sauvegarde contient :

- `data/db.sqlite`
- le dossier `files/`
- `config.json`

## Exports comptables

```bash
python -m app.cli export-sales --activity=OST --from=2025-01-01 --to=2025-12-31 --format=xlsx
```

Les fichiers sont générés dans `exports/`.

## Résolution de problèmes

- **WeasyPrint** : assurez-vous que les bibliothèques système (cairo, pango, gdk-pixbuf) sont installées. Sur macOS, `brew install cairo pango gdk-pixbuf` résout la plupart des problèmes. Si la génération PDF échoue, consultez les logs dans `logs/app.log`.
- **Permissions** : vérifiez que vous avez les droits en écriture sur `data/`, `files/` et `exports/`.
- **Port occupé** : modifiez `UVICORN_HOST` / `UVICORN_PORT` dans `.env`.
- **Mots de passe oubliés** : utilisez la commande `python -m app.cli reset-password --email=user@example.com`.

## Politique RGPD

- Les notes patient sont chiffrées localement (Fernet) avec une clé stockée dans `.env`.
- Page dédiée `/rgpd` pour exporter les données d’un patient (JSON + PDF) et effectuer l’anonymisation logique.
- Les sauvegardes sont locales ; vous êtes responsable de leur stockage.
- Les logs d’audit tracent les connexions, modifications et exports.

## Limitations connues

- Agenda simple (pas de drag & drop, pas de synchronisation externe).
- Pas d’envoi d’emails intégré (export PDF manuel).
- Multi-utilisateurs : aucune gestion de concurrence avancée (optimistic locking basique).

## Tests automatisés

Lancer la suite de tests Pytest pour vérifier les fonctionnalités critiques :

```bash
pytest
```

Des avertissements peuvent apparaître concernant `passlib` sous Python 3.13 et l’utilisation de `@app.on_event`. Ils sont connus et n’empêchent pas l’exécution correcte des tests.

## Structure du projet

Consultez l’arborescence décrite dans le dossier pour comprendre la séparation des responsabilités : configuration, modèles, services métiers, routeurs FastAPI, templates Jinja2, tests.

## Licence

Projet distribué sous licence MIT. Voir le fichier `LICENSE`.

