# Moteur de sauvegarde

## Rôle général

Ce module copie les souvenirs vers une clé USB dans une archive datée, reprend les copies interrompues et vérifie que chaque fichier a été enregistré correctement.

## Fonctions principales

- `calculate_sha256()` : calcule l'empreinte numérique d'un fichier.
- `BackupEngine.run()` : lance la sauvegarde complète.
- `pause()` / `resume()` : met la copie en pause ou la reprend.
- `cancel()` : arrête proprement la copie après le fichier en cours.

## Fiabilité

Chaque fichier passe d'abord par un fichier temporaire. Après copie, Guardian vérifie sa taille et son contenu. Les fichiers déjà présents sont réutilisés lorsqu'ils sont identiques. Les erreurs individuelles sont inscrites dans un journal et ne bloquent pas les fichiers suivants. Une archive reçoit un marqueur de validité uniquement après une fin réussie.

La copie laisse Windows utiliser son cache d'écriture au lieu de forcer une synchronisation
à chaque bloc. Entre deux fichiers, Guardian vide le cache dès que 1 Gio a été écrit ou
que 5 minutes se sont écoulées depuis la dernière synchronisation ; un fichier long est
synchronisé à sa fin. Le cache est vidé une dernière fois avant l'annonce de fin. Sous Windows,
`Write-VolumeCache` vise tous les volumes du disque ; sous Linux, Guardian utilise `sync`.
Si la synchronisation finale échoue, Guardian ne dit pas que la clé peut être retirée.
La mémoire vive entière n'est pas vidée et Guardian ne déclenche pas l'éjection physique.

Les Known Folders sont rangés sous `Sauvegardes/Documents`, `Images`, `Musique`,
`Vidéos` et `Bureau`, avec leur arborescence et sans classement par extension. Les
autres sources sont rangées sous `Sauvegardes/Autres emplacements`, en conservant
le nom du dossier source. Les sources superposées ne sont pas copiées deux fois.
Les catégories et les filtres choisis par l'utilisateur continuent à s'appliquer.

Les anciennes sauvegardes restent en place, donc elles peuvent coexister avec la
nouvelle organisation et occuper de l'espace supplémentaire. Si un chemin de la
nouvelle organisation est déjà occupé par un fichier non associé à la même source,
Guardian ne l'écrase pas : il signale le fichier non copié. Un index existant illisible
est conservé et bloque la sauvegarde. Une sauvegarde qui ne trouve aucun fichier ou
qui laisse des fichiers incomplets n'est pas marquée comme valide.

L'index JSON se trouve dans le dossier discret `.guardian` à la racine de la clé, en
dehors de `Sauvegardes`. Il associe chaque fichier archivé à son chemin d'origine, son
dossier source, sa taille et son empreinte SHA-256 d'origine. Lors de la restauration,
Guardian ignore un fichier si son contenu est identique et remplace toute version
différente sans comparer les dates. Sous Windows, le dossier reçoit les
attributs Caché et Système ; sous les systèmes Unix, son nom commençant par un point le
rend caché.

L'index conserve également la catégorie des fichiers de la nouvelle organisation pour
permettre la restauration sélective. En présence d'anciennes et de nouvelles copies
indexées du même fichier, la nouvelle copie est traitée après l'ancienne lors de la
restauration à l'emplacement d'origine.
