# -*- coding: utf-8 -*-


from odoo import tools
from odoo import api, fields, models


class SubcontractingReport(models.Model):
    _name = "subcontracting.report"
    _description = "Sub-Contracting Analysis Report"
    _auto = False
    _rec_name = 'contract_date'
    _order = 'contract_date desc'

    sub_contract_id = fields.Many2one(comodel_name="contracting.order.sub", string="Contract", required=False, )
    company_id = fields.Many2one('res.company', )
    user_id = fields.Many2one('res.users', )
    team_id = fields.Many2one('crm.team', 'Sales Team', )
    currency_id = fields.Many2one('res.currency', )
    partner_id = fields.Many2one('res.partner', string='Vendor', )
    contract_date = fields.Date(string='Contract Date', )
    start_date = fields.Date(string='Create Date', )
    complete_date = fields.Date(string='Closed Date', )
    sale_contract_id = fields.Many2one('contracting.order', string='Original Contract', )
    contract_amount = fields.Monetary(string="Contract Amount", )
    contract_amount_remain = fields.Monetary(string="Remain Amount", )
    contract_actual_amount = fields.Monetary(string="Actual Amount", )
    amount_invoiced = fields.Monetary('Amount Billed', )
    amount_un_invoiced = fields.Monetary('UnBilled Amount', )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('progress', 'In Progress'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', )

    invoice_status = fields.Selection([('no', 'Nothing to Bill'),
                                       ('to_invoice', 'Waiting Bills'),
                                       ('invoiced', 'Fully Billed'),
                                       ], string='Billing Status', )

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            sco.id as sub_contract_id,
            min(sco.id) as id,
            sco.company_id as company_id,
            sco.user_id as user_id,
            sco.team_id as team_id,
            sco.currency_id as currency_id,
            sco.partner_id as partner_id,
            sco.contract_date as contract_date,
            sco.start_date as start_date,
            sco.complete_date as complete_date,
            sco.sale_contract_id as sale_contract_id,
            sco.contract_amount as contract_amount,
            sco.contract_amount_remain as contract_amount_remain,
            sco.contract_actual_amount as contract_actual_amount,
            sco.amount_invoiced as amount_invoiced,
            sco.amount_un_invoiced as amount_un_invoiced,
            sco.state as state,
            sco.invoice_status as invoice_status
        """

        for field in fields.values():
            select_ += field

        from_ = """
            contracting_order_sub sco
            JOIN res_partner partner ON sco.partner_id = partner.id
        %s
        """ % from_clause

        groupby_ = """
            sco.id,
            sco.company_id,
            sco.user_id,
            sco.team_id,
            sco.currency_id,
            sco.partner_id,
            sco.contract_date,
            sco.start_date,
            sco.complete_date,
            sco.sale_contract_id,
            sco.contract_amount,
            sco.contract_actual_amount,
            sco.amount_invoiced,
            sco.state,
            sco.invoice_status
        %s
        """ % (groupby)

        return '%s (SELECT %s FROM %s WHERE sco.id IS NOT NULL GROUP BY %s)' % (with_, select_, from_, groupby_)

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
