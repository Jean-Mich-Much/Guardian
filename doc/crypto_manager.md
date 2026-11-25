# Protection des sauvegardes

## Rôle général

Ce module permet de protéger un fichier optionnellement avec un mot de passe. Il garantit que seul le mot de passe correct peut retrouver le contenu original.

## Fonctions principales

- `derive_key()` : transforme le mot de passe en clé secrète locale.
- `encrypt_file()` : protège un fichier avec un format identifiable par Guardian.
- `decrypt_file()` : restaure un fichier protégé.
- `verify_password()` : vérifie le mot de passe sans déposer de copie déchiffrée sur le disque.

## Fiabilité

- Chaque protection utilise un sel et une valeur aléatoire distincts.
- Le fichier chiffré est écrit dans un temporaire puis remplacé atomiquement.
- Une erreur de mot de passe ou de corruption est rejetée sans écriture du résultat.
