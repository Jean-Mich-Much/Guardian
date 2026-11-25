# Détection des clés USB

## Rôle général

Ce module recherche les supports amovibles visibles par l'ordinateur. Il fournit à l'application leur emplacement, leur système de fichiers et leur espace libre, sans jargon technique dans les messages destinés aux utilisateurs.

## Fonctions principales

- `detect_usb_devices()` : liste les supports amovibles accessibles.
- `select_backup_device()` : reprend une sauvegarde Guardian existante ; sinon recommande
  le support ayant la plus grande proportion d'espace libre. Une égalité ou plusieurs
  sauvegardes existantes déclenchent un choix explicite.
- `find_usb_for_backup()` : renvoie la recommandation sans choisir arbitrairement en cas d'égalité.
- `get_environment_name()` : indique simplement le système utilisé.

## Mécanismes de stabilité

- Les erreurs d'accès à une partition sont ignorées pour permettre l'analyse des autres supports.
- Les valeurs d'espace sont exprimées en octets afin d'être utilisées de manière fiable dans toute l'application.
- Sous Windows, le type de lecteur amovible est vérifié directement par le système.
- Sous Linux, les périphériques amovibles et les points de montage usuels sont reconnus.
- Les lecteurs fixes locaux, y compris les disques externes que Windows classe comme fixes,
  sont des sources possibles ; les supports amovibles restent exclus sauf si un autre
  support a été choisi comme destination.
- La classification Windows porte sur le lecteur et son média, pas sur une identité USB
  physique parfaite : certaines clés flash sont classées comme lecteurs fixes.

## Encodage et fichiers

Le fichier est en UTF-8 sans BOM et utilise uniquement des fins de ligne LF.
