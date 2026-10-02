<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

use Espo\Core\Exceptions\BadRequest;

class DefinitionError extends BadRequest
{
    public static function create(string $message): self
    {
        return new self($message);
    }
}
