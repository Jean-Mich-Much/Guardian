# Point d'entrée et pont natif

## Rôle général

`main.py` ouvre l'interface locale, expose les opérations Python au JavaScript via
pywebview, gère les événements de sauvegarde et ouvre la fenêtre native.

## Communication

- `GuardianApi` expose au JavaScript les fonctions de statut, détection USB, diagnostic,
  sauvegarde, restauration, sélection et mémorisation des dossiers ajoutés, préférences
  et traductions.
- À la fin de la sauvegarde, Guardian vide le cache du support avant d'afficher que la clé
  peut être retirée ; il ne demande pas son éjection au système.
- Les dossiers et fichiers sélectionnés sont enregistrés dans le profil. Ils peuvent être
  inclus dans le parcours « tous les fichiers » ou sauvegardés seuls.
- Le diagnostic distingue photos, vidéos, documents, musique et autres fichiers, tous
  sélectionnés par défaut. Les options facultatives peuvent limiter la copie aux fichiers
  sous une taille réglable (256 Mo par défaut, option désactivée) et exclure des chemins
  choisis pour la sauvegarde en cours.
- Le choix de plusieurs fichiers conserve leur nom et leur dossier parent dans l'archive.
- La restauration remet les fichiers à leur chemin d'origine si le dossier source est
  encore présent. Sinon, elle utilise `Documents/GuardianRestored`, sauf si un autre
  dossier a été choisi. Les fichiers au contenu identique sont ignorés ; les fichiers
  différents sont remplacés sans comparer leurs dates.
- La sélection de catégories pour la restauration utilise l'index pour les nouvelles
  sauvegardes, sans dépendre du nom de leur dossier sur la clé. Les anciennes archives
  conservent leur classement par catégorie.
- Un dossier sur le Bureau contient des raccourcis vers les éléments restaurés. L'index
  des chemins reste dans le dossier discret `.guardian` à la racine de la clé USB.
- La fenêtre charge `frontend/index.html` via une URL `file://`; CSS, scripts, traductions
  et polices restent des ressources locales séparées.
- Le pont pywebview relaie les appels JavaScript vers Python par le mécanisme natif du
  moteur WebView ; Guardian ne démarre pas de serveur HTTP ni de socket TCP.
- `poll_events()` vide la file Python des événements de progression.

## Démarrage

`main()` acquiert le verrou d'instance et ouvre la fenêtre avec
`webview.create_window(url=..., js_api=...)`. L'URL `file://` charge directement les
fichiers embarqués et `http_server=False` désactive le serveur intégré.

`--self-test` vérifie les ressources locales et les traductions sans ouvrir de fenêtre ni
écouter sur le réseau.

## Distribution Windows 11

L'exécutable Nuitka est autonome vis-à-vis du redistribuable Visual C++ : le rapport de
build vérifie que `vcruntime140.dll` et `vcruntime140_1.dll`, requises par les extensions
Python, sont embarquées à la racine du paquet onefile. Le lanceur dépend seulement de
l'UCRT fourni par Windows 11. Le moteur Evergreen WebView2 est également fourni avec
Windows 11. Le build refuse de remplacer l'exécutable précédent si le nouveau dépasse
256 Mio.
