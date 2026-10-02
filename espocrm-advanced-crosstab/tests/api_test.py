#!/usr/bin/env python3
"""
End-to-end API tests for the Advanced Crosstab extension.

Requires a running EspoCRM instance with the extension installed and the data from tests/seed.php.
Expected values are computed with direct SQL (mysql CLI) and compared with the API results.

    ESPO_URL=http://127.0.0.1:8080 MYSQL_DB=espo python3 tests/api_test.py
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get('ESPO_URL', 'http://127.0.0.1:8080') + '/api/v1/'
DB = os.environ.get('MYSQL_DB', 'espo')

ADMIN = ('admin', 'admin123')
ALICE = ('alice', 'pass123')

failures = []


def call(method, path, body=None, auth=ADMIN, query=None):
    url = URL + path + ('?' + urllib.parse.urlencode(query) if query else '')
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header('Content-Type', 'application/json')
    request.add_header('Authorization', 'Basic ' + base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode())
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or b'null'), None
    except urllib.error.HTTPError as e:
        return e.code, None, e.headers.get('X-Status-Reason')


def run(definition, auth=ADMIN):
    status, result, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': definition, 'noCache': True}, auth)
    if status != 200:
        raise AssertionError(f'run failed: {status} {reason}')
    return result


def sql(query):
    out = subprocess.run(['mysql', '-uroot', DB, '-N', '-B', '-e', query], capture_output=True, text=True, check=True)
    return [line.split('\t') for line in out.stdout.strip().split('\n') if line]


def user_id(name):
    return sql(f"SELECT id FROM user WHERE user_name = '{name}'")[0][0]


def check(name, condition, detail=''):
    if condition:
        print(f'  ok    {name}')
    else:
        print(f'  FAIL  {name} {detail}')
        failures.append(name)


def cell(result, row, column, index=0):
    return result['cells'].get(json.dumps(row, ensure_ascii=False, separators=(',', ':')), {}) \
        .get(json.dumps(column, ensure_ascii=False, separators=(',', ':')), [None] * 10)[index]


def close(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.01


OPP = "FROM opportunity o LEFT JOIN account a ON a.id = o.account_id AND a.deleted = 0 WHERE o.deleted = 0"

MEASURES = [
    {'key': 'revenue', 'label': 'Revenue', 'aggregation': 'SUM', 'expression': 'amount'},
    {'key': 'orders', 'label': 'Orders', 'aggregation': 'COUNT'},
]


def test_totals():
    print('Totals and subtotals (SUM, COUNT)')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'account.industry'}, {'path': 'stage'}],
        'columns': [{'path': 'closeDate', 'granularity': 'year'}],
        'measures': MEASURES,
    })
    total, count = sql(f"SELECT SUM(o.amount), COUNT(*) {OPP}")[0]
    check('grand total', close(cell(result, [], []), total), f"{cell(result, [], [])} != {total}")
    check('grand count', close(cell(result, [], [], 1), count))

    expected = sql(f"SELECT a.industry, SUM(o.amount) {OPP} AND a.industry = 'Retail' GROUP BY a.industry")[0][1]
    check('row subtotal (Retail)', close(cell(result, ['Retail'], []), expected))

    expected = sql(f"SELECT SUM(o.amount) {OPP} AND a.industry = 'Retail' AND o.stage = 'Closed Won' AND YEAR(o.close_date) = 2026")[0][0]
    check('leaf cell (Retail / Closed Won / 2026)', close(cell(result, ['Retail', 'Closed Won'], ['2026']), expected))

    expected = sql(f"SELECT SUM(o.amount) {OPP} AND YEAR(o.close_date) = 2025")[0][0]
    check('column total (2025)', close(cell(result, [], ['2025']), expected))

    empty = sql(f"SELECT SUM(o.amount) {OPP} AND a.industry IS NULL")[0][0]
    check('empty bucket (no account)', close(cell(result, [''], []), empty))

    check('hierarchical rows', all('c' in node for node in result['rows']))


def test_ratio_correctness():
    print('Aggregate formulas: ratio of sums at every level, not average of ratios')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'account.name'}],
        'measures': [
            {'key': 'winRate', 'label': 'Win rate %', 'kind': 'aggregate',
             'formula': "SUM(ifThenElse(stage == 'Closed Won', amount, 0)) / SUM(amount) * 100"},
            {'key': 'avgDeal', 'label': 'Average deal', 'kind': 'aggregate', 'formula': 'SUM(amount) / COUNT(id)'},
        ],
    })
    total_rate = sql(f"SELECT SUM(IF(o.stage = 'Closed Won', o.amount, 0)) / SUM(o.amount) * 100 {OPP}")[0][0]
    check('grand total ratio', close(cell(result, [], []), total_rate), f"{cell(result, [], [])} vs {total_rate}")
    average_of_ratios = sql(
        f"SELECT AVG(r) FROM (SELECT SUM(IF(o.stage = 'Closed Won', o.amount, 0)) / SUM(o.amount) * 100 r {OPP} GROUP BY a.name) t"
    )[0][0]
    check('differs from average of ratios', not close(total_rate, average_of_ratios))
    avg = sql(f"SELECT AVG(o.amount) {OPP}")[0][0]
    check('SUM/COUNT total', close(cell(result, [], [], 1), avg))


def test_display_and_conditional():
    print('Display formula and conditional measures')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'stage'}],
        'measures': [
            {'key': 'revenue', 'label': 'Revenue', 'aggregation': 'SUM', 'expression': 'amount'},
            {'key': 'retail', 'label': 'Retail revenue', 'aggregation': 'SUM', 'expression': 'amount',
             'condition': "account.industry == 'Retail'"},
            {'key': 'share', 'label': 'Retail share %', 'kind': 'display', 'formula': 'retail / revenue * 100'},
            {'key': 'accounts', 'label': 'Accounts', 'aggregation': 'COUNT_DISTINCT', 'expression': 'accountId'},
        ],
    })
    retail = sql(f"SELECT SUM(o.amount) {OPP} AND a.industry = 'Retail'")[0][0]
    check('conditional SUM', close(cell(result, [], [], 1), retail))
    total = sql(f"SELECT SUM(o.amount) {OPP}")[0][0]
    check('display formula', close(cell(result, [], [], 2), float(retail) / float(total) * 100))
    distinct = sql(f"SELECT COUNT(DISTINCT o.account_id) {OPP}")[0][0]
    check('COUNT DISTINCT', close(cell(result, [], [], 3), distinct))


def test_multi_level_relations():
    print('Multi-level relationships')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'account.parent.industry'}],
        'measures': MEASURES,
    })
    expected = sql(
        "SELECT SUM(o.amount) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 "
        "JOIN account p ON p.id = a.parent_id AND p.deleted = 0 WHERE o.deleted = 0 AND p.industry = 'Finance'"
    )[0][0]
    check('account.parent.industry = Finance', close(cell(result, ['Finance'], []), expected))

    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'assignedUser.name'}],
        'measures': MEASURES,
    })
    check('person name through relation', any(node['k'] == 'Alice' for node in result['rows']),
          str([n['k'] for n in result['rows']]))


def test_filters():
    print('Filters')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'stage'}],
        'measures': MEASURES,
        'filter': {'type': 'and', 'items': [
            {'type': 'condition', 'path': 'closeDate', 'operator': 'dateBetween', 'value': ['2025-01-01', '2025-03-31']},
            {'type': 'or', 'items': [
                {'type': 'condition', 'path': 'account.industry', 'operator': 'equals', 'value': 'Retail'},
                {'type': 'condition', 'path': 'account.billingAddressCountry', 'operator': 'equals', 'value': 'Spain'},
            ]},
            {'type': 'formula', 'formula': 'amount > 20000'},
        ]},
    })
    expected = sql(
        f"SELECT SUM(o.amount) {OPP} AND o.close_date BETWEEN '2025-01-01' AND '2025-03-31' "
        "AND (a.industry = 'Retail' OR a.billing_address_country = 'Spain') AND o.amount > 20000"
    )[0][0]
    check('nested AND/OR + related + formula filter', close(cell(result, [], []), expected),
          f"{cell(result, [], [])} vs {expected}")

    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'stage'}],
        'measures': MEASURES,
        'filter': {'type': 'condition', 'path': 'stage', 'operator': 'in', 'value': ['Closed Won', 'Closed Lost']},
    })
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.stage IN ('Closed Won', 'Closed Lost')")[0][0]
    check('enum IN filter', close(cell(result, [], [], 1), expected))


def test_acl():
    print('Security (ACL, record-level, field-level)')
    alice = user_id('alice')
    result = run({'entityType': 'Opportunity', 'rows': [{'path': 'stage'}], 'measures': MEASURES}, ALICE)
    expected = sql(f"SELECT COUNT(*) FROM opportunity WHERE deleted = 0 AND assigned_user_id = '{alice}'")[0][0]
    check('own-only records', close(cell(result, [], [], 1), expected), f"{cell(result, [], [], 1)} vs {expected}")

    result = run({'entityType': 'Opportunity', 'rows': [{'path': 'account.name'}], 'measures': MEASURES}, ALICE)
    names = {node['k'] for node in result['rows']}
    visible = {r[0] for r in sql(
        "SELECT a.name FROM account a JOIN entity_team et ON et.entity_id = a.id AND et.entity_type = 'Account' "
        "AND et.deleted = 0 JOIN team t ON t.id = et.team_id AND t.name = 'North' WHERE a.deleted = 0"
    )}
    check('related records restricted to accessible ones', names - {''} <= visible, f"{names} vs {visible}")

    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'rows': [{'path': 'stage'}],
        'measures': [{'key': 'p', 'aggregation': 'AVG', 'expression': 'probability'}]}}, ALICE)
    check('forbidden field rejected', status == 400 and 'Invalid field' in (reason or ''), f"{status} {reason}")

    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'rows': [{'path': 'stage'}],
        'measures': [{'key': 'p', 'kind': 'aggregate', 'formula': 'SUM(ifThen(probability > 50, 1, 0))'}]}}, ALICE)
    check('forbidden field rejected inside formulas', status == 400, f"{status} {reason}")

    status, _, _ = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Contract', 'rows': [], 'measures': MEASURES}}, ALICE)
    check('no access to entity', status in (400, 403))


def test_validation_and_injection():
    print('Formula validation and injection safety')

    def validate(formula, kind='record'):
        return call('POST', 'AdvancedCrosstab/action/validateFormula',
                    {'entityType': 'Opportunity', 'formula': formula, 'kind': kind})[1]

    r = validate('account.discount * 2')
    check('invalid related field', not r['valid'] and 'Invalid field: account.discount' in r['error'], str(r))
    r = validate('amount * (2')
    check('invalid syntax', not r['valid'] and 'syntax' in r['error'].lower(), str(r))
    r = validate('amount - 1')
    check('valid record formula with preview', r['valid'] and len(r['preview']['values']) > 0, str(r))
    r = validate('SUM(amount) - SUM(amount) / 2', 'aggregate')
    total = float(sql(f"SELECT SUM(o.amount) {OPP}")[0][0])
    check('aggregate preview', r['valid'] and close(r['preview']['value'], total / 2), str(r))
    r = validate('amount - cost', 'aggregate')
    check('field outside aggregate rejected', not r['valid'], str(r))
    r = validate('SUM(amount)', 'record')
    check('aggregate in record formula rejected', not r['valid'], str(r))
    r = validate("stage == 'x'' OR 1=1; DROP TABLE account; --'", 'condition')
    check('injection in literal is harmless', sql("SELECT COUNT(*) FROM account")[0][0] == '8', str(r))
    r = validate("name == 'a\\\\' OR 1=1 -- '", 'condition')
    check('backslash literal rejected', not r['valid'], str(r))
    status, _, _ = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'rows': [{'path': 'stage`; DROP TABLE account; --'}], 'measures': MEASURES}})
    check('malicious path rejected', status == 400)
    r = validate('$x = 1')
    check('assignments rejected', not r['valid'], str(r))


def test_dates_compare_topn():
    print('Date intelligence, comparisons, Top N')
    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'closeDate', 'granularity': 'month'}],
        'columns': [{'path': 'closeDate', 'granularity': 'year', 'id': 'cy'}],
        'measures': [{'key': 'revenue', 'label': 'Revenue', 'aggregation': 'SUM', 'expression': 'amount',
                      'compare': 'previousYear'}],
    })
    r25 = float(sql(f"SELECT SUM(o.amount) {OPP} AND YEAR(o.close_date) = 2025 AND MONTH(o.close_date) = 3")[0][0])
    r26 = float(sql(f"SELECT SUM(o.amount) {OPP} AND YEAR(o.close_date) = 2026 AND MONTH(o.close_date) = 3")[0][0])
    check('YoY % (March 2026 vs 2025)', close(cell(result, ['3'], ['2026'], 1), (r26 - r25) / r25 * 100),
          f"{cell(result, ['3'], ['2026'], 1)} vs {(r26 - r25) / r25 * 100}")
    check('month labels', result['rows'][0]['l'] == 'January', result['rows'][0]['l'])

    result = run({
        'entityType': 'Opportunity',
        'rows': [{'path': 'account.name', 'limit': {'type': 'top', 'count': 3, 'measure': 'revenue'},
                  'sort': {'by': 'measure', 'measure': 'revenue', 'direction': 'desc'}}],
        'measures': MEASURES,
    })
    top = [r[0] for r in sql(f"SELECT a.name {OPP} GROUP BY a.name ORDER BY SUM(o.amount) DESC LIMIT 3")]
    check('Top 3 by revenue', [n['k'] for n in result['rows']] == top, f"{[n['k'] for n in result['rows']]} vs {top}")
    check('ranks', [n.get('r') for n in result['rows']] == [1, 2, 3])


def test_drill_down():
    print('Drill-down')
    definition = {
        'entityType': 'Opportunity',
        'rows': [{'path': 'account.industry'}],
        'columns': [{'path': 'closeDate', 'granularity': 'yearMonth'}],
        'measures': [{'key': 'won', 'aggregation': 'COUNT', 'condition': "stage == 'Closed Won'"}] + MEASURES,
    }
    result = run(definition)
    column = result['columns'][2]['k']
    expected = cell(result, ['Retail'], [column], 2)
    status, data, reason = call('GET', 'AdvancedCrosstab/action/drillDown', query={
        'payload': json.dumps({'definition': definition, 'rowPath': ['Retail'], 'columnPath': [column]}),
        'maxSize': 5, 'select': 'id,name,amount', 'orderBy': 'amount', 'order': 'desc'})
    check('drill-down total = cell count', status == 200 and data['total'] == expected, f"{status} {reason} {data and data['total']} vs {expected}")
    check('drill-down paging', status == 200 and len(data['list']) == min(5, expected))

    status, data, _ = call('GET', 'AdvancedCrosstab/action/drillDown', query={
        'payload': json.dumps({'definition': definition, 'rowPath': [''], 'columnPath': [], 'measure': 'won'})})
    expected = cell(result, [''], [], 0)
    check('drill-down with empty key and measure condition', status == 200 and data['total'] == expected,
          f"{data and data['total']} vs {expected}")


def test_saved_report_and_export():
    print('Saved reports, validation on save, export')
    definition = {'entityType': 'Opportunity', 'rows': [{'path': 'stage'}], 'columns': [{'path': 'leadSource'}],
                  'measures': MEASURES}
    status, entity, reason = call('POST', 'AdvancedCrosstab', {'name': 'Pipeline', 'definition': definition})
    check('create saved crosstab', status == 200 and entity['entityType'] == 'Opportunity', f"{status} {reason}")

    bad = dict(definition, measures=[{'key': 'x', 'kind': 'aggregate', 'formula': 'SUM(account.discount)'}])
    status, _, reason = call('POST', 'AdvancedCrosstab', {'name': 'Bad', 'definition': bad})
    check('invalid formula rejected on save', status == 400 and 'account.discount' in (reason or ''), f"{status} {reason}")

    status, result, _ = call('POST', f"AdvancedCrosstab/{entity['id']}/run", {})
    check('run saved crosstab by id', status == 200 and result['rows'])

    status, _, _ = call('POST', f"AdvancedCrosstab/{entity['id']}/run", {}, ALICE)
    check('saved crosstab of another user not readable (own-only role)', status == 403)

    for fmt in ['csv', 'xlsx', 'pdf']:
        status, data, reason = call('POST', f"AdvancedCrosstab/{entity['id']}/export", {'format': fmt, 'title': 'Pipeline'})
        ok = status == 200 and data.get('attachmentId')
        if ok:
            size = sql(f"SELECT size FROM attachment WHERE id = '{data['attachmentId']}'")[0][0]
            ok = int(size) > 100
        check(f'export {fmt}', ok, f"{status} {reason} {data}")


def test_rollup_consistency():
    print('In-memory roll-up = database aggregation')
    base = {'entityType': 'Opportunity', 'rows': [{'path': 'account.industry'}, {'path': 'stage'}],
            'columns': [{'path': 'closeDate', 'granularity': 'year'}, {'path': 'leadSource'}],
            'measures': [{'key': 'revenue', 'aggregation': 'SUM', 'expression': 'amount'}, {'key': 'n', 'aggregation': 'COUNT'},
                         {'key': 'lo', 'aggregation': 'MIN', 'expression': 'amount'},
                         {'key': 'hi', 'aggregation': 'MAX', 'expression': 'amount', 'condition': "stage == 'Closed Won'"}]}
    for auth in [ADMIN, ALICE]:
        rolled = run(base, auth)
        # An AVG measure is not decomposable: every level is then aggregated by the database.
        database = run(dict(base, measures=base['measures'] + [{'key': 'avg', 'aggregation': 'AVG', 'expression': 'amount'}]), auth)
        diffs = [(r, c) for r, cols in database['cells'].items() for c, vals in cols.items()
                 if rolled['cells'].get(r, {}).get(c) != vals[:4]]
        check(f'{auth[0]}: identical cells, 1 query instead of {database["queryCount"]}',
              not diffs and rolled['queryCount'] == 1, str(diffs[:3]))


def test_spreadsheet_syntax_and_list_filters():
    print('Spreadsheet-style formulas and list-view filters')

    def validate(formula, kind='record'):
        return call('POST', 'AdvancedCrosstab/action/validateFormula',
                    {'entityType': 'Opportunity', 'formula': formula, 'kind': kind})[1]

    r = validate("IF(AND([amount] > 1000, OR([stage] == 'Closed Won', [stage] == 'Closed Lost')), [amount], 0)")
    check('[field] syntax with IF / AND / OR', r['valid'], str(r))
    r = validate("CONTAINS([name], 'Opp') && NOT([amount] < 0)", 'condition')
    total = int(sql(f"SELECT COUNT(*) {OPP}")[0][0])
    check('CONTAINS and NOT', r['valid'] and r['preview']['count'] == total, str(r))
    r = validate('SUM([amount]) / COUNT([account.industry])', 'aggregate')
    expected = sql(f"SELECT SUM(o.amount) / COUNT(a.industry) {OPP}")[0][0]
    check('aggregate with [field] syntax', r['valid'] and close(r['preview']['value'], expected), str(r))
    r = validate('SUM(COUNT([account.industry]))', 'aggregate')
    expected = sql(f"SELECT COUNT(a.industry) {OPP}")[0][0]
    check('COUNT(field) as a non-empty indicator', r['valid'] and close(r['preview']['value'], expected), str(r))

    base = {'entityType': 'Opportunity', 'rows': [{'path': 'stage'}], 'measures': MEASURES}
    result = run(dict(base, listWhere=[{'type': 'in', 'attribute': 'leadSource', 'value': ['Web', 'Call']},
                                       {'type': 'greaterThan', 'attribute': 'amount', 'value': 100000}]))
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.lead_source IN ('Web', 'Call') AND o.amount > 100000")[0][0]
    check('list where items', close(cell(result, [], [], 1), expected))
    result = run(dict(base, listWhere=[{'type': 'primary', 'value': 'open'}]))
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.stage NOT IN ('Closed Won', 'Closed Lost')")[0][0]
    check('list preset filter', close(cell(result, [], [], 1), expected))
    result = run(dict(base, listWhere=[{'type': 'textFilter', 'value': 'Opp 1'}]))
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.name LIKE 'Opp 1%'")[0][0]
    check('list text search', close(cell(result, [], [], 1), expected))
    status, _, _ = call('POST', 'AdvancedCrosstab/action/run', {'definition': dict(base, listWhere=[{'type': 'weird'}])})
    check('malformed list filter rejected with 400', status == 400)
    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': dict(
        base, listWhere=[{'type': 'equals', 'attribute': 'probability', 'value': 5}])}, ALICE)
    check('forbidden field in list filters rejected', status == 403, f"{status} {reason}")


def test_related_measures():
    print('Related measures over one-to-many / many-to-many links (no double counting)')
    rel = lambda key, link, agg, expr=None, cond=None: {k: v for k, v in {
        'key': key, 'label': key, 'kind': 'related', 'link': link, 'aggregation': agg,
        'expression': expr, 'condition': cond}.items() if v is not None}
    result = run({
        'entityType': 'Account',
        'rows': [{'path': 'industry'}],
        'measures': [
            {'key': 'accounts', 'aggregation': 'COUNT'},
            rel('oppAmount', 'opportunities', 'SUM', 'amount'),
            rel('oppCount', 'opportunities', 'COUNT'),
            rel('wonAmount', 'opportunities', 'SUM', 'amount', "stage == 'Closed Won'"),
            rel('oppAvg', 'opportunities', 'AVG', 'amount'),
            rel('contacts', 'contacts', 'COUNT'),
            rel('meetings', 'meetings', 'COUNT'),
        ],
    })
    ACC = "FROM account a WHERE a.deleted = 0"
    check('data-source rows not duplicated', close(cell(result, [], [], 0), sql(f"SELECT COUNT(*) {ACC}")[0][0]))
    expected = sql("SELECT SUM(o.amount) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 WHERE o.deleted = 0")[0][0]
    check('one-to-many SUM', close(cell(result, [], [], 1), expected), f"{cell(result, [], [], 1)} vs {expected}")
    expected = sql("SELECT SUM(o.amount) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 "
                   "WHERE o.deleted = 0 AND a.industry = 'Retail'")[0][0]
    check('one-to-many SUM per row', close(cell(result, ['Retail'], [], 1), expected))
    expected = sql("SELECT COUNT(*) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 WHERE o.deleted = 0")[0][0]
    check('one-to-many COUNT', close(cell(result, [], [], 2), expected))
    expected = sql("SELECT SUM(o.amount) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 "
                   "WHERE o.deleted = 0 AND o.stage = 'Closed Won'")[0][0]
    check('related measure with condition', close(cell(result, [], [], 3), expected))
    expected = sql("SELECT AVG(o.amount) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 WHERE o.deleted = 0")[0][0]
    check('related AVG over all records', close(cell(result, [], [], 4), expected), f"{cell(result, [], [], 4)} vs {expected}")
    expected = sql("SELECT COUNT(*) FROM account_contact ac JOIN contact c ON c.id = ac.contact_id AND c.deleted = 0 "
                   "JOIN account a ON a.id = ac.account_id AND a.deleted = 0 WHERE ac.deleted = 0")[0][0]
    check('many-to-many COUNT', close(cell(result, [], [], 5), expected))
    expected = sql("SELECT COUNT(*) FROM meeting m JOIN account a ON a.id = m.parent_id AND a.deleted = 0 "
                   "WHERE m.deleted = 0 AND m.parent_type = 'Account'")[0][0]
    check('parent (hasChildren) COUNT', close(cell(result, [], [], 6), expected))

    alice = user_id('alice')
    result = run({'entityType': 'Account', 'rows': [], 'measures': [rel('oppCount', 'opportunities', 'COUNT')]}, ALICE)
    expected = sql(
        "SELECT COUNT(*) FROM opportunity o JOIN account a ON a.id = o.account_id AND a.deleted = 0 "
        "JOIN entity_team et ON et.entity_id = a.id AND et.entity_type = 'Account' AND et.deleted = 0 "
        "JOIN team t ON t.id = et.team_id AND t.name = 'North' "
        f"WHERE o.deleted = 0 AND o.assigned_user_id = '{alice}'")[0][0]
    check('related records restricted by ACL', close(cell(result, [], [], 0), expected), f"{cell(result, [], [], 0)} vs {expected}")

    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {'entityType': 'Account', 'rows': [],
        'measures': [rel('p', 'opportunities', 'AVG', 'probability')]}}, ALICE)
    check('forbidden field of related entity rejected', status == 400, f"{status} {reason}")


def test_custom_joins():
    print('Custom links to any entity on any field')
    join_by_id = {'name': 'acc2', 'localField': 'account', 'entityType': 'Account', 'foreignField': 'id'}
    result = run({'entityType': 'Opportunity', 'joins': [join_by_id], 'rows': [{'path': 'acc2.industry'}],
                  'measures': MEASURES})
    expected = sql(f"SELECT SUM(o.amount) {OPP} AND a.industry = 'Retail'")[0][0]
    check('link on id (like a relationship)', close(cell(result, ['Retail'], []), expected))

    # Campaign names are not unique ('Web' twice): first match only, rows never duplicated.
    join_by_name = {'name': 'camp', 'localField': 'leadSource', 'entityType': 'Campaign', 'foreignField': 'name'}
    result = run({'entityType': 'Opportunity', 'joins': [join_by_name], 'rows': [{'path': 'camp.type'}], 'measures': MEASURES})
    total = sql(f"SELECT COUNT(*) {OPP}")[0][0]
    check('link on non-unique field: no duplication', close(cell(result, [], [], 1), total))
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.lead_source = 'Web'")[0][0]
    check('link on non-unique field: first match (Web → cp1)', close(cell(result, ['Web'], [], 1), expected))

    result = run({'entityType': 'Opportunity', 'joins': [join_by_name], 'rows': [{'path': 'stage'}], 'measures': MEASURES,
                  'filter': {'type': 'condition', 'path': 'camp.type', 'operator': 'equals', 'value': 'Television'}})
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.lead_source = 'Call'")[0][0]
    check('filter through custom link', close(cell(result, [], [], 1), expected))

    reverse = {'name': 'opps', 'localField': 'name', 'entityType': 'Opportunity', 'foreignField': 'leadSource'}
    result = run({'entityType': 'Campaign', 'joins': [reverse], 'rows': [{'path': 'type'}],
                  'measures': [{'key': 'n', 'kind': 'related', 'link': 'opps', 'aggregation': 'COUNT'},
                               {'key': 'amount', 'kind': 'related', 'link': 'opps', 'aggregation': 'SUM', 'expression': 'amount'}]})
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.lead_source = 'Web'")[0][0]
    check('related measure through custom link', close(cell(result, ['Email'], [], 0), expected))
    expected = sql(f"SELECT COUNT(*) {OPP} AND o.lead_source IN ('Web', 'Call', 'Partner')")[0][0]
    expected_total = int(expected) + int(sql(f"SELECT COUNT(*) {OPP} AND o.lead_source = 'Web'")[0][0])
    check('related through custom link: each campaign counts its matches', close(cell(result, [], [], 0), expected_total))

    v = call('POST', 'AdvancedCrosstab/action/validateFormula', {'entityType': 'Opportunity', 'formula': "camp.type == 'Web'",
                                                                'kind': 'condition', 'joins': [join_by_name]})[1]
    check('formula validation knows custom links', v['valid'], str(v))

    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'joins': [dict(join_by_name, name='account')], 'rows': [], 'measures': MEASURES}})
    check('link name hiding a field rejected', status == 400, f"{status} {reason}")
    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'joins': [{'name': 'x', 'localField': 'leadSource', 'entityType': 'Contract',
                                                'foreignField': 'name'}], 'rows': [], 'measures': MEASURES}}, ALICE)
    check('link to an entity without access rejected', status in (400, 403), f"{status} {reason}")
    status, _, reason = call('POST', 'AdvancedCrosstab/action/run', {'definition': {
        'entityType': 'Opportunity', 'joins': [{'name': 'x', 'localField': 'leadSource', 'entityType': 'Opportunity',
                                                'foreignField': 'probability'}], 'rows': [{'path': 'x.name'}], 'measures': MEASURES}}, ALICE)
    check('link on a forbidden field rejected', status == 400, f"{status} {reason}")


def test_preview():
    print('ETL data preview per stage')
    definition = {'entityType': 'Opportunity', 'joins': [{'name': 'camp', 'localField': 'leadSource', 'entityType': 'Campaign',
                                                           'foreignField': 'name'}],
                  'rows': [{'path': 'account.industry'}, {'path': 'camp.type'}], 'measures': MEASURES,
                  'filter': {'type': 'condition', 'path': 'stage', 'operator': 'equals', 'value': 'Closed Won'}}
    status, source, reason = call('POST', 'AdvancedCrosstab/action/preview', {'definition': definition, 'stage': 'source', 'limit': 5})
    check('source stage count', status == 200 and source['count'] == int(sql(f"SELECT COUNT(*) {OPP}")[0][0]), f"{status} {reason}")
    status, filtered, _ = call('POST', 'AdvancedCrosstab/action/preview', {'definition': definition, 'stage': 'filtered', 'limit': 5})
    expected = int(sql(f"SELECT COUNT(*) {OPP} AND o.stage = 'Closed Won'")[0][0])
    check('filtered stage count', status == 200 and filtered['count'] == expected, f"{filtered and filtered['count']} vs {expected}")
    paths = [c.get('path') for c in filtered['columns']]
    check('preview columns include used fields', {'account.industry', 'camp.type', 'amount', 'stage'} <= set(paths), str(paths))
    check('preview rows limited', len(filtered['rows']) == 5)
    status, _, reason = call('POST', 'AdvancedCrosstab/action/preview', {'definition': definition, 'stage': 'source'}, ALICE)
    check('preview refuses a link to an entity without access', status == 400, f"{status} {reason}")
    own = {'entityType': 'Opportunity', 'rows': [{'path': 'stage'}], 'measures': MEASURES}
    status, alice, _ = call('POST', 'AdvancedCrosstab/action/preview', {'definition': own, 'stage': 'source'}, ALICE)
    expected = int(sql(f"SELECT COUNT(*) FROM opportunity WHERE deleted = 0 AND assigned_user_id = '{user_id('alice')}'")[0][0])
    check('preview respects ACL', status == 200 and alice['count'] == expected, f"{alice and alice['count']} vs {expected}")


if __name__ == '__main__':
    for test in [test_totals, test_ratio_correctness, test_display_and_conditional, test_multi_level_relations,
                 test_filters, test_acl, test_validation_and_injection, test_dates_compare_topn, test_drill_down,
                 test_saved_report_and_export, test_rollup_consistency,
                 test_spreadsheet_syntax_and_list_filters, test_related_measures, test_custom_joins,
                 test_preview]:
        try:
            test()
        except Exception as e:  # noqa
            print(f'  FAIL  {test.__name__}: {e}')
            failures.append(test.__name__)

    print(f'\n{len(failures)} failure(s)')
    sys.exit(1 if failures else 0)
