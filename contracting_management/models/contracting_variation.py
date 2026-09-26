# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractVariationReason(models.Model):
    _name = 'contracting.variation.reason'
    _rec_name = 'name'
    _description = 'Contracting Variation Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True, translate=True)
    description = fields.Text("Description",
                              help="Enter here the internal requirements for this stage. It will appear "
                                   "as a tooltip over the stage's name.", translate=True)
    sequence = fields.Integer(default=1)
    active = fields.Boolean('Active', default=True, help="Set active to false to hide the Brand without removing it.")
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)

    variation_ids = fields.One2many(comodel_name="contracting.variation.order", inverse_name="reason_id",
                                    string="Variations Count", required=False, )
    variation_count = fields.Integer('# Requests', compute='_compute_variation_count',  help='Number of variation orders using this variation reason.')

    def _compute_variation_count(self):
        for rec in self:
            rec.variation_count = len(rec.variation_ids.ids)


class ContractingVariationOrder(models.Model):
    _name = 'contracting.variation.order'
    _description = 'Contracting Variation Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'internal_reference'
    _order = 'order_date desc, id desc'
    _check_company_auto = True

    internal_reference = fields.Char(string='Extension Reference', copy=False, readonly=True, index=True,
                                     default=lambda self: _('New'))
    description = fields.Text(string='Description', readonly=True)
    order_date = fields.Date(string='Date', required=True, readonly=True,
                             default=fields.Date.today(), )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string='Company', required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string='Created By', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    contract_id = fields.Many2one(comodel_name="contracting.order", string="Contract", required=True, readonly=True, check_company=True, index=True)
    partner_id = fields.Many2one('res.partner', related='contract_id.partner_id', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='contract_id.currency_id')
    reason_id = fields.Many2one(comodel_name="contracting.variation.reason", string="Reason", required=True,
                                readonly=True, )
    variation_amount = fields.Monetary(string="Amount", required=True, default=0.00, store=True, readonly=True)
    variation_cost = fields.Monetary(string="Cost", compute='_compute_variation_total', required=False,
                                     default=0.00, store=True, help='Variation cost: sum of Total Line across all variation order lines.')
    order_lines = fields.One2many(comodel_name="contracting.variation.line", inverse_name="variation_id",
                                  string="Order Lines", required=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get('contract_id'):
                vals['company_id'] = self.env['contracting.order'].browse(vals['contract_id']).company_id.id
            if vals.get('internal_reference', _('New')) == _('New'):
                vals['internal_reference'] = self.env['ir.sequence'].next_by_code('contracting.variation.order') or _('New')
        records = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            records.mapped('contract_id')._refresh_statistics_now()
        return records

    def write(self, vals):
        relevant = {'state', 'contract_id', 'variation_amount', 'order_lines'}
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self.mapped('contract_id') if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self.mapped('contract_id'))._refresh_statistics_now()
        return result

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You can not delete Contract which is not draft'))
        contracts = self.mapped('contract_id')
        result = super(ContractingVariationOrder, self).unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result

    def set_draft(self):
        return self.write({'state': 'draft'})

    def apply_contract_changes(self):
        for line in self.order_lines:
            exist_product = self.env['contracting.order.line'].search(
                [('contract_id', '=', line.contract_id.id),
                 ('product_id', '=', line.product_id.id)])

            if not line.is_modifiable:
                exist_product.update({'product_qty': exist_product.product_qty + line.product_qty,
                                      'planned_hours': exist_product.planned_hours + line.planned_hours,
                                      })
            else:
                contract_line = self.env['contracting.order.line'].create({
                    'contract_id': line.contract_id.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'line_type': line.line_type,
                    'planned_hours': line.planned_hours,
                    'price_unit': line.price_unit,
                    'description': line.description,
                    'supplier_id': line.supplier_id.id,
                })

                if line.line_type == 'overhead':
                    contract_line.action_approve()
        # activate other lines
        self.contract_id.create_contract_labour()
        self.contract_id.create_contract_subcontract()
        self.contract_id._refresh_statistics_now()

    def action_confirm(self):
        if len(self.order_lines.ids) == 0:
            raise UserError(_('You Must Add Variation Data.'))

        for line in self.order_lines:
            line.check_required_data()

        self.apply_contract_changes()
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancel'})

    @api.depends('order_lines', 'order_lines.price_total')
    def _compute_variation_total(self):
        for rec in self:
            rec.variation_cost = sum([p.price_total for p in rec.order_lines])

    @api.constrains("variation_amount", "variation_cost")
    def _constrains_variation_amount(self):
        for rec in self:
            if rec.variation_amount < rec.variation_cost:
                raise UserError(_('Variation Amount Must Be Greater Than Or Equal To Variation Cost'))


class ContractingVariationLine(models.Model):
    _name = 'contracting.variation.line'
    _description = 'Contracting Variation Order Line'
    _order = 'contract_id, sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    variation_id = fields.Many2one(comodel_name="contracting.variation.order", string="Variation Order", required=True,
                                   ondelete='cascade', index=True, copy=False)
    company_id = fields.Many2one(related='variation_id.company_id', string='Company', store=True, readonly=True,
                                 index=True)
    contract_id = fields.Many2one(related='variation_id.contract_id', string="Contract", store=True, readonly=True,
                                  index=True)
    line_type = fields.Selection(selection=[('material', 'Material'),
                                            ('labour', 'Labour'),
                                            ('subcontract', 'Sub Contract'),
                                            ('overhead', 'Over-Head'),
                                            ], string="Type", required=True, )
    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="[('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', required=True)
    description = fields.Char(string='Description', copy=False, )
    product_qty = fields.Float(string='Planned Qty', copy=False, default=0.0)
    uom_id = fields.Many2one('uom.uom', string='Uom')
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    planned_hours = fields.Float(string='Duration')
    price_total = fields.Monetary(compute='_compute_total', string='Total Line', readonly=True, store=True, help='Variation line total: Planned Hours multiplied by Unit Price for labour; otherwise Product Quantity multiplied by Unit Price.')
    original_total = fields.Monetary(string='Original Value', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='variation_id.currency_id')
    is_modifiable = fields.Boolean(default=True)
    supplier_id = fields.Many2one('res.partner', string='Subcontractor', required=False,
                                  domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                  help="You can find a vendor by its Name, TIN, Email or Internal Reference.")

    @api.depends('product_qty', 'planned_hours', 'price_unit')
    def _compute_total(self):
        for line in self:
            if line.line_type == 'labour':
                line.price_total = line.planned_hours * line.price_unit
            else:
                line.price_total = line.product_qty * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return

        vals = {}
        if not self.uom_id or (self.product_id.uom_id.id != self.uom_id.id):
            vals['uom_id'] = self.product_id.uom_id
            vals['product_qty'] = self.product_qty or 1.0

        if not self.description:
            vals['description'] = self.product_id.name

        # check if line exists in contract
        # bring product contract value
        exist_product = self.env['contracting.order.line'].search(
            [('contract_id', '=', self.contract_id.id),
             ('product_id', '=', self.product_id.id)])

        if exist_product:
            vals['line_type'] = exist_product.line_type
            vals['original_total'] = exist_product.price_total
            vals['supplier_id'] = exist_product.supplier_id
            vals['price_unit'] = exist_product.price_unit
            vals['is_modifiable'] = False

        self.update(vals)

    _sql_constraints = [
        (
            'variation_product_uniq',
            'unique (variation_id, product_id)',
            'Duplicate products in Variation line not allowed !',
        ),
    ]

    def check_required_data(self):
        pass
