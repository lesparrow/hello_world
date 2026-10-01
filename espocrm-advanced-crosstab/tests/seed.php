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
    $u->set('password', password_hash('pass123', PASSWORD_BCRYPT));
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
echo "seeded\n";
