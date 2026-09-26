# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    contracting_prepaid_product_id = fields.Many2one(related='company_id.contracting_prepaid_product_id', readonly=False, string='Contracting Prepaid Product', domain="[('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    contracting_retention_product_id = fields.Many2one(related='company_id.contracting_retention_product_id', readonly=False, string='Contracting Retention Product', domain="[('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    account_task_credit_id = fields.Many2one(related='company_id.contracting_task_credit_id', readonly=False, string='Credit Account', domain="[('company_id', '=', company_id)]")
    task_journal_id = fields.Many2one(related='company_id.contracting_task_journal_id', readonly=False, string='Task Journal', domain="[('type', '=', 'general'), ('company_id', '=', company_id)]")
