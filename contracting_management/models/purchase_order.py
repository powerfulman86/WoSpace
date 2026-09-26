# -*- coding: utf-8 -*-

from odoo import models, fields, api


def _distribution_account_ids(distribution):
    account_ids = set()
    for key in (distribution or {}):
        for part in str(key).split(','):
            if part.isdigit():
                account_ids.add(int(part))
    return account_ids


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    task_id = fields.Many2one('project.task', string='Task Id')

    def _refresh_contract_statistics_from_orders(self):
        if self.env.context.get('skip_contract_statistics_refresh') or not self:
            return
        self.order_line._refresh_related_contract_statistics()

    def write(self, vals):
        should_refresh = 'state' in vals
        result = super().write(vals)
        if should_refresh:
            self._refresh_contract_statistics_from_orders()
        return result


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    subcontract_line_id = fields.Many2one(
        'contracting.order.sub.task', 'subcontract Line', ondelete='set null', index=True
    )

    def _related_contracts(self):
        contracts = self.env['contracting.order']
        analytic_ids = set()
        for line in self:
            analytic_ids.update(_distribution_account_ids(line.analytic_distribution))
        if analytic_ids:
            contracts |= contracts.sudo().search([('account_analytic_id', 'in', list(analytic_ids))])
        contracts |= self.mapped('subcontract_line_id.sub_contract_id.sale_contract_id')
        return contracts

    def _refresh_related_contract_statistics(self, extra_contracts=None):
        if self.env.context.get('skip_contract_statistics_refresh'):
            return
        contracts = self._related_contracts()
        if extra_contracts:
            contracts |= extra_contracts
        contracts._refresh_statistics_now()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._refresh_related_contract_statistics()
        return lines

    def write(self, vals):
        relevant = {
            'analytic_distribution', 'product_id', 'product_qty', 'qty_invoiced',
            'price_unit', 'order_id', 'subcontract_line_id',
        }
        old_contracts = self._related_contracts() if relevant.intersection(vals) else self.env['contracting.order']
        result = super().write(vals)
        if relevant.intersection(vals):
            self._refresh_related_contract_statistics(old_contracts)
        return result

    def unlink(self):
        contracts = self._related_contracts()
        result = super().unlink()
        contracts._refresh_statistics_now()
        return result
