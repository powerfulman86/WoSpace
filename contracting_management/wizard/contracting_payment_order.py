# -*- coding: utf-8 -*-

from datetime import date, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractingPaymentOrder(models.TransientModel):
    _name = 'contracting.payment.order'
    _description = 'Contracting Payment Order'

    internal_reference = fields.Char(string='Contact Reference', copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    contract_date = fields.Date(string='Contract Date', readonly=True)

    currency_id = fields.Many2one('res.currency', string='Currency')
    company_id = fields.Many2one('res.company', )

    contract_amount = fields.Monetary(string="Contract Amount", readonly=True)
    amount_to_invoice = fields.Monetary(string="To-Invoice Amount", readonly=True)
    amount_to_invoice_expected = fields.Monetary(string="To-Invoice Amount Expected", readonly=True)
    payment_amount = fields.Monetary(string="Payment Amount", )

    @api.model
    def default_get(self, fields):
        res = super(ContractingPaymentOrder, self).default_get(fields)
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
             'contract_amount': sale_contract_id.contract_amount,
             'amount_to_invoice': sale_contract_id.amount_to_invoice,
             'amount_to_invoice_expected': sale_contract_id.amount_to_invoice_expected,
             'payment_amount': sale_contract_id.amount_to_invoice_expected, })

        return res

    def create_payment_order(self):
        self.ensure_one()
        payment_amount = self.payment_amount

        if payment_amount == 0:
            raise ValidationError(_("Payment Amount Must Be Greater Than 0"))

        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        sale_contract_id = self.env[active_model].browse(active_ids)

        order = sale_contract_id.prepare_contract_payment_order(payment_amount)

        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": order,
        }
