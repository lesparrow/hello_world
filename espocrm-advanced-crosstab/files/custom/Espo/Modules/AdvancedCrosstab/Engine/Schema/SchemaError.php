<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\Core\Exceptions\BadRequest;

class SchemaError extends BadRequest
{
    public static function invalidField(string $path): self
    {
        return new self("Invalid field: {$path}");
    }
}
