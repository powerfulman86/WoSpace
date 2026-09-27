# Copyright 2015-2017 Akretion (http://www.akretion.com)
# @author Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import config, float_compare


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.constrains("product_id", "quantity")
    def check_negative_qty(self):
        # To provide an option to skip the check when necessary.
        # e.g. mrp_subcontracting_skip_no_negative - passes the context
        # for subcontracting receipts.
        if self.env.context.get("skip_negative_qty_check"):
            return

        p = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        check_negative_qty = (
            config["test_enable"] and self.env.context.get("test_stock_no_negative")
        ) or not config["test_enable"]
        if not check_negative_qty:
            return

        negative_lines = []

        for quant in self:
            disallowed_by_product = (
                not quant.product_id.allow_negative_stock
                and not quant.product_id.categ_id.allow_negative_stock
            )
            disallowed_by_location = not quant.location_id.allow_negative_stock

            if (
                float_compare(quant.quantity, 0, precision_digits=p) == -1
                and quant.product_id.is_storable
                and quant.location_id.usage in ("internal", "transit")
                and disallowed_by_product
                and disallowed_by_location
            ):
                lot_text = ""
                if quant.lot_id:
                    lot_text = _(" | Lot: %s") % quant.lot_id.display_name

                negative_lines.append(
                    _(
                        "- Product: %(product)s%(lot)s | Location: %(location)s | Available after validation: %(qty)s"
                    ) % {
                        "product": quant.product_id.display_name,
                        "lot": lot_text,
                        "location": quant.location_id.complete_name,
                        "qty": quant.quantity,
                    }
                )

        if negative_lines:
            raise ValidationError(
                _(
                    "You cannot validate this stock operation because the following products would become negative:\n\n%s"
                )
                % "\n".join(negative_lines)
            )
