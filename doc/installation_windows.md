# Installation Windows

L'installateur `Installer-Guardian.exe` installe Guardian pour l'utilisateur courant
dans `%LOCALAPPDATA%\Programs\Guardian`, sans droits administrateur. Il crée des
raccourcis sur le Bureau et dans le menu Démarrer. Il n'importe pas les réglages
d'une éventuelle version portable, qui reste indépendante.

Windows ne permet pas à l'installateur d'épingler directement l'application à la
barre des tâches : ouvrir Guardian, faire un clic droit sur son icône dans la barre
des tâches, puis choisir « Épingler à la barre des tâches ».

Une désinstallation supprime le programme, ses raccourcis, ses réglages et ses caches
installés. Elle ne supprime pas les fichiers personnels ni les sauvegardes. Elle ne
supprime pas non plus la version portable ou son cache. Fermer Guardian avant une
mise à jour ou une désinstallation. Les fichiers étrangers placés à côté du programme
ne sont pas supprimés, mais `GuardianData` est réservé aux données de l'application.

Un ancien raccourci Guardian pointant ailleurs, ou des fichiers Guardian préexistants
dans le dossier d'installation sans installation reconnue, bloquent l'installation
pour éviter leur écrasement. Une mise à jour conserve les réglages installés.

## Affichage

L'assistant s'adapte à l'écran réel : au lancement, sa fenêtre occupe 80 % de la hauteur
utile de l'écran (sans dépasser 92 % de la largeur), et les polices suivent le même
rapport (texte 14 pt, titres 22 pt de base, jamais sous 10 pt ; facteur borné entre 0,6
et 2,5). La fenêtre est centrée et redimensionnable. Contrôlé en simulation sur des
écrans de 1024x730 et 1920x1000 ; non testé sur un écran 4K réel.

## Vérifier le téléchargement

Comparer l'empreinte SHA-256 du fichier téléchargé (`Get-FileHash <fichier> -Algorithm
SHA256` dans PowerShell) à celle de `SHA256SUMS.txt` publié avec le téléchargement.
L'empreinte garantit l'intégrité, pas l'identité de l'éditeur, car l'exécutable n'est pas
signé. Elle change à chaque compilation.

## Compilation

Compiler le programme installable avec `build_win_11.ps1 -Installed`, puis l'installateur
avec `build_installer_win.ps1`. Le second script nécessite Inno Setup 7 ou 6 et accepte
le chemin de `ISCC.exe` avec `-Compiler`. L'exécutable portable `dist\Guardian.exe`
reste distinct. Pour utiliser Inno Setup dans un cadre commercial, vérifier sa licence.

La version courante n'est pas signée numériquement : Windows peut afficher un
avertissement SmartScreen. Il faut également valider l'installation sur un Windows 11
propre avant une diffusion générale.
