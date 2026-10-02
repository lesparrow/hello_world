<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Exception;

/**
 * Raised when a required setting (certificate, identifier, service account…) is missing or invalid.
 */
class ConfigurationException extends WalletException
{
}
