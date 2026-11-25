# Vérifications système

## Rôle général

Ce module vérifie les éléments simples pouvant perturber une sauvegarde : batterie faible, veille de l'ordinateur et fichiers exceptionnels.

## Fonctions principales

- `get_battery_status()` : indique si l'alimentation est suffisante.
- `prevent_sleep()` : demande au système de rester actif pendant la copie.
- `allow_sleep()` : restitue le fonctionnement normal de veille.
- `get_system_status()` : rassemble les alertes utiles avant la copie.

## Mécanismes de stabilité

Toutes les demandes au système sont protégées par des blocs d'erreur. Si une information n'est pas disponible, Guardian poursuit le diagnostic sans bloquer.
