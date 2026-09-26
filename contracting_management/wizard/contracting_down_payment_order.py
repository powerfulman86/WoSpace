# -*- coding: utf-8 -*-

from datetime import date, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractingDownPaymentOrder(models.TransientModel):
    _name = 'contracting.down.payment.order'
    _description = 'Contracting Down Payment Order'

    internal_reference = fields.Char(string='Contact Reference', copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    contract_date = fields.Date(string='Contract Date', readonly=True)

    currency_id = fields.Many2one('res.currency', string='Currency')
    company_id = fields.Many2one('res.company', )

    contract_amount = fields.Monetary(string="Contract Amount", readonly=True)
    downpayment_amount = fields.Monetary(string="Down-Payment Amount", )

    @api.model
    def default_get(self, fields):
        res = super(ContractingDownPaymentOrder, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        sale_contract_id = self.env[active_model].browse(active_ids)

        res.update(
            {'internal_reference': sale_contract_id.internal_reference,
             'partner_id': sale_contract_id.partner_id.id,
             'contract_date': sale_contract_id.contract_date,
             'currency_id': sale_contract_id.currency_id.id,
             'company_id': sale_contract_id.company_id.id,
             'downpayment_amount': (sale_contract_id.contract_amount * (
                         sale_contract_id.advance_payment_rate / 100)) or 0.0,
             'contract_amount': sale_contract_id.contract_amount})

        return res

    def create_down_payment_order(self):
        self.ensure_one()
        downpayment_amount = self.downpayment_amount

        if downpayment_amount == 0:
            raise ValidationError(
                _("Down-Payment Amount Must Be Greater Than 0"))

        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        sale_contract_id = self.env[active_model].browse(active_ids)

        sale_contract_id.prepare_down_payment_order(downpayment_amount)

        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": sale_contract_id.down_payment_order.id,
        }
