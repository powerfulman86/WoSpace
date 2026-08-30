# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class StockLocationCardReportWizard(models.TransientModel):
    _name = "stock.location.card.report.wizard"
    _description = "Stock Location Card Report Wizard"

    date_from = fields.Date(
        string="Start Date",
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="End Date",
        default=lambda self: fields.Date.context_today(self),
    )
    warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        relation="stock_loc_card_wiz_wh_rel",
        column1="wizard_id",
        column2="warehouse_id",
        string="Warehouses",
        help="Leave empty to include all warehouses.",
    )
    location_ids = fields.Many2many(
        comodel_name="stock.location",
        relation="stock_loc_card_wiz_loc_rel",
        column1="wizard_id",
        column2="location_id",
        string="Locations",
        domain=[("usage", "in", ["internal", "transit"])],
        help="Leave empty to include all internal warehouse locations. Select locations to include internal or transit locations.",
    )
    product_categ_ids = fields.Many2many(
        comodel_name="product.category",
        relation="stock_loc_card_wiz_categ_rel",
        column1="wizard_id",
        column2="category_id",
        string="Product Categories",
        help="Leave empty to include all product categories.",
    )
    product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="stock_loc_card_wiz_product_rel",
        column1="wizard_id",
        column2="product_id",
        string="Products",
        help="Leave empty to include all products.",
    )

    def _prepare_stock_location_card_report(self):
        self.ensure_one()
        return {
            "date_from": self.date_from,
            "date_to": self.date_to or fields.Date.context_today(self),
            "warehouse_ids": [(6, 0, self.warehouse_ids.ids)],
            "location_ids": [(6, 0, self.location_ids.ids)],
            "product_categ_ids": [(6, 0, self.product_categ_ids.ids)],
            "product_ids": [(6, 0, self.product_ids.ids)],
        }

    def button_export_html(self):
        self.ensure_one()
        action = self.env.ref("stock_card_report.action_report_stock_location_card_report_html")
        vals = action.sudo().read()[0]
        context = vals.get("context", {})
        if context:
            context = safe_eval(context)
        report = self.env["report.stock.location.card.report"].create(
            self._prepare_stock_location_card_report()
        )
        context["active_id"] = report.id
        context["active_ids"] = report.ids
        vals["context"] = context
        return vals

    def button_view_lines(self):
        self.ensure_one()
        report = self.env["report.stock.location.card.report"].create(
            self._prepare_stock_location_card_report()
        )
        return report.action_view_lines()

    def button_export_pdf(self):
        self.ensure_one()
        return self._export("qweb-pdf")

    def button_export_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/stock_card_report/location_export_xlsx/%s" % self.id,
            "target": "self",
        }

    def _export(self, report_type):
        report = self.env["report.stock.location.card.report"].create(
            self._prepare_stock_location_card_report()
        )
        return report.print_report(report_type)
