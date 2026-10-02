<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Pivot;

use Espo\Core\Utils\Language;
use Espo\Modules\AdvancedCrosstab\Engine\Query\CompiledDimension;
use Espo\ORM\EntityManager;

/**
 * Produces display labels for dimension keys, server-side, so that the UI, charts and exports agree.
 */
class LabelResolver
{
    public function __construct(
        private Language $language,
        private EntityManager $entityManager,
    ) {}

    /**
     * @param string[] $keys
     * @return array<string, string>
     */
    public function resolve(CompiledDimension $dimension, array $keys): array
    {
        $labels = [];
        $field = $dimension->field;

        $linkNames = $field && $field->foreignEntityType ?
            $this->fetchNames($field->foreignEntityType, $keys) :
            [];

        foreach ($keys as $key) {
            $key = (string) $key;

            if ($key === '') {
                $labels[$key] = $this->language->translateLabel('(empty)', 'labels', 'AdvancedCrosstab');

                continue;
            }

            $labels[$key] = $this->label($dimension, $key, $linkNames);
        }

        return $labels;
    }

    /**
     * @param array<string, string> $linkNames
     */
    private function label(CompiledDimension $dimension, string $key, array $linkNames): string
    {
        $field = $dimension->field;

        if (!$field) {
            return $key;
        }

        if ($field->foreignEntityType) {
            return $linkNames[$key] ?? $key;
        }

        if ($field->fieldType === 'enum') {
            $label = $this->language->translateOption($key, $field->field, $field->entityType);

            return is_string($label) && $label !== '' ? $label : $key;
        }

        if ($field->fieldType === 'bool') {
            return $this->language->translateLabel($key === '1' ? 'Yes' : 'No');
        }

        return match ($dimension->granularity) {
            'quarter' => $this->quarter($key),
            'quarterNumber' => 'Q' . $key,
            'yearMonth' => $this->yearMonth($key),
            'month' => $this->monthName((int) $key),
            'week' => $this->week($key),
            'dayOfWeek' => $this->dayName((int) $key),
            default => $key,
        };
    }

    private function quarter(string $key): string
    {
        $parts = explode('_', $key);

        return count($parts) === 2 ? "Q{$parts[1]} {$parts[0]}" : $key;
    }

    private function yearMonth(string $key): string
    {
        $parts = explode('-', $key);

        return count($parts) === 2 ? $this->monthName((int) $parts[1], true) . ' ' . $parts[0] : $key;
    }

    private function week(string $key): string
    {
        $parts = explode('/', $key);

        return count($parts) === 2 ? "W{$parts[1]} {$parts[0]}" : $key;
    }

    private function monthName(int $month, bool $short = false): string
    {
        $list = $this->language->get(['Global', 'lists', $short ? 'monthNamesShort' : 'monthNames']);

        return is_array($list) && isset($list[$month - 1]) ? (string) $list[$month - 1] : (string) $month;
    }

    /**
     * DAYOFWEEK_NUMBER: 0 = Sunday … 6 = Saturday.
     */
    private function dayName(int $day): string
    {
        $list = $this->language->get(['Global', 'lists', 'dayNames']);

        return is_array($list) && isset($list[$day]) ? (string) $list[$day] : (string) $day;
    }

    /**
     * Names of linked records in one query. Record names are shown the same way EspoCRM shows
     * link names in list views.
     *
     * @param string[] $ids
     * @return array<string, string>
     */
    private function fetchNames(string $entityType, array $ids): array
    {
        $ids = array_values(array_filter(array_map('strval', $ids), fn ($id) => $id !== ''));

        if ($ids === []) {
            return [];
        }

        $defs = $this->entityManager->getDefs()->getEntity($entityType);

        if (!$defs->hasAttribute('name')) {
            return [];
        }

        $names = [];

        foreach (array_chunk($ids, 1000) as $chunk) {
            $collection = $this->entityManager
                ->getRDBRepository($entityType)
                ->select(['id', 'name'])
                ->where(['id' => $chunk])
                ->find();

            foreach ($collection as $entity) {
                $names[$entity->getId()] = (string) $entity->get('name');
            }
        }

        return $names;
    }
}
