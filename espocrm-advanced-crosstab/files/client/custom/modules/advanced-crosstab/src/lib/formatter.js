define('advanced-crosstab:lib/formatter', [], function () {

    /**
     * Formats measure values with the user's number settings. Mirrors the server-side ValueFormatter.
     */
    class Formatter {

        /**
         * @param {import('view').default} view
         */
        constructor(view) {
            const numberUtil = view.getNumberUtil();

            this.thousandSeparator = numberUtil.getThousandSeparator();
            this.decimalMark = numberUtil.getDecimalMark();
            this.defaultCurrency = view.getConfig().get('defaultCurrency') || '';
        }

        number(value, decimals) {
            const negative = value < 0;
            const fixed = Math.abs(value).toFixed(decimals);
            const [integer, fraction] = fixed.split('.');
            const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, this.thousandSeparator);

            return (negative ? '-' : '') + grouped + (fraction ? this.decimalMark + fraction : '');
        }

        /**
         * @param {number|null} value
         * @param {{type: string, decimals: ?number, currency: ?string, prefix: string, suffix: string}} format
         * @param {'value'|'compare'} [variant]
         * @param {'percent'|'difference'} [compareMode]
         */
        format(value, format, variant = 'value', compareMode = 'percent') {
            if (value === null || value === undefined || value === '') {
                return '';
            }

            format = format || {};

            if (variant === 'compare') {
                if (compareMode === 'percent') {
                    return (value > 0 ? '+' : '') + this.number(value, 1) + ' %';
                }

                return (value > 0 ? '+' : '') + this.format(value, format);
            }

            const decimals = format.decimals;
            let text;

            switch (format.type) {
                case 'integer':
                    text = this.number(value, 0);
                    break;

                case 'decimal':
                    text = this.number(value, decimals ?? 2);
                    break;

                case 'percent':
                    text = this.number(value, decimals ?? 1) + ' %';
                    break;

                case 'currency':
                    text = this.number(value, decimals ?? 2) + ' ' + (format.currency || this.defaultCurrency);
                    break;

                case 'duration': {
                    const seconds = Math.round(Math.abs(value));
                    const minutes = Math.floor((seconds % 3600) / 60);

                    text = (value < 0 ? '-' : '') + Math.floor(seconds / 3600) + ':' + String(minutes).padStart(2, '0');
                    break;
                }

                default:
                    text = this.number(value, decimals ?? (Number.isInteger(value) ? 0 : 2));
            }

            return (format.prefix || '') + text.trim() + (format.suffix || '');
        }

        /**
         * Short form for charts and KPI cards: 1.25 M, 24.8 %, 1,245.
         */
        compact(value, format) {
            if (value === null || value === undefined) {
                return '—';
            }

            format = format || {};

            if (['percent', 'duration'].includes(format.type) || Math.abs(value) < 10000) {
                return this.format(value, format);
            }

            const units = [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']];

            for (const [size, unit] of units) {
                if (Math.abs(value) >= size) {
                    const currency = format.type === 'currency' ? ' ' + (format.currency || this.defaultCurrency) : '';

                    return (format.prefix || '') + this.number(value / size, 2) + ' ' + unit + currency + (format.suffix || '');
                }
            }

            return this.format(value, format);
        }
    }

    return Formatter;
});
