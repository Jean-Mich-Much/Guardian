# Repérage des souvenirs

## Rôle général

Ce module trouve les dossiers personnels habituels et compte les images, vidéos, documents et autres fichiers qui pourraient être sauvegardés.

Sous Windows, les emplacements viennent des Known Folders de l'utilisateur, résolus par
`SHGetKnownFolderPath` (Documents, Images, Vidéos, Bureau et Musique).
Cela respecte les déplacements configurés dans Windows, par exemple `E:\Images`, au lieu
de supposer que les dossiers se trouvent sous `C:\Users\<nom>`. Les autres systèmes
utilisent les dossiers usuels sous le répertoire personnel.

Le profil courant et les racines des lecteurs locaux fixes sont aussi examinés sur deux
niveaux de dossiers au maximum, sans redécouvrir les Known Folders déjà retenus.
Les dossiers Windows, Program Files, ProgramData, les
répertoires temporaires usuels, cachés et techniques sont exclus de cette découverte.
Lorsqu'un dossier pertinent est repéré, il est parcouru récursivement : seuls les fichiers
aux extensions personnelles reconnues sont retenus, avec un contrôle des marqueurs de
logiciels et d'images disque dans ses sous-dossiers. Un autre support amovible n'est ajouté aux sources que si plusieurs
supports sont connectés et qu'un autre a été retenu comme destination.

La découverte automatique écarte les dossiers qui contiennent un exécutable ou des
marqueurs forts de projet logiciel (`.git`, `pyproject.toml`, `package.json`, `Cargo.toml`,
`go.mod`, etc.), ainsi que leurs sous-dossiers. Un `requirements.txt` ou un `Makefile`
seul, `.vscode` ou `__pycache__` ne suffit pas : il doit aussi y avoir du code ou une
arborescence de sources. Les fichiers `.log` ne sont pas des marqueurs. Les dossiers
ajoutés explicitement restent inclus même s'ils contiennent ces indices ; les Known
Folders restent aussi des sources prioritaires.

Les Known Folders et les éléments explicitement ajoutés sont parcourus sans filtre
automatique d'extensions ou de marqueurs, y compris les dossiers cachés. Les catégories,
la limite de taille et les exclusions choisies restent applicables. Les fichiers de code
non classés dans une autre catégorie apparaissent dans « Autres souvenirs ».
Les liens symboliques vers des dossiers ne sont pas suivis.

Le dossier Téléchargements n'est pas une source automatique, même s'il se trouve dans
un dossier personnel parcouru. Il peut être ajouté explicitement. Les images Clonezilla
et Rescuezilla sont ignorées lors de la découverte si elles contiennent `clonezilla-img`
ou la combinaison `disk`, `parts` et `dev-fs.list` ; une sélection explicite reste possible.
Il n'existe pas de moyen infaillible d'identifier tous les dossiers utilitaires.

Dans un dossier découvert, les volumes Duplicati aux noms par défaut documentés sont
ignorés uniquement si un volume `dblock` et une liste `dlist` sont présents ensemble.
Les autres fichiers du dossier restent sélectionnables. La détection repose sur le nom,
sans ouvrir les archives ; les préfixes personnalisés et jeux incomplets peuvent ne pas
être reconnus. Une sauvegarde Duplicati peut contenir des données importantes : elle
reste intégralement accessible en ajoutant explicitement son dossier, et n'est pas
filtrée dans un Known Folder personnel.

L'étude de logiciels populaires et d'outils de sauvegarde a notamment porté sur
Rescuezilla, Python, Firefox, Docker, Steam, Syncthing, Ventoy, OBS Studio, Ollama,
Visual Studio Code, Rufus, Duplicati, 7-Zip, GIMP, Chrome, Blender, Audacity,
LibreOffice, Thunderbird, KeePassXC, Nextcloud, Krita, Bitwarden, VLC et Veeam.
Cette sélection n'est pas un classement des installations réelles et inclut des
outils étudiés hors classement. Elle ne justifie pas une exclusion par nom de logiciel :
VLC et LibreOffice, par exemple, peuvent produire des fichiers personnels, et des
profils ou dossiers synchronisés peuvent eux aussi contenir des données importantes.

Références : [Known Folders Microsoft](https://learn.microsoft.com/en-us/windows/win32/shell/known-folders),
[extensions courantes Microsoft](https://support.microsoft.com/en-gb/windows/experience/storage-filemanagement/common-file-name-extensions-in-windows)
et [formats Clonezilla et Rescuezilla](https://deepwiki.com/rescuezilla/rescuezilla/4.1-clonezilla-and-redo-backup-formats),
[volumes Duplicati](https://docs.duplicati.com/using-tools/disaster-recovery),
[documents LibreOffice](https://help.libreoffice.org/latest/en-US/text/shared/guide/doc_save.html),
[profils Thunderbird](https://support.mozilla.org/en-US/kb/profiles-tb),
et [dossiers Syncthing](https://docs.syncthing.net/intro/gui.html).

La détection distingue les lecteurs que Windows classe comme fixes et amovibles ; elle
n'identifie pas parfaitement tous les supports USB physiques. Windows peut classer une
clé flash comme lecteur fixe, auquel cas elle peut être analysée comme source.

Les dossiers ajoutés manuellement sont enregistrés dans le profil Guardian. Ils sont
inclus dans « Sauvegarder tous mes fichiers » et peuvent être retirés depuis l'accueil.

## Fonctions principales

- `get_personal_directories()` : réunit les Known Folders, les dossiers repérés et ceux
  ajoutés au profil.
- `discover_personal_directories()` : cherche des fichiers personnels sur une profondeur
  bornée avant d'ajouter un dossier comme source.
- `scan_directories()` : parcourt les dossiers choisis et calcule les compteurs ainsi que la taille totale.

## Mécanismes de stabilité

Le scan et la sauvegarde parcourent récursivement les sous-dossiers en conservant leur
arborescence relative sur la clé. Les dossiers non accessibles sont ignorés et les fichiers
verrouillés ne font pas échouer le diagnostic complet. Les dossiers système, temporaires ou
cachés usuels sont exclus de la découverte automatique, pas des sources de confiance.
