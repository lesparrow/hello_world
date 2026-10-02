<?php

namespace Espo\Modules\AdvancedCrosstab\Classes\RecordHooks;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Record\Hook\SaveHook;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\DefinitionParser;
use Espo\Modules\AdvancedCrosstab\Engine\Query\QueryCompiler;
use Espo\ORM\Entity;

/**
 * A saved crosstab must be valid: structure, fields, relationships and formulas are compiled
 * (without running queries) for the saving user. Invalid formulas are never silently accepted.
 *
 * @implements SaveHook<Entity>
 */
class BeforeSaveValidation implements SaveHook
{
    public function __construct(
        private DefinitionParser $parser,
        private QueryCompiler $compiler,
    ) {}

    public function process(Entity $entity): void
    {
        if (!$entity->isNew() && !$entity->isAttributeChanged('definition')) {
            return;
        }

        $raw = $entity->get('definition');

        if ($raw === null) {
            throw new BadRequest("The crosstab definition is empty.");
        }

        $definition = $this->parser->parse($raw);

        $this->compiler->compile($definition);

        $entity->set('entityType', $definition->entityType);
    }
}
