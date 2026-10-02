<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Formula;

use Espo\Core\Exceptions\BadRequest;

class FormulaError extends BadRequest
{
    public static function create(string $message): self
    {
        return new self($message);
    }
}
