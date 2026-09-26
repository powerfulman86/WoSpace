# Copyright 2013 Julius Network Solutions
# Copyright 2015 Clear Corp
# Copyright 2016 OpenSynergy Indonesia
# Copyright 2017 ForgeFlow S.L.
# Copyright 2018 Hibou Corp.
# Copyright 2023 Quartile Limited
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


def _distribution_from_account_id(account_id):
    return {str(account_id): 100.0} if account_id else False


def _single_100_percent_account_id(distribution):
    if not distribution or len(distribution) != 1:
        return False
    key, percentage = next(iter(distribution.items()))
    key = str(key)
    if not key.isdigit():
        return False
    try:
        percentage = float(percentage)
    except (TypeError, ValueError):
        return False
    return int(key) if percentage == 100.0 else False


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "analytic.mixin"]

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
    analytic_distribution = fields.Json(
        inverse="_inverse_analytic_distribution",
    )

    @api.depends("analytic_distribution")
    def _compute_analytic_account_id(self):
        """Expose a simple account selector for single-account distributions.

        Existing complex/multi-plan distributions are intentionally not reduced to
        a misleading single account; they remain untouched until the user explicitly
        selects an analytic account.
        """
        account_by_move = [
            (move, _single_100_percent_account_id(move.analytic_distribution))
            for move in self
        ]
        account_ids = {
            account_id for _move, account_id in account_by_move if account_id
        }
        existing_ids = set(
            self.env["account.analytic.account"].browse(list(account_ids)).exists().ids
        )
        for move, account_id in account_by_move:
            move.analytic_account_id = (
                account_id if account_id in existing_ids else False
            )

    def _inverse_analytic_account_id(self):
        for move in self:
            move.analytic_distribution = _distribution_from_account_id(
                move.analytic_account_id.id if move.analytic_account_id else False
            )

    def _inverse_analytic_distribution(self):
        """If analytic distribution is set on move, write it on all move lines"""
        for move in self:
            move.move_line_ids.write(
                {"analytic_distribution": move.analytic_distribution}
            )

    def _prepare_account_move_line(
        self, qty, cost, credit_account_id, debit_account_id, svl_id, description
    ):
        self.ensure_one()
        res = super()._prepare_account_move_line(
            qty, cost, credit_account_id, debit_account_id, svl_id, description
        )
        if not self.analytic_distribution:
            return res
        for line in res:
            if (
                line[2]["account_id"]
                != self.product_id.categ_id.property_stock_valuation_account_id.id
            ):
                # Add analytic account in debit line
                line[2].update({"analytic_distribution": self.analytic_distribution})
        return res

    def _prepare_procurement_values(self):
        """
        Allows to transmit analytic account from moves to new
        moves through procurement.
        """
        res = super()._prepare_procurement_values()
        if self.analytic_distribution:
            res.update(
                {
                    "analytic_distribution": self.analytic_distribution,
                }
            )
        return res

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """
        We fill in the analytic account when creating the move line from
        the move
        """
        res = super()._prepare_move_line_vals(
            quantity=quantity, reserved_quant=reserved_quant
        )
        if self.analytic_distribution:
            res.update({"analytic_distribution": self.analytic_distribution})
        return res

    def _need_validate_distribution(self):
        """Return moves are made outside the scope of the validation for now, since
        there could be cases where the necessity cannot be judged solely by the
        operation type.
        """
        self.ensure_one()
        if self._is_in() and self._is_returned(valued_type="in"):
            return False
        elif self._is_out() and self._is_returned(valued_type="out"):
            return False
        elif self.company_id.anglo_saxon_accounting and self._is_dropshipped_returned():
            return False
        return True

    def _action_done(self, cancel_backorder=False):
        for move in self:
            move.move_line_ids.analytic_distribution = move.analytic_distribution
            if not move._need_validate_distribution():
                continue
            move._validate_distribution(
                **{
                    "product": move.product_id.id,
                    "picking_type": move.picking_type_id.id,
                    "business_domain": "stock_move",
                    "company_id": move.company_id.id,
                }
            )
        return super()._action_done(cancel_backorder=cancel_backorder)


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "analytic.mixin"]

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
        account_by_line = [
            (
                move_line,
                _single_100_percent_account_id(move_line.analytic_distribution),
            )
            for move_line in self
        ]
        account_ids = {
            account_id for _move_line, account_id in account_by_line if account_id
        }
        existing_ids = set(
            self.env["account.analytic.account"].browse(list(account_ids)).exists().ids
        )
        for move_line, account_id in account_by_line:
            move_line.analytic_account_id = (
                account_id if account_id in existing_ids else False
            )

    def _inverse_analytic_account_id(self):
        for move_line in self:
            move_line.analytic_distribution = _distribution_from_account_id(
                move_line.analytic_account_id.id
                if move_line.analytic_account_id
                else False
            )

    @api.model
    def _prepare_stock_move_vals(self):
        """
        In the case move lines are created manually, we should fill in the
        new move created here with the analytic account if filled in.
        """
        res = super()._prepare_stock_move_vals()
        if self.analytic_distribution:
            res.update({"analytic_distribution": self.analytic_distribution})
        return res

    def write(self, vals):
        if "analytic_distribution" in vals:
            self.move_id.analytic_distribution = vals["analytic_distribution"]
        return super().write(vals)
