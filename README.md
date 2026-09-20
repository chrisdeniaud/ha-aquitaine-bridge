# ha-aquitaine-bridge

Intégration Home Assistant qui suit les fermetures actuelles et à venir du pont d'Aquitaine (A630, rocade de Bordeaux).

## Pourquoi pas l'API DiaLog ?

Le projet gouvernemental [DiaLog](https://github.com/MTES-MCT/dialog) expose un flux DATEX II national des arrêtés de circulation, avec un filtre géographique par code INSEE de commune (`GET /api/regulations/json?inseeCode=...`). Vérification faite (20/09/2026) : la DIR Atlantique, gestionnaire du pont d'Aquitaine, n'y publie aucun arrêté pour les communes de Bordeaux (33063), Lormont (33249) ou Bruges (33075) - la base DiaLog est vide sur ce périmètre.

La véritable source des fermetures est le site de la DIR Atlantique, qui publie un flux RSS (`spip.php?page=backend-actu`) mis à jour à chaque communiqué. C'est cette source qu'utilise l'intégration.

## Fonctionnement

Le composant interroge périodiquement le flux RSS, ne retient que les articles dont le titre/lien contient un des mots-clés configurés (par défaut `pont d'aquitaine` et `a630`), puis tente d'extraire les plages de fermeture (dates/heures) depuis le texte libre de chaque article. Le format des dates n'est pas structuré côté source : l'extraction est donc "best effort" - un article dont la formulation n'est pas reconnue reste visible (capteur "Dernière actualité") mais ne contribue pas aux capteurs de fermeture.

## Entités créées

- `binary_sensor.fermeture_en_cours` : `on` si une fermeture est en cours actuellement.
- `sensor.prochaine_fermeture` : horodatage (fuseau d'affichage configuré) de la prochaine fermeture prévue (attribut `fermetures_a_venir` avec la liste complète).
- `sensor.derniere_actualite` : titre du dernier communiqué correspondant aux mots-clés, avec lien et description brute en attributs.
- `sensor.statut` : résumé textuel prêt à afficher ("Fermeture en cours jusqu'au ...", "Prochaine fermeture le ...", ou "Aucune fermeture du pont d'Aquitaine prévue" si le switch `always_show` est activé). Devient indisponible si rien à signaler et que le switch est désactivé. Affiche "L'API a évolué, une mise à jour est nécessaire" si la structure du flux change (voir plus bas).
- `switch.toujours_afficher` : quand activé, `sensor.statut` reste toujours disponible, même sans fermeture prévue. Désactivé (par défaut), il devient indisponible plutôt que d'afficher un message vide.

## Installation

### Via HACS

Ce dépôt n'est pas référencé dans le magasin par défaut de HACS ; il doit être ajouté comme dépôt personnalisé :

1. HACS > Intégrations > menu (⋮) > Dépôts personnalisés.
2. URL : `https://github.com/chrisdeniaud/ha-aquitaine-bridge`, catégorie "Intégration".
3. Installer "Pont d'Aquitaine" (version 0.1.0), redémarrer Home Assistant.

### Manuelle

Copier `custom_components/aquitaine_bridge` dans le dossier `custom_components` de Home Assistant, redémarrer.

### Dans les deux cas

Ajouter l'intégration "Pont d'Aquitaine" depuis Paramètres > Appareils et services.

## Configuration

- **URL du flux RSS** : par défaut le flux d'actualités DIR Atlantique.
- **Mots-clés de filtrage** : séparés par des virgules. Réduire à `pont d'aquitaine` seul pour exclure les travaux généraux de la rocade non liés au pont.
- **Intervalle de rafraîchissement** : en minutes (modifiable après coup via les options de l'intégration).
- **Fuseau horaire d'affichage** : pré-rempli avec le fuseau de l'instance Home Assistant, modifiable après coup via les options. Les dates du flux sont toujours écrites en heure française par la DIR Atlantique (interprétation fixe, non configurable) ; ce réglage ne change que le fuseau dans lequel les horodatages sont présentés (attributs `fin`, `fermetures_a_venir`, `publie_le`, texte de `sensor.statut`).

## Robustesse face à une évolution du flux

Le flux RSS n'est pas un contrat d'API stable : à chaque rafraîchissement, l'intégration vérifie que les champs qu'elle exploite réellement (`title`, `link`, `date`/`dc:date` sur les articles) sont toujours présents. Si un changement de structure fait disparaître ces champs de tous les articles, `sensor.statut` bascule sur "L'API a évolué, une mise à jour est nécessaire" (toujours visible, quel que soit le switch `always_show`), tandis que les autres capteurs conservent leur dernière donnée valide plutôt que de tomber en erreur. À l'inverse, l'ajout, la suppression ou le renommage de champs non utilisés par le module (n'importe quelle balise RSS en dehors de `title`/`link`/`date`/`dc:date`) n'a aucun impact : ils ne sont jamais lus.
