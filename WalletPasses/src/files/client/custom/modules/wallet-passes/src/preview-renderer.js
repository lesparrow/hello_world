/**
 * Renders a Wallet-like HTML preview of a pass.
 * Input: normalized data returned by GET WalletPasses/pass/{id}/preview (or built from a template model).
 */
define('wallet-passes:preview-renderer', [], () => {

    const escape = value => Handlebars.Utils.escapeExpression(value == null ? '' : String(value));

    const sectionOrder = ['header', 'primary', 'secondary', 'auxiliary'];

    const renderField = field => {
        const align = field.textAlignment && field.textAlignment !== 'natural' ?
            ` style="text-align:${escape(field.textAlignment)}"` : '';

        return `<div class="wp-field"${align}>` +
            `<div class="wp-label">${escape(field.label)}</div>` +
            `<div class="wp-value">${escape(field.value)}</div>` +
            '</div>';
    };

    return {
        /**
         * @param {Object} data
         * @param {function(string): string} translate
         * @returns {string}
         */
        render(data, translate) {
            const fields = data.fields || [];
            const bySection = section => fields.filter(f => f.section === section);
            const images = data.images || {};

            const style = [
                `background-color:${escape(data.backgroundColor || '#1E3A5F')}`,
                `color:${escape(data.foregroundColor || '#FFFFFF')}`,
                `--wp-label-color:${escape(data.labelColor || data.foregroundColor || '#C8D3E0')}`,
            ].join(';');

            let html = `<div class="wallet-pass-preview wp-style-${escape(data.appleStyle || 'generic')}` +
                (data.status && data.status !== 'Active' ? ' wp-inactive' : '') + `" style="${style}">`;

            html += '<div class="wp-top">';
            html += images.logo ?
                `<img class="wp-logo" src="${escape(images.logo)}" alt="">` : '<span class="wp-logo-placeholder"></span>';
            html += `<span class="wp-logo-text">${escape(data.logoText || data.organizationName)}</span>`;
            html += `<div class="wp-header">${bySection('header').map(renderField).join('')}</div>`;
            html += '</div>';

            if (images.strip) {
                html += `<div class="wp-strip" style="background-image:url('${escape(images.strip)}')">` +
                    `<div class="wp-primary">${bySection('primary').map(renderField).join('')}</div></div>`;
            } else {
                html += '<div class="wp-primary-row">';
                html += `<div class="wp-primary">${bySection('primary').map(renderField).join('')}</div>`;

                if (images.thumbnail) {
                    html += `<img class="wp-thumbnail" src="${escape(images.thumbnail)}" alt="">`;
                }

                html += '</div>';
            }

            sectionOrder.slice(2).forEach(section => {
                const list = bySection(section);

                if (list.length) {
                    html += `<div class="wp-row wp-${section}">${list.map(renderField).join('')}</div>`;
                }
            });

            if (data.barcodeMessage) {
                html += '<div class="wp-barcode-box">' +
                    `<div class="wp-barcode" data-format="${escape(data.barcodeFormat)}"></div>` +
                    `<div class="wp-barcode-text">${escape(data.barcodeAltText || '')}</div>` +
                    '</div>';
            }

            if (data.status && data.status !== 'Active') {
                html += `<div class="wp-status-badge">${escape(translate(data.status))}</div>`;
            }

            html += '</div>';

            const back = bySection('back');

            if (back.length) {
                html += '<div class="wallet-pass-back">' + back.map(renderField).join('') + '</div>';
            }

            return html;
        },

        /**
         * Draws the barcode inside an already rendered preview (QR / Code 128 via EspoCRM bundled libs).
         *
         * @param {HTMLElement} container
         * @param {Object} data
         */
        drawBarcode(container, data) {
            const element = container.querySelector('.wp-barcode');

            if (!element || !data.barcodeMessage) {
                return;
            }

            element.innerHTML = '';

            if (data.barcodeFormat === 'QR' || !data.barcodeFormat) {
                Espo.loader.requirePromise('lib!qrcodejs').then(QRCode => {
                    new QRCode(element, {text: data.barcodeMessage, width: 110, height: 110});
                });

                return;
            }

            if (data.barcodeFormat === 'Code128') {
                Espo.loader.requirePromise('lib!jsbarcode').then(JsBarcode => {
                    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    element.appendChild(svg);

                    try {
                        JsBarcode(svg, data.barcodeMessage, {format: 'CODE128', height: 50, displayValue: false});
                    } catch (e) {
                        element.textContent = data.barcodeMessage;
                    }
                });

                return;
            }

            element.innerHTML = `<div class="wp-barcode-generic">${escape(data.barcodeFormat)}</div>`;
        },

        /**
         * Builds preview data from a WalletPassTemplate model with sample values.
         *
         * @param {import('model').default} model
         * @returns {Object}
         */
        fromTemplateModel(model) {
            const sample = {
                'pass.serialNumber': 'PREVIEW0001',
                'pass.holderName': 'Jane Doe',
                'pass.points': '120',
                'pass.expiresAt': '31/12/2026',
                'pass.issuedAt': '01/01/2026',
                'contact.firstName': 'Jane',
                'contact.lastName': 'Doe',
                'contact.name': 'Jane Doe',
                'account.name': 'ACME',
                'template.organizationName': model.get('organizationName') || '',
            };

            const render = value => String(value || '')
                .replace(/\{([A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*)\}/g, (m, key) =>
                    key in sample ? sample[key] : '‹' + key + '›');

            const imageUrl = field => model.get(field + 'Id') ?
                '?entryPoint=image&size=large&id=' + encodeURIComponent(model.get(field + 'Id')) : null;

            const fields = [];

            (model.get('frontFields') || []).forEach(f => fields.push({...f, value: render(f.value)}));
            (model.get('backFields') || []).forEach(f => fields.push({...f, section: 'back', value: render(f.value)}));

            const passType = model.get('passType') || 'generic';

            return {
                appleStyle: passType === 'loyaltyCard' ? 'storeCard' : passType,
                organizationName: model.get('organizationName'),
                logoText: render(model.get('logoText')),
                backgroundColor: model.get('backgroundColor'),
                foregroundColor: model.get('foregroundColor'),
                labelColor: model.get('labelColor'),
                barcodeFormat: model.get('barcodeFormat') || 'QR',
                barcodeMessage: render(model.get('barcodeMessage') || '{pass.serialNumber}'),
                barcodeAltText: render(model.get('barcodeAltText')),
                status: 'Active',
                fields: fields,
                images: {
                    logo: imageUrl('logo'),
                    strip: imageUrl('strip'),
                    thumbnail: imageUrl('thumbnail'),
                    background: imageUrl('background'),
                },
            };
        },
    };
});
