# Guardian

Guardian sauvegarde vos documents sur une clé USB ou un disque externe, en quelques clics, sans jargon.

- Dossiers Windows reconnus (Documents, Images, Musique, Vidéos, Bureau) copiés en entier dans `Sauvegardes\Documents`, `Images`, etc.
- Autres emplacements recherchés par extensions, copiés dans `Sauvegardes\Autres emplacements`, sans doublons.
- Protection par mot de passe optionnelle (chiffrement scrypt + AES, via pycryptodome).
- Interface pywebview (HTML/CSS/JS), noyau Python.

## Installer (Windows 11)

Téléchargez l'installateur depuis la page **Releases** du dépôt, ou depuis https://iactu.info/download. Vérifiez le SHA-256 indiqué avec la version.

L'installateur n'est pas signé pour l'instant : Windows peut afficher un avertissement SmartScreen. Détails dans [doc/installation_windows.md](doc/installation_windows.md).

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
