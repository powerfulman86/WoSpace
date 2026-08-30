from collections import OrderedDict

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_negative_stock_violations(self):
        """
        Collect all products in this picking that would become negative after
        validating this transfer.

        Important:
        - The check is based on physical current stock in the source location,
          not reserved/free quantity.
        - Reservations from other orders must not block this transfer if the
          physical stock is still enough for this transfer.
        - This allows the order that validates first to consume the available
          stock; later orders will be blocked when physical stock is no longer
          enough.
        - Transit source locations are checked the same way as internal
          locations, so transit stock cannot become negative.
        """
        self.ensure_one()

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        Quant = self.env['stock.quant']

        grouped = OrderedDict()

        move_lines = self.move_line_ids.filtered(
            lambda ml: ml.quantity and ml.product_id and ml.product_id.is_storable
        )

        for line in move_lines:
            source_location = line.location_id
            product = line.product_id
            lot = line.lot_id
            owner = line.owner_id
            package = line.package_id

            # Check both real internal stock locations and transit locations.
            # Transit locations are also physical controlled locations in this
            # implementation, so outgoing transfers from transit must not make
            # their stock negative unless negative stock is explicitly allowed.
            if source_location.usage not in ('internal', 'transit'):
                continue

            disallowed_by_product = (
                not product.allow_negative_stock
                and not product.categ_id.allow_negative_stock
            )
            disallowed_by_location = not source_location.allow_negative_stock

            if not (disallowed_by_product and disallowed_by_location):
                continue

            key = (
                product.id,
                source_location.id,
                lot.id or False,
                owner.id or False,
                package.id or False,
            )

            if key not in grouped:
                grouped[key] = {
                    'product': product.display_name,
                    'location': source_location.complete_name,
                    'lot': lot.display_name if lot else False,
                    'owner': owner.display_name if owner else False,
                    'package': package.display_name if package else False,
                    'on_hand_qty': 0.0,
                    'order_qty': 0.0,
                }

            line_qty = line.product_uom_id._compute_quantity(line.quantity, product.uom_id)
            grouped[key]['order_qty'] += line_qty

        for key, item in grouped.items():
            product_id, location_id, lot_id, owner_id, package_id = key
            quants = Quant.search([
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
                ('lot_id', '=', lot_id or False),
                ('owner_id', '=', owner_id or False),
                ('package_id', '=', package_id or False),
            ])
            item['on_hand_qty'] = sum(quants.mapped('quantity'))

        violations = []

        for item in grouped.values():
            remaining_qty = item['on_hand_qty'] - item['order_qty']
            not_available_qty = max(item['order_qty'] - item['on_hand_qty'], 0.0)

            # Only block when this transfer itself would make physical stock
            # negative. Do not use reserved_quantity here, because reservations
            # are priority/availability data, not actual stock consumption.
            if float_compare(remaining_qty, 0.0, precision_digits=precision) == -1:
                extra_parts = []
                if item['lot']:
                    extra_parts.append(_('Lot: %s') % item['lot'])
                if item['owner']:
                    extra_parts.append(_('Owner: %s') % item['owner'])
                if item['package']:
                    extra_parts.append(_('Package: %s') % item['package'])

                extra_text = ''
                if extra_parts:
                    extra_text = ' | ' + ' | '.join(extra_parts)

                violations.append(
                    _(
                        "- Product: %(product)s | Location: %(location)s%(extra)s | "
                        "Current Stock: %(current_stock)s | Order Quantity: %(order_qty)s | "
                        "Not Available Quantity: %(not_available_qty)s | Remaining: %(remaining)s"
                    ) % {
                        'product': item['product'],
                        'location': item['location'],
                        'extra': extra_text,
                        'current_stock': item['on_hand_qty'],
                        'order_qty': item['order_qty'],
                        'not_available_qty': not_available_qty,
                        'remaining': remaining_qty,
                    }
                )

        return violations

    def _check_negative_stock_before_validate(self):
        all_violations = []

        for picking in self:
            violations = picking._get_negative_stock_violations()
            if violations:
                picking_name = picking.name or _('New')
                all_violations.append(_('Transfer: %s') % picking_name)
                all_violations.extend(violations)
                all_violations.append('')

        if all_violations:
            raise ValidationError(
                _(
                    "You cannot validate this stock operation because the following products would become negative:\n\n%s"
                ) % '\n'.join(all_violations).rstrip()
            )

    def button_validate(self):
        # Show one aggregated popup for the whole transfer before Odoo starts
        # updating quants, so the user sees all products that are short in the
        # same order instead of only the first quant constraint error.
        self._check_negative_stock_before_validate()
        return super().button_validate()
