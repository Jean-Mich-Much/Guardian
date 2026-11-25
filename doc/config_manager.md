# Configuration, verrouillage et conservation

## Rôle général

Ce module centralise les réglages des profils, le verrou Guardian, les journaux locaux et le nettoyage des anciennes sauvegardes.

## Fonctions principales

- `InstanceLock` : refuse une seconde instance ou une seconde opération active.
- `atomic_write_text()` et `atomic_write_json()` : remplacent les fichiers seulement après écriture complète.
- `load_profile()` et `save_profile()` : gèrent les préférences locales.
- `append_log()` : conserve les incidents dans un journal lisible.
- `cleanup_old_archives()` : conserve les versions récentes et protège une sauvegarde valide.

## Fiabilité

Les configurations sont enregistrées dans un fichier temporaire, puis déplacées atomiquement après vidage du disque. Les journaux sont reconstruits puis remplacés, évitant une corruption liée à une interruption. L'objet verrou reste dans l'application tant qu'elle tourne et supprime le fichier de verrou en fin d'utilisation.
