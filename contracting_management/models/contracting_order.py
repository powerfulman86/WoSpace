# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError


class ContractingOrder(models.Model):
    _name = 'contracting.order'
    _description = 'Contracting Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'internal_reference'
    _order = 'contract_date desc, id desc'
    _check_company_auto = True

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    internal_reference = fields.Char(string='Contact Reference', copy=False, readonly=True, index=True,
                                     default=lambda self: _('New'))
    contract_reference = fields.Char(string="Reference", required=False, )
    name = fields.Char(string="Title", required=False, )

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string='Created By')
    team_id = fields.Many2one('crm.team', 'Sales Team', change_default=True, default=_get_default_team,
                              check_company=True,
                              domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    description = fields.Text(string='Description', )
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(comodel_name='res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True,
                                 domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]")
    advisor_id = fields.Many2one('res.partner', string='Advisor', required=True,
                                 domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]")
    contractor_id = fields.Many2one('res.partner', string='Contractor', required=True,
                                    domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]")
    project_manager_id = fields.Many2one('res.users', string='Project Manager')
    project_engineer_id = fields.Many2one('hr.employee', string='Project Engineer', check_company=True, domain="[('company_id', '=', company_id)]")

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', copy=False, readonly=True, check_company=True, index=True)
    project_id = fields.Many2one('project.project', string='Project', copy=False, readonly=True, check_company=True, index=True)
    contract_date = fields.Date(string='Contract Date', )
    start_date = fields.Date(string='Create Date', readonly=True, default=fields.Date.today(), )
    complete_date = fields.Date(string='Closed Date', readonly=True, )

    stage_id = fields.Many2one('contracting.order.stage', string='Stage', index=True, domain="[('company_id', '=', company_id)]", check_company=True,
                               default=lambda s: s._get_default_stage_id(),
                               copy=False, group_expand='_read_group_stage_ids', tracking=True)
    stage_sequence = fields.Integer(related="stage_id.sequence")
    kanban_state = fields.Selection([('normal', 'Grey'),
                                     ('done', 'Green'),
                                     ('blocked', 'Red')
                                     ], string='Kanban State', default='normal', tracking=True, copy=False)

    template_id = fields.Many2one('contracting.order.template', string='Subscription Template',
                                  domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                  required=True,
                                  tracking=True, check_company=True)

    starred_user_ids = fields.Many2many('res.users', 'contracting_order_starred_user_rel', 'contracting_order_id',
                                        'user_id',
                                        default=lambda s: s._get_default_starred_user_ids(),
                                        string='Members')
    starred = fields.Boolean(compute='_compute_starred', inverse='_inverse_starred',
                             string='Show Subscription on dashboard',
                             help="Whether this subscription should be displayed on the dashboard or not")

    contract_amount = fields.Monetary(string="Contract Amount", required=False, default=0.00, tracking=True, )

    # contract down payment
    @api.depends('consumed_down_payment')
    def _compute_down_payment(self):
        for rec in self:
            rec.remain_down_payment = rec.down_payment - rec.consumed_down_payment

    advance_payment_rate = fields.Integer(string="Advance Payment %", required=False)
    down_payment_order = fields.Many2one("sale.order", string="Down Payment Order", readonly=True, tracking=True,
                                         copy=False, )
    down_payment = fields.Monetary(string="Down Payment", related='down_payment_order.amount_total', required=False,
                                   store=True)
    consumed_down_payment = fields.Monetary(string="Consumed Down Payment", required=False, default=0.00, readonly=True)
    remain_down_payment = fields.Monetary(string="Remain Down Payment", compute='_compute_down_payment', required=False,
                                          default=0.00, readonly=True, store=True, help='Remaining down payment: Down Payment minus Consumed Down Payment.')

    # contract retention
    retention_rate = fields.Integer(string="Retention %", required=False, default=0)
    retention_amount = fields.Monetary(string='To Be Amount', readonly=True, store=True,
                                       compute='_compute_retention_amount',
                                       default=0.0, help='Retention amount: Contract Amount multiplied by Retention Percentage.')
    retention_remain = fields.Monetary(string="Remain", compute='_compute_retention_remain', required=False,
                                       default=0.00, readonly=True, store=True, help='Remaining retention: Retention Amount minus Retention Balance.')
    retention_balance = fields.Monetary(string='Balance', readonly=True, store=True,
                                        compute='_compute_retention_amount',
                                        default=0.0, help='Retention balance used by the retention calculation to determine the remaining retention.')

    @api.depends('retention_rate', 'contract_amount')
    def _compute_retention_amount(self):
        for rec in self:
            if rec.retention_rate and rec.contract_amount:
                rec.retention_amount = rec.retention_rate * (rec.contract_amount / 100)

    @api.depends('retention_amount', 'retention_balance')
    def _compute_retention_remain(self):
        for rec in self:
            if rec.retention_amount and rec.retention_balance:
                rec.retention_remain = rec.retention_amount - rec.retention_balance

    # contract margins
    margin_expected = fields.Monetary(string="Expected Margin", compute='_compute_expected', default=0.00, store=True, help='Expected margin: Contract Total Amount minus Expected Cost.')
    margin_expected_percentage = fields.Float(string="Expected Margin %", compute='_compute_expected', default=0.00,
                                              store=True, help='Expected margin percentage: (Contract Total Amount minus Expected Cost) divided by Contract Total Amount, multiplied by 100.')
    cost_expected = fields.Monetary(string="Expected Cost", compute='_compute_margins', default=0.00, store=True, help='Expected cost: Labour Estimated Cost plus Material Estimated Cost plus Subcontract Estimated Cost plus Overhead Estimated Cost.')
    margin_actual = fields.Monetary(string="Actual Margin", compute='_compute_margins', default=0.00, store=True, help='Actual margin: Current Income minus Current Expense when both values are available.')
    margin_actual_percentage = fields.Float(string="Actual Margin %", compute='_compute_margins', default=0.00,
                                            store=True, help='Actual margin percentage: Actual Margin divided by Contract Total Amount, multiplied by 100 when the margin is positive.')
    contract_progress = fields.Float("Overall Progress", compute='_compute_totals', store=True,  help='Overall progress: average of Labour, Material, Subcontract and Overhead progress percentages.')
    current_expense = fields.Monetary(string="Current Expense", store=True,
                                      related='account_analytic_id.debit')
    current_income = fields.Monetary(string="Current Income", store=True,
                                     related='account_analytic_id.credit')
    current_income_percentage = fields.Float(string="Current Income Percentage", default=0.00, store=True,
                                             compute='_compute_income_rate', help='Current income percentage: Current Income divided by Contract Total Amount, multiplied by 100.')
    amount_to_invoice = fields.Monetary(string="To-Invoice Amount", compute='_compute_totals', default=0.00,
                                        readonly=True, store=True, help='Total amount ready to invoice: Labour plus Material plus Subcontract plus Overhead amounts to invoice.')
    amount_to_invoice_expected = fields.Monetary(string="To-Invoice Amount Expected", compute='_compute_totals',
                                                 default=0.00, readonly=True, store=True, help='Expected invoice amount based on cost progress: Contract Total Amount multiplied by Amount To Invoice divided by Expected Cost.')
    amount_invoiced = fields.Monetary(string='Invoiced Amount', compute='_compute_totals', readonly=True, store=True,
                                      default=0.0, help='Total invoiced amount: sum of Labour, Material, Subcontract and Overhead invoiced amounts.')

    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            template_id = vals.get('template_id')
            if template_id:
                contract_template = self.env['contracting.order.template'].browse(template_id)
                vals['internal_reference'] = contract_template.template_sequence_id.next_by_id()
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.stage_id.sequence != 1:
                raise UserError(_('You can not delete Contract which is not draft'))
        return super(ContractingOrder, self).unlink()

    # purchase_order_line_ids = fields.One2many("purchase.order.line", inverse_name='account_analytic_id', )
    purchase_order_line_count = fields.Integer(compute='_purchase_order_line_count', help='Number of purchase order lines whose analytic distribution contains this contract analytic account.')

    timesheet_line_ids = fields.One2many("account.analytic.line", 'project_id', )
    timesheet_line_count = fields.Integer(compute='_timesheet_line_count', help='Number of analytic or timesheet lines linked to the project created for this contract.')

    # sales_orders_ids = fields.One2many('sale.order', 'analytic_account_id', string='Orders')
    sales_orders_count = fields.Integer(string='Sales Orders Count', compute='_sales_order_line_count', help='Number of sales orders having at least one line allocated to this contract analytic account.')

    # contract labour
    contract_labour = fields.One2many('contracting.order.line', 'contract_id', string='Contract Labour',
                                      copy=False, domain=[('line_type', '=', 'labour')])
    planned_hours = fields.Float(string='Duration', store=True, compute='_compute_labor_total', help='Total planned labour hours: sum of Planned Hours on all contract labour lines.')
    effective_hours = fields.Float(string='Hours Spent', store=True, compute='_compute_labor_total', help='Total labour hours spent: sum of billed or effective quantities on all contract labour lines.')
    remaining_hours = fields.Float(string='Remaining Hours', store=True, compute='_compute_labor_total', help='Total remaining labour hours: sum of Remaining Hours on all contract labour lines.')
    planned_hours_cost = fields.Float(string='Planned Hours Cost', store=True, compute='_compute_labor_total', help='Planned labour cost: sum of Planned Hours multiplied by Unit Price for all labour lines.')
    effective_hours_cost = fields.Float(string='Hours Spent Cost', store=True, compute='_compute_labor_total', help='Spent labour cost: sum of Billed or Effective Hours multiplied by Unit Price for all labour lines.')
    remaining_hours_cost = fields.Float(string='Remaining Hours Cost', store=True, compute='_compute_labor_total', help='Remaining labour cost: sum of Remaining Hours multiplied by Unit Price for all labour lines.')

    labour_progress = fields.Float("Labour Progress", compute='_compute_labor_total', store=True,  help='Labour progress percentage: Effective Hours divided by Planned Hours, multiplied by 100.')
    labour_estimate_cost = fields.Float(string="Labour Estimate Cost", store=True, required=False, default=0.0,
                                        compute='_compute_labor_total', help='Estimated labour cost: sum of Planned Hours multiplied by Unit Price for all labour lines.')
    labour_amount_to_invoice = fields.Monetary(string='LB.To-Invoice Amount', compute='_compute_labor_total',
                                               readonly=True, store=True, default=0.0, help='Sum of Amount To Invoice from all labour contract lines.')
    labour_amount_invoiced = fields.Monetary(string='LB.Invoiced Amount', compute='_compute_labor_total',
                                             readonly=True, store=True, default=0.0, help='Sum of Invoiced Amount from all labour contract lines.')

    # contract material
    contract_material = fields.One2many('contracting.order.line', 'contract_id', string='Contract Material',
                                        copy=False, domain=[('line_type', '=', 'material')])
    material_estimate_cost = fields.Float(string="Material Estimate Cost", store=True, required=False, default=0.0,
                                          compute='_compute_material_total', help='Estimated material cost: sum of Total on all material contract lines.')
    material_current_cost = fields.Float(string="Material Current Cost", store=True, required=False, default=0.0,
                                         compute='_compute_material_total', help='Current material cost: sum of Billed Amount on all material contract lines.')
    material_amount_to_invoice = fields.Monetary(string='MT.To-Invoice Amount', compute='_compute_material_total',
                                                 readonly=True, store=True, default=0.0, help='Sum of Amount To Invoice from all material contract lines.')
    material_amount_invoiced = fields.Monetary(string='MT.Invoiced Amount', compute='_compute_material_total',
                                               readonly=True, store=True, default=0.0, help='Sum of Invoiced Amount from all material contract lines.')
    material_progress = fields.Float("Material Progress", compute='_compute_material_total', store=True,  help='Material progress percentage: Current Material Cost divided by Estimated Material Cost, multiplied by 100.')

    # sub contract
    contract_subcontract = fields.One2many('contracting.order.line', 'contract_id', string='Contract Subcontract',
                                           copy=False, domain=[('line_type', '=', 'subcontract')])
    subcontract_estimate_cost = fields.Float(string="Subcontract Estimate Cost", store=True, required=False,
                                             default=0.0, compute='_compute_subcontract_total', help='Estimated subcontract cost: sum of Total on all subcontract contract lines.')
    subcontract_current_cost = fields.Float(string="Subcontract Current Cost", store=True, required=False, default=0.0,
                                            compute='_compute_subcontract_total', help='Current subcontract cost: sum of Billed Amount on all subcontract contract lines.')
    subcontract_amount_to_invoice = fields.Monetary(string='SC.To-Invoice Amount', compute='_compute_subcontract_total',
                                                    readonly=True, store=True, default=0.0, help='Sum of Amount To Invoice from all subcontract contract lines.')
    subcontract_amount_invoiced = fields.Monetary(string='SC.Invoiced Amount', compute='_compute_subcontract_total',
                                                  readonly=True, store=True, default=0.0, help='Sum of Invoiced Amount from all subcontract contract lines.')
    subcontract_progress = fields.Float("Sub-Contract Progress", compute='_compute_subcontract_total', store=True,  help='Subcontract progress percentage: Current Subcontract Cost divided by Estimated Subcontract Cost, multiplied by 100.')

    # overhead
    contract_overhead = fields.One2many('contracting.order.line', 'contract_id', string='Contract Over-Head',
                                        copy=False, domain=[('line_type', '=', 'overhead')])

    overhead_estimate_cost = fields.Float(string="Overhead Estimate Cost", store=True, required=False,
                                          default=0.0, compute='_compute_overhead_total', help='Estimated overhead cost: sum of Total on all overhead contract lines.')
    overhead_current_cost = fields.Float(string="Overhead Current Cost", store=True, required=False, default=0.0,
                                         compute='_compute_overhead_total', help='Current overhead cost: sum of Billed Amount on all overhead contract lines.')
    overhead_amount_to_invoice = fields.Monetary(string='OH.To-Invoice Amount', compute='_compute_overhead_total',
                                                 readonly=True, store=True, default=0.0, help='Sum of Amount To Invoice from all overhead contract lines.')
    overhead_amount_invoiced = fields.Monetary(string='OH.Invoiced Amount', compute='_compute_overhead_total',
                                               readonly=True, store=True, default=0.0, help='Sum of Invoiced Amount from all overhead contract lines.')
    overhead_progress = fields.Float("Over-Head Progress", compute='_compute_overhead_total', store=True,  help='Overhead progress percentage: Current Overhead Cost divided by Estimated Overhead Cost, multiplied by 100.')

    # clearances
    clearance_ids = fields.One2many(comodel_name="contracting.clearance", inverse_name="contract_id",
                                    string="Clearances", required=False, )
    clearance_count = fields.Integer(compute='_clearance_count', help='Number of clearance records linked to this contract.')
    is_clearance = fields.Boolean(string="Create Clearance", compute='_check_clearance_enable', help='Enabled when the actual margin percentage is greater than zero.')

    # variations
    variation_ids = fields.One2many(comodel_name="contracting.variation.order", inverse_name="contract_id",
                                    string="Variations", required=False, )
    variation_count = fields.Integer(string="Variations Count", required=False, compute='_variation_count', help='Number of variation orders linked to this contract.')
    variation_amount = fields.Monetary(string="Variation Amount", compute='compute_variation_amount', required=False,
                                       default=0.00, store=True, help='Sum of Variation Amount for variation orders in Done status.')

    contract_total_amount = fields.Monetary(string="Total Amount", required=False, default=0.00,
                                            compute='_compute_total_amount', store=True, help='Contract total amount: original Contract Amount plus done Variation Amount.')

    critical_rate = fields.Float(string="Critical Rate", default=0.00, store=True,
                                 compute='_compute_critical_rate', help='Critical rate: Current Expense divided by Expected Cost, multiplied by 100.')

    def _compute_critical_rate(self):
        for rec in self:
            if rec.cost_expected > 0:
                rec.critical_rate = ((rec.current_expense or 0.0) / (rec.cost_expected or 0.0)) * 100

    @api.depends('variation_amount', 'contract_amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.contract_total_amount = rec.variation_amount + rec.contract_amount

    @api.depends('variation_ids')
    def compute_variation_amount(self):
        for rec in self:
            variation_orders = rec.variation_ids.filtered(lambda order: order.state == 'done')
            if len(variation_orders) > 0:
                rec.variation_amount = sum([c.variation_amount for c in variation_orders])
            else:
                rec.variation_amount = 0

    def _check_clearance_enable(self):
        if self.margin_actual_percentage > 0:
            self.is_clearance = True
        else:
            self.is_clearance = False

    def _clearance_count(self):
        for rec in self:
            rec.clearance_count = len(self.clearance_ids) or 0

    def _variation_count(self):
        for rec in self:
            rec.variation_count = len(self.variation_ids) or 0

    # contract invoice status
    @api.depends('contract_material.invoice_status', 'contract_labour.invoice_status',
                 'contract_subcontract.invoice_status')
    def _get_invoiced(self):
        for rec in self:
            if any(line.invoice_status == 'to_invoice' for line in rec.contract_material) \
                    or any(line.invoice_status == 'to_invoice' for line in rec.contract_subcontract) \
                    or any(line.invoice_status == 'to_invoice' for line in rec.contract_labour):
                rec.contract_invoice_status = 'to_invoice'
            else:
                rec.contract_invoice_status = 'no'

    contract_invoice_status = fields.Selection([('no', 'Nothing to Invoice'),
                                                ('to_invoice', 'Waiting Invoice'),
                                                ('invoiced', 'Fully Invoiced'),
                                                ], string='Invoice Status', compute='_get_invoiced', store=True,
                                               readonly=True,
                                               copy=False, default='no', help='Waiting Invoice when any labour, material or subcontract line has an amount to invoice; otherwise Nothing to Invoice.')
    health = fields.Selection([('normal', 'Neutral'),
                               ('done', 'Good'),
                               ('bad', 'Bad')], string="Health", default='normal',
                              help="Contract health status", compute='_compute_contract_health', store=True)

    @api.depends('margin_actual_percentage')
    def _compute_contract_health(self):
        for rec in self:
            if not rec.margin_actual_percentage:
                return

            if rec.margin_actual_percentage > 20:
                rec.health = 'done'
            elif rec.margin_actual_percentage == 20:
                rec.health = 'normal'
            elif rec.margin_actual_percentage < 20:
                rec.health = 'bad'

    _sql_constraints = [
        (
            'check_advance_payment',
            'check(advance_payment_rate >= 0 and advance_payment_rate <= 100)',
            'Advance Payment Rate should be between 0% and 100%!',
        ),
        (
            'check_retention',
            'check(retention_rate >= 0 and retention_rate <= 100)',
            'Retention Rate should be between 0% and 100%!',
        ),
    ]

    def _purchase_order_line_count(self):
        for rec in self:
            rec.purchase_order_line_count = self.env['purchase.order.line'].search_count([
                ('analytic_distribution', 'ilike', f'"{rec.account_analytic_id.id}"')
            ])

    @api.depends('timesheet_line_ids')
    def _timesheet_line_count(self):
        for rec in self:
            if rec.project_id:
                rec.timesheet_line_count = self.env['account.analytic.line'].search_count(
                    [('project_id', '=', rec.project_id.id)])
            else:
                rec.timesheet_line_count = 0

    def _sales_order_line_count(self):
        for rec in self:
            if rec.account_analytic_id:
                rec.sales_orders_count = self.env['sale.order'].search_count(
                    [('order_line.analytic_distribution', 'ilike', f'"{rec.account_analytic_id.id}"')])
            else:
                rec.sales_orders_count = 0

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.sudo().search([('company_id', 'in', self.env.companies.ids)])

    def _get_default_stage_id(self):
        return self.env['contracting.order.stage'].search([('company_id', '=', self.env.company.id)], order='sequence', limit=1)

    def _get_default_starred_user_ids(self):
        return [(6, 0, [self.env.uid])]

    def _compute_starred(self):
        for rec in self:
            rec.starred = self.env.user in rec.starred_user_ids

    def _inverse_starred(self):
        starred_contracting = not_star_contracting = self.env['contracting.order'].sudo()
        for rec in self:
            if self.env.user in rec.starred_user_ids:
                starred_contracting |= rec
            else:
                not_star_contracting |= rec
        not_star_contracting.write({'starred_user_ids': [(4, self.env.uid)]})
        starred_contracting.write({'starred_user_ids': [(3, self.env.uid)]})

    def action_view_purchase_order_line(self):
        self.ensure_one()
        purchase_order_lines_obj = self.env['purchase.order.line']
        cost_ids = purchase_order_lines_obj.search(
            [('analytic_distribution', 'ilike', f'"{self.account_analytic_id.id}"')]).ids
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order Line',
            'res_model': 'purchase.order.line',
            'res_id': self.id,
            'domain': "[('id','in',[" + ','.join(map(str, cost_ids)) + "])]",
            'view_mode': 'list,form',
            'target': self.id,
        }
        return action

    def action_view_hr_timesheet_line(self):
        self.ensure_one()
        hr_timesheet = self.env['account.analytic.line']
        cost_ids = hr_timesheet.search([('project_id', '=', self.project_id.id)]).ids
        action = self.env.ref('hr_timesheet.timesheet_action_all').read()[0]
        action['domain'] = [('id', 'in', cost_ids)]
        return action

    def action_view_sale_orders(self):
        self.ensure_one()
        # action = self.env.ref('sale.view_order_tree').read()[0]
        return {
            'name': _('Contract Sales Orders'),
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form,pivot',
            'domain': [('order_line.analytic_distribution', 'ilike', f'"{self.account_analytic_id.id}"')],
            # 'context': {"default_sale_contract": self.id, },
        }

    def action_view_clearance_orders(self):
        self.ensure_one()
        # action = self.env.ref('sale.view_order_tree').read()[0]
        return {
            'name': _('Contract Clearance Orders'),
            'res_model': 'contracting.clearance',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
        }

    def _prepare_down_payment_order(self, down_payment_value):
        deposit_product = self.company_id.contracting_prepaid_product_id
        if not deposit_product:
            raise ValidationError(_("Down Payment Product Must Be Defined In Order To Create Down Payment Order"))

        res = dict()
        for rec in self:
            order_lines = []

            order_lines.append((0, 0, {
                'product_id': deposit_product.id,
                'name': deposit_product.name,
                'product_uom_id': deposit_product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': down_payment_value,
            }))

            addr = rec.partner_id.address_get(['delivery', 'invoice'])
            res[rec.id] = {
                'pricelist_id': rec.partner_id.property_product_pricelist.id,
                'partner_id': rec.partner_id.id,
                'partner_invoice_id': addr['invoice'],
                'partner_shipping_id': addr['delivery'],
                'currency_id': rec.partner_id.property_product_pricelist.currency_id.id,
                'order_line': order_lines,
                'origin': rec.internal_reference,
                'user_id': rec.user_id.id,
                'company_id': rec.company_id.id,
            }

        return res

    def prepare_down_payment_order(self, down_payment_value):
        self.ensure_one()
        # if not self.account_analytic_id:
        #     raise ValidationError(_("Analytic Account In Required In Order To Proceed With Contract."))

        values = self._prepare_down_payment_order(down_payment_value)
        order = self.env['sale.order'].create(values[self.id])
        order.message_post(body=(
                _("This Down Payment order has been created from the Contract ") + " <a href=# data-oe-model=contracting.order data-oe-id=%d>%s</a>" % (
            self.id, self.display_name)))
        order.order_line._compute_tax_id()

        self.write({'down_payment_order': order.id})
        self.set_open()

    @api.depends('contract_labour', 'contract_labour.remaining_hours')
    def _compute_labor_total(self):
        for rec in self:
            rec.planned_hours = sum([p.planned_hours for p in rec.contract_labour])
            rec.effective_hours = sum([p.quantity_billed for p in rec.contract_labour])
            rec.remaining_hours = sum([p.remaining_hours for p in rec.contract_labour])

            rec.planned_hours_cost = rec.labour_estimate_cost = sum(
                [(p.planned_hours * p.price_unit) for p in rec.contract_labour])
            rec.effective_hours_cost = sum([(p.quantity_billed * p.price_unit) for p in rec.contract_labour])
            rec.remaining_hours_cost = sum([(p.remaining_hours * p.price_unit) for p in rec.contract_labour])
            rec.labour_amount_to_invoice = sum([p.amount_to_invoice for p in rec.contract_labour])
            rec.labour_amount_invoiced = sum([p.amount_invoiced for p in rec.contract_labour])

            if rec.planned_hours > 0.0 and rec.effective_hours > 0.0:
                rec.labour_progress = (rec.effective_hours / rec.planned_hours) * 100
            else:
                rec.labour_progress = 0.0

    @api.depends('contract_material', 'contract_material.price_unit', 'contract_material.amount_billed')
    def _compute_material_total(self):
        for rec in self:
            rec.material_estimate_cost = sum([p.price_total for p in rec.contract_material])
            rec.material_current_cost = sum([p.amount_billed for p in rec.contract_material])
            rec.material_amount_to_invoice = sum([p.amount_to_invoice for p in rec.contract_material])
            rec.material_amount_invoiced = sum([p.amount_invoiced for p in rec.contract_material])
            if rec.material_current_cost > 0.0 and rec.material_estimate_cost > 0.0:
                rec.material_progress = (rec.material_current_cost / rec.material_estimate_cost) * 100
            else:
                rec.material_progress = 0.0

    @api.depends('contract_subcontract', 'contract_subcontract.price_unit', 'contract_subcontract.amount_billed')
    def _compute_subcontract_total(self):
        for rec in self:
            rec.subcontract_estimate_cost = sum([p.price_total for p in rec.contract_subcontract])
            rec.subcontract_current_cost = sum([p.amount_billed for p in rec.contract_subcontract])
            rec.subcontract_amount_to_invoice = sum([p.amount_to_invoice for p in rec.contract_subcontract])
            rec.subcontract_amount_invoiced = sum([p.amount_invoiced for p in rec.contract_subcontract])

            if rec.subcontract_current_cost > 0.0 and rec.subcontract_estimate_cost > 0.0:
                rec.subcontract_progress = (rec.subcontract_current_cost / rec.subcontract_estimate_cost) * 100
            else:
                rec.subcontract_progress = 0.0

    @api.depends('contract_overhead', 'contract_overhead.price_unit', 'contract_overhead.amount_billed')
    def _compute_overhead_total(self):
        for rec in self:
            rec.overhead_estimate_cost = sum([p.price_total for p in rec.contract_overhead])
            rec.overhead_current_cost = sum([p.amount_billed for p in rec.contract_overhead])
            rec.overhead_amount_to_invoice = sum([p.amount_to_invoice for p in rec.contract_overhead])
            rec.overhead_amount_invoiced = sum([p.amount_invoiced for p in rec.contract_overhead])

            if rec.overhead_current_cost > 0.0 and rec.overhead_estimate_cost > 0.0:
                rec.overhead_progress = (rec.overhead_current_cost / rec.overhead_estimate_cost) * 100
            else:
                rec.overhead_progress = 0.0

    @api.depends('account_analytic_id.credit', 'contract_total_amount')
    def _compute_income_rate(self):
        for rec in self:
            if rec.current_income > 0:
                rec.current_income_percentage = ((rec.current_income or 0.00) / (
                        rec.contract_total_amount or 0.00)) * 100
            else:
                rec.current_income_percentage = 0

    @api.depends('labour_estimate_cost', 'material_estimate_cost', 'subcontract_estimate_cost')
    def _compute_expected(self):
        for rec in self:
            rec.cost_expected = rec.labour_estimate_cost + rec.material_estimate_cost + rec.subcontract_estimate_cost + rec.overhead_estimate_cost
            rec.margin_expected = (rec.contract_total_amount or 0.00) - (rec.cost_expected or 0.00)
            if rec.contract_total_amount > 0:
                rec.margin_expected_percentage = (((rec.contract_total_amount or 0.00) - (
                        rec.cost_expected or 0.00)) / (
                                                          rec.contract_total_amount or 0.00)) * 100
            else:
                rec.margin_expected_percentage = 0

    @api.depends('account_analytic_id.debit', 'account_analytic_id.credit')
    def _compute_margins(self):
        for rec in self:
            if rec.current_expense != 0 and rec.current_income != 0:
                rec.margin_actual = (rec.current_income or 0.00) - (rec.current_expense or 0.00)

                if rec.margin_actual > 0:
                    rec.margin_actual_percentage = ((rec.margin_actual or 0.00) / (
                            rec.contract_total_amount or 0.00)) * 100
            else:
                rec.margin_actual = 0
                rec.margin_actual_percentage = 0

    @api.depends('contract_overhead.amount_to_invoice', 'contract_subcontract.amount_to_invoice',
                 'contract_labour.amount_to_invoice', 'contract_material.amount_to_invoice')
    def _compute_totals(self):
        for rec in self:
            rec.amount_to_invoice = rec.material_amount_to_invoice + rec.subcontract_amount_to_invoice \
                                    + rec.overhead_amount_to_invoice + rec.labour_amount_to_invoice
            rec.amount_invoiced = rec.labour_amount_invoiced + rec.overhead_amount_invoiced \
                                  + rec.subcontract_amount_invoiced + rec.material_amount_invoiced
            if rec.cost_expected > 0:
                rec.amount_to_invoice_expected = rec.contract_total_amount * (rec.amount_to_invoice / rec.cost_expected)
            else:
                rec.amount_to_invoice_expected = 0

            if rec.overhead_progress >= 0.0 and rec.subcontract_progress >= 0.0 and rec.material_progress >= 0.0 and rec.labour_progress >= 0.0:
                rec.contract_progress = (
                                                rec.overhead_progress + rec.subcontract_progress + rec.material_progress + rec.labour_progress) / 4
            else:
                rec.contract_progress = 0.0

    def action_view_down_payment_order(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": self.down_payment_order.id,
        }
        return action

    def action_view_variations(self):
        self.ensure_one()
        return {
            'name': _('Variation Orders'),
            'res_model': 'contracting.variation.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
        }

    def create_contract_labour(self):
        project_labour = self.env['contracting.order.line'].search([
            ('contract_id', '=', self.id),
            ('project_task_id', '=', False),
            ('line_type', '=', 'labour'), ], )
        # b - create labour tasks
        if len(project_labour) != 0:
            for line in project_labour:
                line.write({'project_task_id': self.env['project.task'].create({
                    'project_id': self.project_id.id,
                    'user_ids': [Command.set(self.user_id.ids)],
                    'allocated_hours': line.planned_hours,
                    'name': line.description, }).id})

    def create_contract_subcontract(self):
        # a - check labour exists
        project_subtract = self.env['contracting.order.line'].search([
            ('contract_id', '=', self.id),
            ('sale_subcontract_id', '=', False),
            ('line_type', '=', 'subcontract'), ], )
        # b - create subcontract tasks
        if len(project_subtract) != 0:
            for line in project_subtract:
                line.write({'sale_subcontract_id': self.env['contracting.order.sub'].create({
                    'sale_contract_id': self.id,
                    'company_id': self.company_id.id,
                    'user_id': self.user_id.id,
                    'partner_id': line.supplier_id.id,
                    'contract_date': self.contract_date,
                    'contract_amount': line.price_total,
                    'product_id': line.product_id.id,
                    'description': line.description, }).id})
                line.sale_subcontract_id.state = 'approved'
                line.sale_subcontract_id._onchange_state()

    def write(self, vals):
        last = self.stage_id
        res = super(ContractingOrder, self).write(vals)
        if self.env.context.get('skip_contracting_stage_automation'):
            return res
        now = self.stage_id

        if now.sequence and last.sequence:
            if now.sequence < last.sequence:
                if not self.env.user.has_group('contracting_management.sale_contracting_manager'):
                    raise ValidationError(_("Contracting Must Proceed In Forwarded Steps !"))

        if now.sequence == 2:
            # 1st create analytic account if not exists
            if not self.account_analytic_id:
                self.write({'account_analytic_id': self.env['account.analytic.account'].create({
                    'name': self.internal_reference,
                    'plan_id': self.template_id.analytic_plan_id.id,
                    'partner_id': self.partner_id.id}).id})

            # 2nd create project if not exist
            if not self.project_id:
                task_type = [(0, 0, {'name': _('New'), }),
                             (0, 0, {'name': _('Open'), }),
                             (0, 0, {'name': _('Close'), }),
                             (0, 0, {'name': _('Cancel'), })]
                self.write({'project_id': self.env['project.project'].create({
                    'name': self.internal_reference,
                    'partner_id': self.partner_id.id,
                    'account_id': self.account_analytic_id.id,
                    'type_ids': task_type,
                    'allow_billable': False,
                    'privacy_visibility': 'employees',
                    'is_contracting_project': True,
                }).id})
            # 3rd create tasks
            self.create_contract_labour()

            # 4th create sub contract tasks
            self.create_contract_subcontract()

    @api.constrains('account_analytic_id')
    def _constrains_account_analytic_id(self):
        for rec in self:
            if rec.account_analytic_id:
                check_analytic = self.env['contracting.order'].search([
                    ('id', '!=', rec.id),
                    ('account_analytic_id', '=', rec.account_analytic_id.id), ], limit=1)

                if check_analytic:
                    raise ValidationError(_("Analytic Account Is Already Used In Another Contract."))

    def set_open(self):
        search = self.env['contracting.order.stage'].search
        for sub in self:
            stage = search([('in_progress', '=', True), ('sequence', '>=', sub.stage_id.sequence)], limit=1)
            if not stage:
                stage = search([('in_progress', '=', True)], limit=1)
            sub.write({'stage_id': stage.id})

    def _refresh_statistics_now(self):
        """Synchronously refresh statistics for the affected contracts.

        Source-model hooks call this method after a business change.  Contracts
        are grouped by company so company-dependent fields and check_company
        validations use the correct environment.  A context flag prevents the
        writes performed by the refresh itself from triggering another refresh.
        """
        if not self or self.env.context.get('skip_contract_statistics_refresh'):
            return
        for company in self.mapped('company_id'):
            contracts = self.filtered(lambda contract: contract.company_id == company)
            contracts = contracts.sudo().with_company(company).with_context(
                skip_contract_statistics_refresh=True,
                allowed_company_ids=[company.id],
            )
            contracts.update_statistics()
            contracts._compute_contract_health()

    def update_statistics(self):
        """Refresh contract statistics in batches.

        This method is intentionally recordset-aware because it is called by the
        real-time refresh hooks.  Aggregates are fetched once and all contract lines are
        refreshed as recordsets instead of issuing one search per line.
        """
        if not self:
            return

        clearance_groups = self.env['contracting.clearance'].read_group(
            [('state', '=', 'invoiced'), ('contract_id', 'in', self.ids)],
            ['contract_id', 'amount_deduct_from_ap:sum', 'retention_amount:sum'],
            ['contract_id'],
            lazy=False,
        )
        clearance_totals = {
            group['contract_id'][0]: (
                group.get('amount_deduct_from_ap', 0.0) or 0.0,
                group.get('retention_amount', 0.0) or 0.0,
            )
            for group in clearance_groups if group.get('contract_id')
        }
        for contract in self:
            consumed, retention = clearance_totals.get(contract.id, (0.0, 0.0))
            contract.consumed_down_payment = consumed
            contract.retention_balance = retention

        subcontract_records = self.mapped('contract_subcontract.sale_subcontract_id')
        if subcontract_records:
            subcontract_records.update_statistics()

        all_lines = (
            self.mapped('contract_material')
            | self.mapped('contract_subcontract')
            | self.mapped('contract_labour')
            | self.mapped('contract_overhead')
        )
        if all_lines:
            all_lines._update_statistics()

        self._compute_income_rate()
        self.compute_variation_amount()

    def compute_clearance_retention_amount(self):
        clearance_retention_amount = 0
        for contract in self:
            if contract.retention_rate and contract.amount_to_invoice_expected:
                clearance_retention_amount = contract.amount_to_invoice_expected * (contract.retention_rate / 100)
            else:
                clearance_retention_amount = 0
        return clearance_retention_amount

    def compute_clearance_down_payment_consumption_amount(self):
        amount_deduct_from_ap = 0
        for contract in self:
            if contract.cost_expected:
                amount_deduct_from_ap = contract.remain_down_payment * (
                        contract.amount_to_invoice / contract.cost_expected)
                if amount_deduct_from_ap > contract.remain_down_payment:
                    amount_deduct_from_ap = contract.remain_down_payment
            else:
                amount_deduct_from_ap = 0

        return amount_deduct_from_ap

    def create_clearance(self):
        # check if open clearance
        unconfirmed_orders = self.clearance_ids.filtered(lambda so: so.state == 'draft')
        if unconfirmed_orders:
            raise ValidationError(
                _("All Clearances Must Be Closed Before Create New , please Check Previous Clearances"))

        # contract_remain_payment = self.contract_total_amount - self.current_income
        # if self.amount_to_invoice_expected > contract_remain_payment:
        #     raise UserError(_('Clearance Amount exceeds Contract Total Amount , Please Review'))

        # create clearance
        for contract in self:
            # add consumed form down payment
            amount_deduct_from_ap = self.compute_clearance_down_payment_consumption_amount()

            # add retention amount
            retention_amount = self.compute_clearance_retention_amount()

            # creat clearance
            clearance_id = contract.env['contracting.clearance'].create({
                'contract_id': contract.id,
                'retention_amount': retention_amount,
                'amount_deduct_from_ap': amount_deduct_from_ap,
                'amount_deduct_from_ap_min': amount_deduct_from_ap,
                'amount_to_invoice_expected': contract.amount_to_invoice_expected,
                'amount_to_invoice_actual': contract.amount_to_invoice_expected,
                'amount_to_invoice': contract.amount_to_invoice,
                'cost_expected': contract.cost_expected,
                'down_payment': contract.down_payment,
            })

            # labour
            for line in contract.contract_labour.filtered(lambda x: x.amount_to_invoice > 0):
                self.env['contracting.clearance.line'].create({
                    'clearance_id': clearance_id.id,
                    'contract_line_id': line.id,
                    'qty_to_invoice': line.qty_to_invoice,
                    'amount_to_invoice': line.amount_to_invoice,
                    'amount_actual': line.amount_to_invoice
                })

            # Material
            for line in contract.contract_material.filtered(lambda x: x.amount_to_invoice > 0):
                self.env['contracting.clearance.line'].create({
                    'clearance_id': clearance_id.id,
                    'contract_line_id': line.id,
                    'qty_to_invoice': line.qty_to_invoice,
                    'amount_to_invoice': line.amount_to_invoice,
                    'amount_actual': line.amount_to_invoice
                })

            # Sub-Contract
            for line in contract.contract_subcontract.filtered(lambda x: x.amount_to_invoice > 0):
                self.env['contracting.clearance.line'].create({
                    'clearance_id': clearance_id.id,
                    'contract_line_id': line.id,
                    'qty_to_invoice': line.qty_to_invoice,
                    'amount_to_invoice': line.amount_to_invoice,
                    'amount_actual': line.amount_to_invoice
                })

            # Overhead
            for line in contract.contract_overhead.filtered(lambda x: x.amount_to_invoice > 0):
                self.env['contracting.clearance.line'].create({
                    'clearance_id': clearance_id.id,
                    'contract_line_id': line.id,
                    'qty_to_invoice': line.qty_to_invoice,
                    'amount_to_invoice': line.amount_to_invoice,
                    'amount_actual': line.amount_to_invoice
                })

            return {
                "type": "ir.actions.act_window",
                "res_model": "contracting.clearance",
                "views": [[False, "form"]],
                "res_id": clearance_id.id,
            }


    def action_open_expenses_vendor_invoice(self):
        self.ensure_one()
        account_invoice_lines_obj = self.env['account.move.line']
        line_ids = account_invoice_lines_obj.search(
            [('analytic_distribution', 'ilike', f'"{self.account_analytic_id.id}"')]).ids
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        action['domain'] = [('invoice_line_ids', 'in', line_ids), ('move_type', '=', 'in_invoice')]
        return action
