# Copyright (C) 2019 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models

from .stock_move import _distribution_from_account_id, _single_100_percent_account_id


class StockScrap(models.Model):
    _name = "stock.scrap"
    _inherit = ["stock.scrap", "analytic.mixin"]

    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        compute="_compute_analytic_account_id",
        inverse="_inverse_analytic_account_id",
        readonly=False,
        check_company=True,
        help="Selecting an analytic account automatically creates a 100% analytic "
        "distribution for the analytic plan assigned to that account.",
    )
    analytic_plan_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan",
        related="analytic_account_id.plan_id",
        readonly=True,
    )

    @api.depends("analytic_distribution")
    def _compute_analytic_account_id(self):
        account_by_scrap = [
            (scrap, _single_100_percent_account_id(scrap.analytic_distribution))
            for scrap in self
        ]
        account_ids = {
            account_id for _scrap, account_id in account_by_scrap if account_id
        }
        existing_ids = set(
            self.env["account.analytic.account"].browse(list(account_ids)).exists().ids
        )
        for scrap, account_id in account_by_scrap:
            scrap.analytic_account_id = (
                account_id if account_id in existing_ids else False
            )

    def _inverse_analytic_account_id(self):
        for scrap in self:
            scrap.analytic_distribution = _distribution_from_account_id(
                scrap.analytic_account_id.id if scrap.analytic_account_id else False
            )

    def _prepare_move_values(self):
        res = super()._prepare_move_values()
        res.update(
            {
                "analytic_distribution": self.analytic_distribution,
            }
        )
        return res

    def action_validate(self):
        self = self.with_context(validate_analytic=True)
        return super().action_validate()
