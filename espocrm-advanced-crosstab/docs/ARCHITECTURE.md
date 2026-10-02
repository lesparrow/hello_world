# Architecture

## Layout

```text
files/custom/Espo/Modules/AdvancedCrosstab/
├── Api/                      Action classes (one per route): PostRun, PostValidateFormula, GetDrillDown, PostExport
├── Controllers/              Record controller: standard CRUD for saved crosstabs
├── Classes/
│   ├── ORM/CountDistinct     COUNT_DISTINCT ORM function, registered in metadata app/orm.json
│   └── RecordHooks/          Validates (compiles) a definition before a crosstab is saved
├── Engine/
│   ├── Definition/           Definition, Dimension, Measure value objects + DefinitionParser (structure, limits)
│   ├── Schema/               PathResolver (metadata + ACL), JoinRegistry, ResolvedField
│   ├── Formula/              FormulaParser (EspoCRM parser), ExpressionCompiler (AST → ORM), DisplayEvaluator
│   ├── Filter/               FilterCompiler (filter tree → ORM where), operators
│   ├── Query/                QueryCompiler (base query + expressions), UserContext (time zone, week start)
│   ├── Pivot/                PivotEngine, TreeBuilder (sort / Top N / rank), LabelResolver, ResultCache
│   └── Limits                Server protection limits
├── Tools/
│   ├── ReportService         Load/authorize definitions, run, validate formulas, drill-down
│   └── Export/               Grid (layout), Exporter (CSV/XLSX/HTML/PDF), ValueFormatter, ExportService
├── Jobs/ExportJob            Background export for large results (runs with the requesting user's ACL)
└── Resources/                metadata (entity, scope, clientDefs, recordDefs, dashlet, ORM functions, limits),
                              layouts, routes, i18n (en_US, fr_FR)

files/client/custom/modules/advanced-crosstab/src/
├── lib/                      schema (metadata helper), formatter, operators, styles
└── views/
    ├── advanced-crosstab/    designer (detail/edit page), field-tree, formula-builder, filter-builder,
    │   ├── modals/           dimension, measure, field-picker, drill-down
    │   ├── result/           panel (mode switch, drill-down), table, chart (SVG), kpi
    │   └── fields/           entity-type
    └── dashlets/             advanced-crosstab
```

## Request flow (run)

1. `PostRun` → `ReportService::getDefinition()`: checks the AdvancedCrosstab scope; for a saved crosstab, loads the
   record and checks record-level read access.
2. `DefinitionParser` validates the structure, identifiers, limits and filter tree. It builds a `Definition`.
3. `QueryCompiler::compile()`:
   - checks read access to the data source;
   - resolves each dimension (field path or record formula) and each measure into ORM `Expression`s. All joins
     needed by dimensions, measures and filters go into one `JoinRegistry`, so each relation path is joined once;
   - builds the base query with `SelectBuilderFactory … ->forUser($user)->withStrictAccessControl()`, plus the
     entity's preset filter if one is chosen, then applies the joins and the compiled filter.
4. `PivotEngine::run()`:
   - checks the per-user cache;
   - fetches the detail grouping set (all row and column dimensions) with one `GROUP BY` query;
   - if every measure is decomposable, rolls the detail up into the requested subtotal and total sets in memory.
     Otherwise each requested set (rows[0..i] × columns[0..j]) is its own `GROUP BY` query on the same base query;
   - evaluates display formulas for every cell (in PHP, from aggregated values);
   - builds the row and column header trees (natural order, label or measure sort, Top/Bottom N, ranks) and the
     labels (enum translations, link names in one query per entity, month and day names, quarters, weeks);
   - computes period comparisons along the last date dimension (columns first, then rows);
   - keeps only the cells of visible nodes and returns `{rows, columns, cells, valueColumns, measures, …}`.

## Formula compilation

`FormulaParser` uses `Espo\Core\Formula\Parser`, so the syntax is EspoCRM's: operators, `ifThenElse`,
`string\…`, `datetime\…` and so on. Before parsing, it rewrites `AND` / `OR` and `COUNT(DISTINCT x)` (outside string
literals). Statements, assignments and variables are rejected.

`ExpressionCompiler` walks the AST and produces ORM expressions:

| AST | ORM |
|---|---|
| Attribute `a.b.c` | `PathResolver` → `Expression::column('acxJn.c')` with joins registered |
| Value | `Expression::value()`. The ORM re-quotes it with the PDO driver; backslashes and control characters are rejected |
| Operators | `ADD`, `SUB`, `MUL`, `DIV` (with `NULLIF(divisor, 0)`), `MOD`, comparisons, `AND`/`OR`/`NOT`, `IS NULL` for `== null` |
| Whitelisted functions | ORM functions (`CONCAT`, `LOWER`, `ROUND`, `YEAR_NUMBER`, `TIMESTAMPDIFF_DAY`, `IN`, …) |
| Aggregate functions | `SUM`/`AVG`/`MIN`/`MAX`/`COUNT`/`COUNT_DISTINCT`, only in aggregate mode, never nested; conditions become `IF(cond, value, NULL)` inside the aggregate |

Modes:

- **record**: dimensions, measure values and conditions, filter formulas;
- **aggregate**: fields must be inside an aggregate function;
- **display**: `DisplayEvaluator` validates that every identifier is the key of a previous measure, then evaluates
  per cell. NULL propagates, and division by zero gives NULL.

## Record selectors

`Engine/Query/SelectorJoiner` joins the record picked by a selector once per query. Every field read through the
selector therefore comes from the same row:

```
LEFT JOIN (
    SELECT c.fk k, MAX(c.id) id                -- tie-break on ID (MIN for ascending rules)
    FROM <candidates> c
    JOIN (SELECT fk k, MAX(order) v FROM <candidates> GROUP BY fk) best
         ON best.k = c.fk AND best.v = c.order
    GROUP BY c.fk
) pick ON pick.k = <owner key>
LEFT JOIN related sel ON sel.id = pick.id
```

- **Candidates**: the related records the user can read, with a non-empty order value, that match the optional
  condition.
- **Relation**: resolved by `PathResolver::resolveToMany()`, the same code the related measures use (one-to-many,
  many-to-many through the middle table, children, custom links).
- **Paths**: the `JoinRegistry` treats a selector name as the first segment of paths, so `PathResolver`,
  formulas, filters, drill-down and the data preview support selectors without any change.

## Security model

| Concern | Enforcement |
|---|---|
| Entity access | Scope read check on the data source and on every traversed related entity |
| Record access (data source) | `withStrictAccessControl()` for the user the crosstab runs for |
| Record access (related) | If the related scope's read level is not `all`, the key is first joined to a derived table of the accessible IDs (`LEFT JOIN (SELECT id FROM related WHERE <access-control filter>) acxA ON acxA.id = key`), and the related entity is then joined on `acxA.id`. A derived table is used because EspoCRM 8.x does not support sub-queries in join conditions. Record selectors, related measures and custom links only consider accessible records |
| Field access | `getScopeForbiddenFieldList()` for the final field and for every traversed link, in dimensions, measures, formulas and filters |
| Saved crosstabs | Record ACL (assigned user, teams, collaborators on EspoCRM 9+) to read or edit the definition. The data is always computed with the viewer's ACL |
| Background jobs | The job rebuilds the services with the requesting user and their `Acl` bound (`InjectableFactory::createWithBinding`) |
| SQL injection | No string concatenation into SQL. Identifiers come from metadata, functions from a whitelist, values are bound or quoted by the driver |
| Export injection | CSV labels starting with `= + - @` are prefixed. XLSX labels are written as explicit strings |
| Cache | The key contains the user ID and the full definition. Short TTL (`cacheTtl`) |

## Extension points

- **New formula functions**: add a mapping to `ExpressionCompiler::SIMPLE_FUNCTIONS`, or a `case` for a special
  form. For SQL functions that the ORM doesn't provide, register a `FunctionConverter` in `app/orm.json`, as
  `COUNT_DISTINCT` does.
- **New date granularities**: `QueryCompiler::GRANULARITY_FUNCTIONS`, plus labels in `LabelResolver` and sorting in
  `TreeBuilder`.
- **New filter operators**: `FilterOperators` (server) and `lib/operators` (client).
- **New views** (heatmap, conditional formatting, forecasting…): add a view under `views/advanced-crosstab/result/`
  that consumes the result structure, and register it in `result/panel`.
- **Scheduled or emailed reports, alerts**: a job can run `PivotEngine` with a bound user (see `ExportJob`) and use
  `ExportService::generate()`.
- **AI or natural-language crosstabs**: the definition is plain JSON validated by `DefinitionParser`, so a generator
  only has to produce JSON. Validation, ACL and limits stay on the server.
