# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import date_utils
from odoo.tools.safe_eval import safe_eval


class StockCardReportWizard(models.TransientModel):
    _name = "stock.card.report.wizard"
    _description = "Stock Card Report Wizard"

    date_from = fields.Date(
        string="Start Date",
        default=lambda self: fields.Date.context_today(self).replace(day=1)
    )
    date_to = fields.Date(
        string="End Date",
        default=lambda self: fields.Date.context_today(self),
    )
    warehouse_id = fields.Many2one(comodel_name="stock.warehouse", string="Warehouse")
    product_categ_ids = fields.Many2many(
        comodel_name="product.category",
        string="Product Categories",
    )
    product_ids = fields.Many2many(comodel_name="product.product", string="Products")

    def button_export_html(self):
        self.ensure_one()
        action = self.env.ref("stock_card_report.action_report_stock_card_report_html")
        vals = action.sudo().read()[0]
        context = vals.get("context", {})
        if context:
            context = safe_eval(context)
        model = self.env["report.stock.card.report"]
        report = model.create(self._prepare_stock_card_report())
        context["active_id"] = report.id
        context["active_ids"] = report.ids
        vals["context"] = context
        return vals

    def button_view_lines(self):
        self.ensure_one()
        report = self.env["report.stock.card.report"].create(self._prepare_stock_card_report())
        return report.action_view_lines()

    def button_export_pdf(self):
        self.ensure_one()
        report_type = "qweb-pdf"
        return self._export(report_type)

    def button_export_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/stock_card_report/export_xlsx/%s" % self.id,
            "target": "self",
        }

    def _prepare_stock_card_report(self):
        self.ensure_one()
        return {
            "date_from": self.date_from,
            "date_to": self.date_to or fields.Date.context_today(self),
            "product_categ_ids": [(6, 0, self.product_categ_ids.ids)],
            "product_ids": [(6, 0, self.product_ids.ids)],
            # Keep report engine based on stock.location.
            # Wizard shows warehouses only; selected warehouse maps to its main stock location.
            "location_id": self.warehouse_id.lot_stock_id.id if self.warehouse_id else False,
        }

    def _export(self, report_type):
        model = self.env["report.stock.card.report"]
        report = model.create(self._prepare_stock_card_report())
        return report.print_report(report_type)
