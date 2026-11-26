# Guardian

<p align="center">
  <a href="#francais">🇫🇷 Français</a> |
  <a href="#english">🇬🇧 English</a>
</p>

---

<a id="francais"></a>

# 🇫🇷 Français

Le gardien de vos souvenirs.

Guardian sauvegarde vos documents sur une clé USB ou un disque externe, en quelques clics et sans jargon.

- Les dossiers Windows connus (Documents, Images, Musique, Vidéos, Bureau) sont copiés avec leur arborescence sous `Sauvegardes/Documents`, `Sauvegardes/Images`, etc.
- Les autres emplacements sélectionnés sont analysés selon les extensions de fichiers, puis copiés sous `Sauvegardes/Autres emplacements`, sans doublons.
- Protection facultative par mot de passe (dérivation de clé scrypt et chiffrement AES via PyCryptodome).
- Interface PyWebView (HTML/CSS/JS), noyau Python.

## Installation (Windows 11)

Téléchargez l’installateur uniquement depuis https://iactu.info/download. Ce dépôt contient seulement le code source : aucun exécutable n’y est publié.

L’installateur n’est pas signé pour l’instant : Windows peut afficher un avertissement SmartScreen. Consultez [doc/installation_windows.md](doc/installation_windows.md) pour plus de détails.

### Vérifier le téléchargement

Chaque version est publiée sur la page de téléchargement avec un fichier `SHA256SUMS.txt` (une ligne par fichier : empreinte, puis nom du fichier). Dans PowerShell, depuis le dossier de téléchargement, calculez l’empreinte ainsi :

```powershell
Get-FileHash .\Installer-Guardian.exe -Algorithm SHA256
```

Comparez l’empreinte affichée à celle de `SHA256SUMS.txt`. Si elles diffèrent, le fichier est corrompu ou ne correspond pas à celui qui a été publié : ne le lancez pas. L’empreinte vérifie l’intégrité du fichier, mais pas l’identité de l’éditeur, car l’exécutable n’est pas signé. Les empreintes changent à chaque version.

## Lancer depuis les sources

```bash
pip install -r requirements.txt
python main.py
```

Tests : `python test.py`

## Compiler

Prérequis : Python, Nuitka, un compilateur C pris en charge par Nuitka et Inno Setup 6 ou 7 pour créer l’installateur.

```powershell
.\build_win_11.ps1               # Guardian.exe autonome
.\build_win_11.ps1 -Installed    # Variante destinée à l'installateur
.\build_installer_win.ps1        # Installer-Guardian.exe
```

Consultez [doc/installation_windows.md](doc/installation_windows.md). Sous Linux, le script `build_linux_kde_gnome.sh` est disponible, mais n’a pas été validé.

## Organisation

| Dossier | Rôle |
| --- | --- |
| `backend/` | Analyse, sauvegarde, chiffrement et détection des supports |
| `frontend/` | Interface (HTML, CSS, JS, langues française et anglaise) |
| `installer/` | Script Inno Setup |
| `doc/` | Documentation des modules |

## Soutenir le projet

Guardian est gratuit. Un don libre et facultatif aide à financer [iactu.info](https://iactu.info) et son serveur :

https://iactu.info/download

## Licence

Sources consultables, **tous droits réservés** : vous pouvez lire, étudier, exécuter et modifier le code pour un usage personnel et non commercial. Toute redistribution, tout usage commercial ou professionnel, ainsi que toute reprise du code dans un autre projet nécessitent l’accord écrit préalable de l’auteur, qui peut être payant.

Ce logiciel n’est pas open source.

Texte en français et traduction anglaise : [LICENSE](LICENSE).

Composants tiers : [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

<a id="english"></a>

# 🇬🇧 English

The guardian of your memories.

Guardian backs up your documents to a USB flash drive or an external drive in just a few clicks, with no technical jargon.

- Windows known folders (Documents, Pictures, Music, Videos, Desktop) are copied with their folder structure under `Sauvegardes/Documents`, `Sauvegardes/Images`, etc. Destination folder names remain in French.
- Other selected locations are scanned by file extension and copied to `Sauvegardes/Autres emplacements`, without duplicates.
- Optional password protection (scrypt key derivation and AES encryption via PyCryptodome).
- PyWebView interface (HTML/CSS/JS), Python core.

## Install (Windows 11)

Download the installer only from https://iactu.info/download. This repository contains source code only; no executables are published here.

The installer is currently unsigned, so Windows may display a SmartScreen warning. See [doc/installation_windows.md](doc/installation_windows.md) for details.

### Verify the download

Each release is published on the download page with a `SHA256SUMS.txt` file (one line per file: hash, then filename). In PowerShell, from your download folder, calculate the hash with:

```powershell
Get-FileHash .\Installer-Guardian.exe -Algorithm SHA256
```

Compare the displayed hash with the one in `SHA256SUMS.txt`. If they differ, the file is corrupted or does not match the published file: do not run it. The hash verifies file integrity, not the publisher’s identity, because the executable is unsigned. Hashes change with every release.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Tests: `python test.py`

## Build

Prerequisites: Python, Nuitka, a C compiler supported by Nuitka, and Inno Setup 6 or 7 for the installer.

```powershell
.\build_win_11.ps1               # Standalone Guardian.exe
.\build_win_11.ps1 -Installed    # Variant intended for the installer
.\build_installer_win.ps1        # Installer-Guardian.exe
```

See [doc/installation_windows.md](doc/installation_windows.md). The Linux script `build_linux_kde_gnome.sh` is available but has not been validated.

## Structure

| Folder | Purpose |
| --- | --- |
| `backend/` | Scanning, backup, encryption, and storage device detection |
| `frontend/` | User interface (HTML, CSS, JS, French and English languages) |
| `installer/` | Inno Setup script |
| `doc/` | Module documentation |

## Support the project

Guardian is free. Optional donations help fund [iactu.info](https://iactu.info) and its server:

https://iactu.info/download

## License

Source-available, **all rights reserved**: you may read, study, run, and modify the code for personal, non-commercial use. Any redistribution, commercial or professional use, or reuse of the code in another project requires the author’s prior written permission, which may be subject to a fee.

This is not open-source software.

French text and English translation: [LICENSE](LICENSE).

Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
