# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    contracting_validated = fields.Boolean(string="Contracting Validated", default=False)

    @api.model
    def _refresh_related_contract_statistics(self, analytic_account_ids):
        """Immediately refresh contracts affected by analytic activity."""
        if self.env.context.get('skip_contract_statistics_refresh'):
            return
        analytic_account_ids = list({account_id for account_id in analytic_account_ids if account_id})
        if not analytic_account_ids:
            return
        contracts = self.env['contracting.order'].sudo().search([
            ('account_analytic_id', 'in', analytic_account_ids),
        ])
        contracts._refresh_statistics_now()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._refresh_related_contract_statistics(lines.mapped('account_id').ids)
        return lines

    def write(self, vals):
        # Only accounting/timesheet values that can affect contract statistics
        # need a refresh; flags such as contracting_validated do not.
        relevant = {'account_id', 'amount', 'unit_amount', 'project_id', 'task_id'}
        old_account_ids = self.mapped('account_id').ids if relevant.intersection(vals) else []
        result = super().write(vals)
        if old_account_ids:
            self._refresh_related_contract_statistics(old_account_ids + self.mapped('account_id').ids)
        return result

    def unlink(self):
        analytic_account_ids = self.mapped('account_id').ids
        # Preserve the existing validation guard before deleting anything.
        for rec in self:
            if rec.contracting_validated:
                raise UserError(_('You can not delete Validated Transaction'))
        result = super().unlink()
        self._refresh_related_contract_statistics(analytic_account_ids)
        return result

    def action_validate_line(self):
        for rec in self:
            company = rec.company_id or rec.task_id.company_id or self.env.company
            journal_id = company.contracting_task_journal_id
            task_credit_account = company.contracting_task_credit_id
            if not journal_id:
                raise ValidationError(_("Please Define Task cost Journal In Contracting Settings for %s") % company.display_name)
            if not task_credit_account:
                raise ValidationError(_("Please Define Task Default Credit Account In Contracting Settings for %s") % company.display_name)
            contract_line = self.env['contracting.order.line'].search([('project_task_id', '=', rec.task_id.id), ('company_id', '=', company.id)], limit=1)
            task_cost = contract_line.price_unit * rec.unit_amount
            move_id = self.env['account.move'].with_company(company).create({
                'journal_id': journal_id.id, 'company_id': company.id, 'name': '/', 'move_type': 'entry',
                'ref': "Project " + self.project_id.name + "- Task " + rec.task_id.name,
                'line_ids': [(0, 0, {'name': "Project " + rec.project_id.name + "/ Task " + rec.task_id.name,
                    'account_id': contract_line.contract_id.template_id.product_id.property_account_expense_id.id,
                    'analytic_distribution': {str(rec.project_id.account_id.id): 100.0}, 'debit': task_cost}),
                    (0, 0, {'name': "Project " + rec.project_id.name + "/ Task " + rec.task_id.name,
                    'account_id': task_credit_account.id, 'credit': task_cost})],
            })
            move_id.action_post()
            rec.write({'contracting_validated': True})

