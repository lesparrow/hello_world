<?php
require 'bootstrap.php';
use Espo\ORM\EntityManager;
$app = new \Espo\Core\Application();
$app->setupSystemUser();
$c = $app->getContainer();
$em = $c->getByClass(EntityManager::class);
mt_srand(42);

// Role: Opportunity own only, Account team only.
$role = $em->createEntity('Role', [
    'name' => 'Sales Rep',
    'data' => (object) [
        'Opportunity' => (object) ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no', 'stream' => 'own'],
        'Account' => (object) ['create' => 'no', 'read' => 'team', 'edit' => 'no', 'delete' => 'no', 'stream' => 'no'],
        'AdvancedCrosstab' => (object) ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'own'],
    ],
    'fieldData' => (object) [
        'Opportunity' => (object) ['probability' => (object) ['read' => 'no', 'edit' => 'no']],
    ],
]);
$team = $em->createEntity('Team', ['name' => 'North']);
$users = [];
foreach (['alice', 'bob'] as $name) {
    $u = $em->createEntity('User', ['userName' => $name, 'lastName' => ucfirst($name), 'type' => 'regular', 'isActive' => true,
        'rolesIds' => [$role->getId()], 'teamsIds' => [$team->getId()], 'defaultTeamId' => $team->getId()]);
    // Espo's own hashing (the algorithm differs between EspoCRM versions).
    $u->set('password', $c->getByClass(\Espo\Core\InjectableFactory::class)->create(\Espo\Core\Utils\PasswordHash::class)->hash('pass123'));
    $em->saveEntity($u);
    $users[$name] = $u;
}
$parents = [];
foreach (['Holding North' => 'Finance', 'Holding South' => 'Insurance'] as $n => $ind) {
    $parents[] = $em->createEntity('Account', ['name' => $n, 'industry' => $ind, 'billingAddressCountry' => 'Morocco']);
}
$accounts = [];
$defs = [
    ['Rabat Retail', 'Retail', 'Morocco', 0, true], ['Kenitra Foods', 'Food', 'Morocco', 0, true],
    ['Casa Steel', 'Manufacturing', 'Morocco', 1, false], ['Paris Mode', 'Retail', 'France', 1, false],
    ['Lyon Tech', 'Electronics', 'France', null, true], ['Madrid Bank', 'Finance', 'Spain', null, false],
];
foreach ($defs as [$n, $ind, $country, $p, $teamed]) {
    $accounts[] = $em->createEntity('Account', ['name' => $n, 'industry' => $ind, 'billingAddressCountry' => $country,
        'parentId' => $p === null ? null : $parents[$p]->getId(), 'teamsIds' => $teamed ? [$team->getId()] : []]);
}
$stages = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'];
for ($i = 0; $i < 300; $i++) {
    $acc = $i % 17 === 0 ? null : $accounts[mt_rand(0, 5)];
    $user = mt_rand(0, 1) ? $users['alice'] : $users['bob'];
    $date = sprintf('%d-%02d-%02d', mt_rand(2025, 2026), mt_rand(1, 12), mt_rand(1, 28));
    $em->createEntity('Opportunity', [
        'name' => "Opp $i", 'amount' => mt_rand(10, 2000) * 100, 'amountCurrency' => 'MAD',
        'stage' => $stages[mt_rand(0, 5)], 'closeDate' => $date, 'probability' => mt_rand(0, 100),
        'accountId' => $acc?->getId(), 'assignedUserId' => $user->getId(), 'leadSource' => ['Web', 'Call', 'Partner', ''][mt_rand(0, 3)],
    ]);
}
// Contacts (many-to-many with accounts) and meetings (children of accounts), for related measures and selectors.
$contacts = [];
foreach (['Alaoui', 'Bennani', 'Chraibi', 'Dupont', 'Garcia', 'Idrissi'] as $i => $lastName) {
    $contacts[] = $em->createEntity('Contact', [
        'firstName' => 'C' . $i, 'lastName' => $lastName,
        'accountsIds' => [$accounts[$i % 6]->getId(), $accounts[($i + 2) % 6]->getId()],
    ]);
}
$statuses = ['Planned', 'Held', 'Not Held'];
for ($i = 0; $i < 12; $i++) {
    $start = sprintf('%d-%02d-%02d %02d:00:00', 2026, mt_rand(1, 12), mt_rand(1, 28), mt_rand(8, 17));
    $em->createEntity('Meeting', [
        'name' => "Meeting $i", 'status' => $statuses[mt_rand(0, 2)], 'dateStart' => $start,
        'dateEnd' => date('Y-m-d H:i:s', strtotime($start) + 3600),
        'parentType' => 'Account', 'parentId' => $accounts[mt_rand(0, 5)]->getId(),
        'assignedUserId' => $users['alice']->getId(),
    ]);
}
// Campaigns with a non-unique name ('Web' twice), for custom links on non-unique fields.
foreach ([['cp1', 'Web', 'Web'], ['cp2', 'Web', 'Email'], ['cp3', 'Call', 'Television'], ['cp4', 'Partner', 'Mail']] as [$id, $n, $type]) {
    $em->createEntity('Campaign', ['id' => $id, 'name' => $n, 'type' => $type, 'status' => 'Active']);
}
echo "seeded\n";
