# Copyright 2026 Ecosoft Co., Ltd. (<http://ecosoft.co.th>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    analytic_distribution = fields.Json(related="stock_move_id.analytic_distribution")
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        related="stock_move_id.analytic_account_id",
    )
    analytic_plan_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan",
        related="stock_move_id.analytic_plan_id",
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
