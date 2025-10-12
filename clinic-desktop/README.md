# Clinic Desktop

Application Qt locale pour la gestion d'un cabinet combinant ostéopathie et drainage lymphatique. Le projet fournit une interface moderne en PySide6/QML, une base de données SQLite sécurisée et tous les outils nécessaires pour la facturation, les exports et les sauvegardes hors-ligne.

## Fonctionnalités clés

- Gestion des activités Ostéopathie (OST) et Drainage lymphatique (DRL) avec séquences de factures indépendantes.
- Fiches patients chiffrées, consultations et suivi des paiements.
- Génération de factures PDF locales (ReportLab) et exports comptables CSV/XLSX.
- Sauvegardes/restauration en un clic, conformité RGPD (export/anonymisation).
- Interface Qt Quick Material clair/sombre, navigation clavier et composants accessibles.
- Scripts de build PyInstaller pour Windows (.exe) et macOS (.app).

## Prérequis système

- Python 3.11 ou supérieur.
- Bibliothèques système requises pour Qt 6 et WeasyPrint/ReportLab (Cairo, Pango). Sous macOS, installez via Homebrew :
  ```bash
  brew install cairo pango gdk-pixbuf libffi libjpeg
  ```
- Sous Windows, installez les Visual C++ Redistributables (2015-2022) et assurez-vous que `python` pointe vers Python 3.11.

## Installation développement

1. Clonez le dépôt puis exécutez :
   ```bash
   cd clinic-desktop
   ./scripts/dev_run.sh
   ```
   Le script crée un environnement virtuel `.venv`, installe les dépendances et lance l'application Qt.

2. Pour lancer les tests :
   ```bash
   source .venv/bin/activate
   pytest
   ```

3. Outils qualité :
   ```bash
   black .
   isort .
   flake8
   ```

## Base de données & données de démonstration

- Les données sont stockées dans `data/clinic.sqlite`.
- Un jeu d'activités/services est injecté à chaque lancement de test ou via `python -m app.db.seed`.
- Les PDF sont enregistrés dans `files/invoices/<année>/`.

## Sauvegardes & restauration

- Sauvegarde : `python -m app.domain.backups --backup sauvegarde.zip`
- Restauration : `python -m app.domain.backups --restore sauvegarde.zip`
- Le zip contient : base SQLite, fichiers PDF, `config.json`, clé de chiffrement.

## RGPD

- Export patient :
  ```bash
  python -c "from app.domain import rgpd; from pathlib import Path; rgpd.export_patient_data(1, Path('export_patient.zip'))"
  ```
- Anonymisation :
  ```bash
  python -c "from app.domain import rgpd; rgpd.anonymize_patient(1)"
  ```

## Build des applications

### macOS

#### Lancer l'application en mode développement (débutant)

1. Ouvrez l'application **Terminal** (Spotlight `⌘ + Espace`, tapez « Terminal »).
2. Tapez la commande suivante pour vous placer dans le dossier du projet (adaptez le chemin si nécessaire) :
   ```bash
   cd ~/Téléchargements/clinic-desktop
   ```
3. Lancez le script d'installation et de démarrage :
   ```bash
   ./scripts/dev_run.sh
   ```
   - Au premier lancement, macOS peut bloquer le script : clic droit sur `dev_run.sh` > **Ouvrir**, puis validez.
   - Le script crée automatiquement un environnement Python, installe les dépendances puis affiche la fenêtre de l'application.
4. Lorsque vous souhaitez relancer l'application plus tard :
   ```bash
   source .venv/bin/activate
   python -m app.main
   ```

#### Créer l'application .app (pour double-clic)

```bash
./scripts/build_mac.sh
```

- Produit `dist/Clinic.app`. Pour l'exécuter : clic droit > Ouvrir (contourner Gatekeeper). La signature ad-hoc est effectuée par PyInstaller.

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_win.ps1
```

- Produit `dist/Clinic.exe` et le dossier `dist/Clinic`. L'exécutable est windowed (`--noconsole`).

### Conseils de packaging

- Ajoutez les dépendances Qt `platforms`, `styles` et `imageformats` si PyInstaller ne les détecte pas. Exemple : `--add-data "<venv>/Lib/site-packages/PySide6/plugins/platforms;PySide6/Qt/plugins/platforms"`.
- Pour WeasyPrint, veillez à inclure les bibliothèques de police et `cairo` si utilisées.
- Testez le lancement hors-ligne en double-clic sur la machine cible.

## Maintenance

- Audit log : toutes les opérations critiques sont journalisées dans `audit_logs` (à étendre côté UI).
- Pour réinitialiser le mot de passe maître, supprimez `data/crypto.key.enc` puis relancez l'application (nouvelle initialisation).
- Préparez des sauvegardes régulières via la vue « Sauvegardes » ou le script CLI.

## Licence

Ce projet est distribué sous licence [MIT](LICENSE).
