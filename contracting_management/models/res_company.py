# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    contracting_prepaid_product_id = fields.Many2one('product.product', string='Contracting Prepaid Product')
    contracting_retention_product_id = fields.Many2one('product.product', string='Contracting Retention Product')
    contracting_task_credit_id = fields.Many2one('account.account', string='Contracting Task Credit Account')
    contracting_task_journal_id = fields.Many2one('account.journal', string='Contracting Task Journal')
