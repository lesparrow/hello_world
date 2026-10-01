# Extension EspoCRM « Crosstab » (tableaux croisés)

Ajoute un onglet **Tableau croisé** à EspoCRM (≥ 8.0, PHP ≥ 8.1) qui sert à croiser deux champs de n'importe quelle entité
(Comptes, Opportunités, Leads, entités personnalisées…) et à calculer un agrégat pour chaque combinaison.

## Fonctionnalités

- Lignes / colonnes : champs `enum`, `varchar`, `bool`, `link`, `int`, `date`, `datetime`
  (dates regroupées par année, trimestre, mois ou jour).
- Agrégats : nombre, somme, moyenne, min, max (sur `int`, `float` et `currency`).
- Filtres prédéfinis de l'entité (filtres primaires).
- Affichage en valeurs, en % de la ligne, en % de la colonne ou en % du total.
- Totaux par ligne et par colonne, et total général.
- Carte de chaleur, tri en cliquant sur un en-tête, inversion lignes/colonnes, export CSV (compatible Excel).
- Dernière configuration mémorisée par utilisateur.

## Optimisations

- **Agrégation côté base de données** : une seule requête `GROUP BY`, au lieu de charger tous les enregistrements dans le
  navigateur. Le volume transféré dépend du nombre de cellules et non du nombre d'enregistrements.
- Les totaux additifs (nombre, somme) sont calculés à partir des cellules, sans requête supplémentaire. Pour la moyenne,
  le min et le max, les totaux viennent de la base, ce qui les rend exacts.
- Les noms des enregistrements liés sont récupérés en une seule requête (pas de requête N+1).
- L'inversion lignes/colonnes est une simple transposition côté client, sans nouvel appel au serveur.
- Les réponses arrivées après une requête plus récente sont ignorées.
- Le tableau est construit en une seule écriture dans le DOM.
- Le résultat est limité à 20 000 cellules, avec un avertissement si la limite est atteinte.

## Sécurité

- Les droits de lecture sur l'entité, les droits par champ et les restrictions par équipe ou par propriétaire s'appliquent
  (`withStrictAccessControl`).
- Les noms de champs sont validés à partir des métadonnées. Aucune donnée saisie n'est injectée dans le SQL.
- Les rôles disposent d'une permission dédiée, `Crosstab`.

## Installation

```bash
./build.sh            # crée dist/crosstab-1.0.0.zip
```

Ensuite : Administration → Extensions → importer le zip → Installer.
L'onglet est ajouté automatiquement à la barre de navigation. Pensez à activer la permission `Crosstab` dans les rôles
des utilisateurs qui ne sont pas administrateurs.

## Limites connues

- Pour les champs `datetime`, les dates sont regroupées en UTC, sans conversion vers le fuseau horaire de l'utilisateur.
- Pour les champs `currency`, les montants sont agrégés tels quels, sans conversion de devise.
