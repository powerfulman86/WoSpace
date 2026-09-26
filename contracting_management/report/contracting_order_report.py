# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import SQL


class ContractingOrderReport(models.Model):
    _name = "contracting.order.report"
    _description = "Contracting Order Analysis Report"
    _auto = False
    _rec_name = 'contract_date'
    _order = 'contract_date desc'

    contract_id = fields.Many2one(comodel_name="contracting.order", string="Contract", required=False, )
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', string='Created By')
    team_id = fields.Many2one('crm.team', 'Sales Team', )
    currency_id = fields.Many2one('res.currency', string='Currency', )
    advisor_id = fields.Many2one('res.partner', string='Advisor')
    contractor_id = fields.Many2one('res.partner', string='Contractor')
    project_manager_id = fields.Many2one('res.users', string='Project Manager')
    project_engineer_id = fields.Many2one('hr.employee', string='Project Engineer')

    partner_id = fields.Many2one('res.partner', string='Customer', )
    account_analytic_id = fields.Many2one('account.analytic.account', )
    project_id = fields.Many2one('project.project', string='Project', )
    contract_date = fields.Date(string='Contract Date', )
    start_date = fields.Date(string='Create Date', )
    complete_date = fields.Date(string='Closed Date', )
    stage_id = fields.Many2one('contracting.order.stage', string='Stage', )

    template_id = fields.Many2one('contracting.order.template', string='Subscription Template', )
    contract_amount = fields.Monetary(string="Contract Amount", required=False, default=0.00)
    down_payment = fields.Monetary(string="Down Payment", default=0.00, )

    consumed_down_payment = fields.Monetary(string="Consumed Down Payment", default=0.00)
    remain_down_payment = fields.Monetary(string="Remain Down Payment", default=0.00)

    margin_expected = fields.Monetary(string="Expected Margin", default=0.00, )
    margin_expected_percentage = fields.Float(string="Expected Margin %", default=0.00)
    cost_expected = fields.Monetary(string="Expected Cost", default=0.00)
    margin_actual = fields.Monetary(string="Actual Margin", default=0.00)
    margin_actual_percentage = fields.Float(string="Actual Margin %", default=0.00)
    contract_progress = fields.Float("Overall Progress", )
    current_expense = fields.Monetary(string="Current Expense", default=0.00, )
    current_income = fields.Monetary(string="Current Income", default=0.00, )
    amount_to_invoice = fields.Monetary(string="To-Invoice Amount", default=0.00, )
    amount_to_invoice_expected = fields.Monetary(string="To-Invoice Amount Expected", default=0.00, )
    amount_invoiced = fields.Monetary(string='Invoiced Amount', default=0.00, )
    variation_amount = fields.Monetary(string="Variation Amount", default=0.00, )
    contract_total_amount = fields.Monetary(string="Total Amount", default=0.00, )
    health = fields.Selection([('normal', 'Neutral'),
                               ('done', 'Good'),
                               ('bad', 'Bad')], string="Health", )

    retention_amount = fields.Monetary(string='Retention To Be Amount', )
    retention_remain = fields.Monetary(string="Remain", )
    retention_balance = fields.Monetary(string='Balance', )

    def _with_contract(self):
        return ""

    def _select_contract(self):
        select_str = f"""
                    co.id as contract_id,
                    min(cl.id) as id,
                    co.company_id as company_id,
                    co.user_id as user_id,
                    co.team_id as team_id,
                    co.currency_id as currency_id,
                    co.advisor_id as advisor_id,
                    co.contractor_id as contractor_id,
                    co.project_manager_id as project_manager_id,
                    co.project_engineer_id as project_engineer_id,
                    co.partner_id as partner_id,
                    co.account_analytic_id as account_analytic_id,
                    co.project_id as project_id,
                    co.contract_date as contract_date,
                    co.stage_id as stage_id,
                    co.template_id as template_id,
                    co.contract_amount as contract_amount,
                    co.down_payment as down_payment,
                    co.consumed_down_payment as consumed_down_payment,
                    co.remain_down_payment as remain_down_payment,
                    co.margin_expected as margin_expected,
                    co.margin_expected_percentage as margin_expected_percentage,
                    co.current_expense as current_expense,
                    co.current_income as current_income,
                    co.amount_to_invoice as amount_to_invoice,
                    co.amount_to_invoice_expected as amount_to_invoice_expected,
                    co.amount_invoiced as amount_invoiced,
                    co.variation_amount as variation_amount,
                    co.contract_total_amount as contract_total_amount,
                    co.health as health,
                    co.retention_amount as retention_amount,
                    co.retention_remain as retention_remain,
                    co.retention_balance as retention_balance
                    
        """

        return select_str

    def _from_contract(self):
        return """
            contracting_order_line cl
            LEFT JOIN contracting_order co ON co.id=cl.contract_id
            JOIN res_partner partner ON co.partner_id = partner.id
            """

    def _group_by_contract(self):
        return """
            co.id,
            co.company_id,
            co.user_id,
            co.team_id,
            co.currency_id,
            co.advisor_id,
            co.contractor_id,
            co.project_manager_id,
            co.project_engineer_id,
            co.partner_id,
            co.account_analytic_id,
            co.project_id,
            co.contract_date,
            co.stage_id,
            co.template_id,
            co.variation_amount,
            co.contract_total_amount,
            co.health"""

    def _where_contract(self):
        return """
            cl.id IS not NULL"""

    def _query(self):
        return SQL(
            """
            SELECT %s
            FROM %s
            WHERE %s
            GROUP BY %s
            """,
            SQL(self._select_contract()),
            SQL(self._from_contract()),
            SQL(self._where_contract()),
            SQL(self._group_by_contract()),
        )

    @property
    def _table_query(self):
        return self._query()
