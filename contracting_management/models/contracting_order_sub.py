# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractingOrderSub(models.Model):
    _name = 'contracting.order.sub'
    _description = 'Contracting Order Sub'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'internal_reference'
    _check_company_auto = True

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    internal_reference = fields.Char(string='Contact Reference', copy=False, readonly=True, index=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string='Company', required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string='Created By', readonly=True, )
    team_id = fields.Many2one(
        'crm.team', 'Sales Team', change_default=True, default=_get_default_team,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", readonly=True, )
    description = fields.Text(string='Description', readonly=True, )
    note = fields.Text(string='Notes', readonly=True, )
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id, readonly=True, )

    partner_id = fields.Many2one('res.partner', string='Vendor', required=True,
                                 readonly=True,
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    contract_date = fields.Date(string='Contract Date', readonly=True, )
    start_date = fields.Date(string='Create Date', readonly=True, default=fields.Date.today(), )
    complete_date = fields.Date(string='Closed Date', readonly=True, )

    sale_contract_id = fields.Many2one('contracting.order', string='Sale Contract Reference', required=True, ondelete='cascade', index=True, copy=False, check_company=True)
    project_id = fields.Many2one('project.project', string='Project', related='sale_contract_id.project_id', store=True)
    project_task_id = fields.Many2one(comodel_name="project.task", string="Task", required=False, readonly=True)
    sale_contract_partner_id = fields.Many2one('res.partner', string='Contacting Partner',
                                               related='sale_contract_id.partner_id')
    contract_amount = fields.Monetary(string="Contract Amount", required=False, default=0.00, readonly=True, )
    contract_actual_amount = fields.Monetary(string="Actual Amount", compute='_compute_total', required=False,
                                             default=0.00, store=True, help='Actual subcontract amount: sum of Unit Price across the subcontract task lines.')
    contract_amount_remain = fields.Monetary(string="Remain Amount", default=0.00,
                                             compute='_compute_remain_amount', store=True, help='Remaining subcontract amount: Contract Amount minus Actual Amount.')
    amount_invoiced = fields.Monetary('Amount Billed', compute='_compute_total', default=0.0, readonly=True,
                                      store=True, help='Total subcontract amount invoiced from the related subcontract task lines and statistics.')
    amount_un_invoiced = fields.Monetary('UnBilled Amount', compute='_compute_un_invoiced', default=0.0, readonly=True,
                                         store=True, help='Unbilled subcontract amount: Actual Amount minus Amount Billed.')
    sale_contract_line = fields.One2many(comodel_name="contracting.order.line", inverse_name="sale_subcontract_id",
                                         string="Original Contract Line", required=False, readonly=True, )

    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="['&',('sale_ok', '=', True),('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('progress', 'In Progress'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', copy=False, index=True, tracking=3, default='draft')

    def _get_invoiced(self):
        # need to implment
        pass

    invoice_status = fields.Selection([('no', 'Nothing to Bill'),
                                       ('to_invoice', 'Waiting Bills'),
                                       ('invoiced', 'Fully Billed'),
                                       ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True,
                                      copy=False, default='no', help='Invoice status computed for the subcontract record by the subcontract invoice-status calculation.')
    subcontract_task = fields.One2many('contracting.order.sub.task', 'sub_contract_id', string='Payment Items',
                                       copy=False, readonly=True, )

    @api.depends('subcontract_task.purchase_order_lines.order_id')
    def _compute_purchase_ids(self):
        for rec in self:
            orders = rec.mapped('subcontract_task.purchase_order_lines.order_id')
            rec.purchase_ids = orders
            rec.purchase_count = len(orders)

    purchase_count = fields.Integer(string='Purchase Count', compute='_compute_purchase_ids', help='Number of distinct purchase orders linked through subcontract task purchase lines.')
    purchase_ids = fields.Many2many('purchase.order', compute="_compute_purchase_ids", string='Purchase Orders',
                                    copy=False, help='Purchase orders collected from all purchase lines linked to this subcontract task.')

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get('sale_contract_id'):
                vals['company_id'] = self.env['contracting.order'].browse(vals['sale_contract_id']).company_id.id
            if vals.get('internal_reference', _('New')) == _('New'):
                vals['internal_reference'] = self.env['ir.sequence'].next_by_code('contracting.order.sub') or _('New')
        records = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            records.mapped('sale_contract_id')._refresh_statistics_now()
        return records

    def write(self, vals):
        relevant = {
            'sale_contract_id', 'state', 'contract_amount', 'project_task_id',
            'subcontract_task', 'product_id',
        }
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self.mapped('sale_contract_id') if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self.mapped('sale_contract_id'))._refresh_statistics_now()
        return result

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete Contract which is not draft or cancelled.'))
        contracts = self.mapped('sale_contract_id')
        result = super(ContractingOrderSub, self).unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result

    @api.depends('subcontract_task', 'subcontract_task.price_unit', 'subcontract_task.amount_invoiced')
    def _compute_total(self):
        for rec in self:
            rec.contract_actual_amount = sum([p.price_unit for p in rec.subcontract_task]) or 0.0
            rec.amount_invoiced = sum([p.amount_invoiced for p in rec.subcontract_task]) or 0.0

    @api.depends('contract_amount', 'contract_actual_amount')
    def _compute_remain_amount(self):
        for rec in self:
            rec.contract_amount_remain = rec.contract_amount - rec.contract_actual_amount

    @api.depends('amount_invoiced', 'contract_actual_amount')
    def _compute_un_invoiced(self):
        for rec in self:
            rec.amount_un_invoiced = rec.contract_actual_amount - rec.amount_invoiced

    def reset_to_draft(self):
        pass

    @api.onchange('state')
    def _onchange_state(self):
        for rec in self:
            if rec.state == 'approved':
                rec.write({'project_task_id': self.env['project.task'].create({
                    'project_id': rec.project_id.id,
                    'user_ids': [rec.user_id.id],
                    'supplier_id': rec.partner_id.id,
                    'is_subcontractor_task': True,
                    'name': rec.description, }).id})
                rec.sale_contract_line.project_task_id = rec.project_task_id

    def action_view_purchase_orders(self):
        self.ensure_one()
        self.sudo()._read(['purchase_ids'])

        # action = self.env.ref('sale.view_order_tree').read()[0]
        return {
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.purchase_ids.ids)],
        }

    @api.depends('sale_contract_line.price_unit')
    def update_contract_amount(self):
        for rec in self:
            rec.contract_amount = rec.sale_contract_line[:1].price_unit or 0.0

    @api.depends('sale_contract_line.product_id')
    def update_sub_contract_product(self):
        for rec in self:
            rec.product_id = rec.sale_contract_line[:1].product_id

    def update_statistics(self):
        tasks = self.mapped('subcontract_task')
        if tasks:
            tasks._update_statistics()
        self.update_contract_amount()
        self.update_sub_contract_product()



class SaleSubContractingTask(models.Model):
    _name = 'contracting.order.sub.task'
    _description = 'Sale Sub Contracting Line'
    _order = 'sub_contract_id, sequence, id'

    sub_contract_id = fields.Many2one('contracting.order.sub', string='Sub-Contract Reference', required=True,
                                      ondelete='cascade', index=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(related='sub_contract_id.company_id', string='Company', store=True, readonly=True,
                                 index=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='sub_contract_id.currency_id')
    partner_id = fields.Many2one(related='sub_contract_id.partner_id', store=True, string='Customer', readonly=False)
    project_id = fields.Many2one('project.project', string='Project', related='sub_contract_id.project_id', store=True)
    description = fields.Char(string='Description', copy=False, required=True, )
    project_task_id = fields.Many2one(comodel_name="project.task", string="Task", required=False, readonly=True)
    task_created = fields.Boolean(string="Task Created", default=False)
    task_date = fields.Date(string="Date", required=True, )
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    amount_invoiced = fields.Float('Amount Invoiced', digits='Product Price', default=0.0, readonly=True)
    purchase_order_id = fields.Many2one(comodel_name="purchase.order", string="Purchase Order", required=False, )
    purchase_order_lines = fields.One2many('purchase.order.line', 'subcontract_line_id', string="Purchase Lines",
                                           readonly=True, copy=False)
    purchase_created = fields.Boolean(string="Purchase Created", default=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            records.mapped('sub_contract_id.sale_contract_id')._refresh_statistics_now()
        return records

    def write(self, vals):
        relevant = {
            'sub_contract_id', 'price_unit', 'project_task_id',
            'purchase_order_id', 'purchase_order_lines', 'amount_invoiced',
        }
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self.mapped('sub_contract_id.sale_contract_id') if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self.mapped('sub_contract_id.sale_contract_id'))._refresh_statistics_now()
        return result

    def action_create_subtask(self):
        for rec in self:
            rec.write({'project_task_id': self.env['project.task'].create({
                'project_id': rec.project_id.id,
                'user_ids': [rec.sub_contract_id.user_id.id],
                'parent_id': rec.sub_contract_id.project_task_id.id,
                'name': rec.description, }).id, 'task_created': True})

    def unlink(self):
        for rec in self:
            if rec.project_task_id:
                raise UserError(_('You can not delete Line which has task related.'))
        contracts = self.mapped('sub_contract_id.sale_contract_id')
        result = super(SaleSubContractingTask, self).unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result

    def create_purchase_order(self):
        # create Purchase order
        for rec in self:
            po = self.env['purchase.order'].with_context(skip_contract_statistics_refresh=True).create({
                'partner_id': rec.partner_id.id,
                'company_id': rec.company_id.id,
            })

            po_line = self.env['purchase.order.line'].with_context(skip_contract_statistics_refresh=True).create({
                'order_id': po.id,
                'name': rec.description,
                'product_id': rec.sub_contract_id.product_id.id,
                'product_qty': 1,
                'product_uom_id': rec.sub_contract_id.product_id.uom_po_id.id,
                'price_unit': rec.price_unit,
                'date_planned': rec.task_date,
                'subcontract_line_id': rec.id,
                'analytic_distribution': {str(rec.sub_contract_id.sale_contract_id.account_analytic_id.id): 100},
            })

            message = _(
                "This Purchase Order has been created from the Sub-Contract : <a href=# data-oe-model=contracting.order.sub data-oe-id=%d>%s</a>") % (
                          rec.sub_contract_id.id, rec.sub_contract_id.description)
            po.message_post(body=message)
            po.button_confirm()
            rec.with_context(skip_contract_statistics_refresh=True).write({
                'purchase_order_id': po.id,
                'purchase_order_lines': po_line,
                'purchase_created': True,
                'amount_invoiced': rec.price_unit,
            })
            rec.sub_contract_id.sale_contract_id._refresh_statistics_now()

            return {
                "type": "ir.actions.act_window",
                "res_model": "purchase.order",
                "views": [[False, "form"]],
                "res_id": po.id,
            }

    def _update_statistics(self):
        if not self:
            return

        purchase_groups = self.env['purchase.order.line'].read_group(
            [
                ('state', 'in', ('purchase', 'done')),
                ('subcontract_line_id', 'in', self.ids),
            ],
            ['subcontract_line_id', 'price_total:sum'],
            ['subcontract_line_id'],
            lazy=False,
        )
        totals = {
            group['subcontract_line_id'][0]: (group.get('price_total', 0.0) or 0.0)
            for group in purchase_groups if group.get('subcontract_line_id')
        }

        for rec in self:
            rec.amount_invoiced = totals.get(rec.id, 0.0)
