# Per-entity presets

A preset is the default layout used when a crosstab is opened from an entity's list ("Pivot" button) or when that
entity is picked as a data source. It lives in the entity's client metadata under the `advancedCrosstab` key:
`rows`, `columns`, `measures`, `filter`, `options` (same format as a crosstab definition). Set
`"advancedCrosstab": {"disabled": true}` to hide the Pivot button on an entity's list.

The files here reproduce the default pivots of the forestry dashboard (Besoins, Marchés, Périmètres,
Allotissement, Travaux). To install one, copy it to
`custom/Espo/Custom/Resources/metadata/clientDefs/<Entity>.json` (or merge its content into that file if it exists),
then clear the cache (Administration → Clear Cache).

These presets have **not been checked against the real entity definitions**. The dashboard's field keys were
converted as follows: `xxxName` keys became the link `xxx` (for example `programmeName` → `programme`), and
browser-computed fields (`computed_*`) were dropped. If a field turns out to be a link, an enum or a varchar under
another name, adjust its `path`. The designer shows an `Invalid field: …` error for any path that doesn't exist.

| File | Rows | Columns | Measures |
|---|---|---|---|
| `LigneBesoinPlants.json` (Besoins) | DRANEF | Action | Sum of Nombre plants |
| `CMarche.json` (Marchés) | Programme | État | Sum of Montant marché |
| `FicheAction.json` (Périmètres) | DRANEF | Composante biologique (Action) | Sum of Superficie |
| `CLotTechnique.json` (Allotissement) | DRANEF | Plantation / Regarni | Sum of Montant estimatif |
| `CLigneDeSuiviPlantation.json` (Travaux) | DRANEF › DPANEF | Situation (week) | Sums of Préparation du sol and Plantation |
