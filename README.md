# Guardian

Guardian sauvegarde vos documents sur une clé USB ou un disque externe, en quelques clics, sans jargon.

- Dossiers Windows reconnus (Documents, Images, Musique, Vidéos, Bureau) copiés en entier dans `Sauvegardes\Documents`, `Images`, etc.
- Autres emplacements recherchés par extensions, copiés dans `Sauvegardes\Autres emplacements`, sans doublons.
- Protection par mot de passe optionnelle (chiffrement scrypt + AES, via pycryptodome).
- Interface pywebview (HTML/CSS/JS), noyau Python.

## Installer (Windows 11)

Téléchargez l'installateur uniquement depuis https://iactu.info/download. Ce dépôt ne contient que le code source : aucun exécutable n'y est publié. Vérifiez le SHA-256 indiqué avec le téléchargement.

L'installateur n'est pas signé pour l'instant : Windows peut afficher un avertissement SmartScreen. Détails dans [doc/installation_windows.md](doc/installation_windows.md).

### Vérifier le téléchargement

Chaque version est publiée sur la page de téléchargement avec un fichier `SHA256SUMS.txt` (une ligne par fichier : empreinte, puis nom). Dans PowerShell, depuis le dossier du téléchargement :

```
Get-FileHash .\Installer-Guardian.exe -Algorithm SHA256
```

Comparez l'empreinte affichée à celle de `SHA256SUMS.txt`. Si elles diffèrent, le fichier est corrompu ou n'est pas celui publié : ne le lancez pas. L'empreinte prouve l'intégrité du fichier, pas l'identité de l'éditeur, puisque l'exécutable n'est pas signé. Les empreintes changent à chaque version.

## Lancer depuis les sources

```
pip install -r requirements.txt
python main.py
```

Tests : `python test.py`

## Compiler

Prérequis : Python, Nuitka, un compilateur C supporté par Nuitka, et Inno Setup 7 pour l'installateur.

```
.\build_win_11.ps1               # Guardian.exe autonome
.\build_win_11.ps1 -Installed    # variante destinée à l'installateur
.\build_installer_win.ps1        # Installer-Guardian.exe
```

Voir [doc/installation_windows.md](doc/installation_windows.md). Linux : `build_linux_kde_gnome.sh` (non validé).

## Organisation

| Dossier | Rôle |
| --- | --- |
| `backend/` | Analyse, sauvegarde, chiffrement, détection des supports |
| `frontend/` | Interface (HTML, CSS, JS, langues fr/en) |
| `installer/` | Script Inno Setup |
| `doc/` | Documentation des modules |

## Soutenir le projet

Le logiciel Guardian est gratuit, avec un don libre et facultatif. S'il vous est utile, un don aide à financer [iactu.info](https://iactu.info) et son serveur : https://iactu.info/download

## Licence

Sources consultables, **tous droits réservés** : vous pouvez lire le code, l'étudier, le lancer et le modifier pour un usage personnel non commercial. Toute redistribution, tout usage commercial ou professionnel et toute reprise du code dans un autre projet nécessitent l'accord écrit préalable de l'auteur, qui peut être payant. Ce n'est pas un logiciel open source. Texte en français, avec traduction anglaise : [LICENSE](LICENSE). Composants tiers : [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

# Guardian

Guardian backs up your documents to a USB drive or external disk in just a few clicks, without technical jargon.

- Windows known folders (Documents, Pictures, Music, Videos, Desktop) are copied entirely into `Backups\Documents`, `Pictures`, etc.
- Other locations are scanned by file extension and copied into `Backups\Other locations`, without duplicates.
- Optional password protection (scrypt + AES encryption via pycryptodome).
- PyWebView interface (HTML/CSS/JS), Python backend.

## Install (Windows 11)

Download the installer only from https://iactu.info/download. This repository contains source code only: no executables are published here. Verify the SHA-256 checksum provided with the download.

The installer is currently unsigned: Windows may display a SmartScreen warning. See [doc/installation_windows.md](doc/installation_windows.md) for details.

### Verify the download

Each version is published on the download page with a `SHA256SUMS.txt` file (one line per file: checksum followed by filename). In PowerShell, from the download folder:

```powershell
Get-FileHash .\Installer-Guardian.exe -Algorithm SHA256
```

Compare the displayed checksum with the one listed in `SHA256SUMS.txt`. If they differ, the file is corrupted or is not the published file. Do not run it. The checksum verifies file integrity, not the publisher's identity, since the executable is not signed. Checksums change with every version.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Tests:

```bash
python test.py
```

## Build

Requirements: Python, Nuitka, a C compiler supported by Nuitka, and Inno Setup 7 for the installer.

```powershell
.\build_win_11.ps1               # standalone Guardian.exe
.\build_win_11.ps1 -Installed    # version intended for the installer
.\build_installer_win.ps1        # Installer-Guardian.exe
```

See [doc/installation_windows.md](doc/installation_windows.md). Linux: `build_linux_kde_gnome.sh` (not validated).

## Project structure

| Folder | Purpose |
| --- | --- |
| `backend/` | Analysis, backup, encryption, storage device detection |
| `frontend/` | User interface (HTML, CSS, JS, French/English translations) |
| `installer/` | Inno Setup script |
| `doc/` | Module documentation |

## Support the project

Guardian is free software supported by optional donations. If you find it useful, a donation helps fund iactu.info and its server:

https://iactu.info/download

## License

Source-available, **all rights reserved**: you may read, study, run, and modify the code for personal, non-commercial use. Any redistribution, commercial or professional use, or reuse of the code in another project requires prior written permission from the author, which may be subject to a licensing fee.

This is not open-source software. French text, with English translation: [LICENSE](LICENSE). Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
