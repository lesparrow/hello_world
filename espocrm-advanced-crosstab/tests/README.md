# Tests

End-to-end tests against a real EspoCRM instance (run on EspoCRM 8.3.0 and 10.0.9, MariaDB 10.11, PHP 8.3).
Expected values are computed with direct SQL and compared with the API results.

1. Install EspoCRM and this extension (Administration → Extensions, or copy `files/` into the instance and run
   `php command.php rebuild`).
2. Multi-level relationship tests use a custom `parent` link on Account (stock EspoCRM has none). Copy
   `custom-metadata/Account.json` to `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json`, then rebuild.
3. Seed data from the EspoCRM root: `php seed.php` (copy `seed.php` there first). It creates a "Sales Rep" role
   (Opportunity: own, Account: team, `probability` field hidden), users `alice` / `bob` (password `pass123`),
   accounts, 300 opportunities, contacts (linked to accounts), meetings (children of accounts) and campaigns with a
   non-unique name. Then set account parents:

   ```sql
   UPDATE account SET parent_id = (SELECT id FROM (SELECT id FROM account WHERE name = 'Holding North') x)
       WHERE name IN ('Rabat Retail', 'Kenitra Foods');
   UPDATE account SET parent_id = (SELECT id FROM (SELECT id FROM account WHERE name = 'Holding South') x)
       WHERE name IN ('Casa Steel', 'Paris Mode');
   ```

4. Run: `ESPO_URL=http://127.0.0.1:8080 MYSQL_DB=espo python3 api_test.py` (needs the `mysql` client with root access).

Covered: totals, subtotals and grand totals vs SQL; ratio-of-sums correctness; display and conditional measures;
COUNT DISTINCT; multi-level relations; nested AND/OR/formula filters; ACL (own-only records, team-restricted related
records, forbidden fields, also inside formulas); formula validation errors; SQL-injection attempts; YoY comparison;
Top N and ranks; drill-down totals, paging, empty keys and measure conditions; saved reports (validation on save,
access by another user); CSV/XLSX/PDF export; in-memory roll-up = database aggregation; related measures; custom
links; data preview; record selectors (FIRST / LAST / MIN / MAX / EARLIEST / LATEST, checked against
`ROW_NUMBER()` queries, same-record guarantee, conditions, many-to-many and children links, ACL).
