# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.fields import Domain


class ContractingOrderLine(models.Model):
    _name = 'contracting.order.line'
    _description = 'Contracting Order Line'
    _order = 'contract_id, sequence, id'
    _rec_name = 'name'
    _check_company_auto = True

    name = fields.Text(string="Description", compute='_compute_name',
                       store=True, readonly=False, required=True, precompute=True, help='Generated description: Contract Internal Reference followed by the Product Name.')

    contract_id = fields.Many2one('contracting.order', string='Contract Reference', required=True, ondelete='cascade',
                                  index=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(related='contract_id.company_id', string='Company', store=True, readonly=True,
                                 index=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='contract_id.currency_id')
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Customer', readonly=False)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account',
                                          related='contract_id.account_analytic_id', store=True)
    product_id = fields.Many2one('product.product', string='Product',
                                 domain="[('is_contracting','=' , True),'|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                 change_default=True, ondelete='restrict', required=True, check_company=True)

    description = fields.Char(string='Line Note', copy=False, )
    product_qty = fields.Float(string='Planned Qty', copy=False, default=1)
    uom_id = fields.Many2one('uom.uom', string='Uom')
    line_type = fields.Selection(selection=[('material', 'Material'),
                                            ('labour', 'Labour'),
                                            ('subcontract', 'Sub Contract'),
                                            ('overhead', 'Over-Head'),
                                            ], string="Type", required=True, default='labour')
    project_task_id = fields.Many2one(comodel_name="project.task", string="Task", required=False, readonly=True)

    planned_hours = fields.Float(string='Duration')

    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)

    price_total = fields.Monetary(compute='_compute_total', string='Total', readonly=True, store=True, help='Line total: Planned Hours multiplied by Unit Price for labour; otherwise Planned Quantity multiplied by Unit Price.')

    sale_subcontract_id = fields.Many2one(comodel_name="contracting.order.sub", string="Sub-Contract", required=False, index=True,
                                          readonly=True)
    supplier_id = fields.Many2one('res.partner', string='Subcontractor', required=False,
                                  domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                  help="You can find a vendor by its Name, TIN, Email or Internal Reference.")

    remaining_hours = fields.Float(string='R.Hours', compute='_update_statistics', store=True, help='For labour lines, Remaining Hours equals Planned Hours minus effective or billed project-task hours.')
    quantity_billed = fields.Float(string='Billed Quantity', compute='_update_statistics',
                                   digits='Product Unit of Measure', readonly=True, store=True, default=0.0, help='Billed or effective quantity derived from confirmed purchase quantities, project-task effective hours, or subcontract progress according to line type.')
    amount_billed = fields.Monetary(string='Billed Amount', compute='_update_statistics', readonly=True, store=True,
                                    default=0.0, help='Billed or current cost derived from related purchase lines or subcontract invoiced amount according to line type.')
    qty_to_invoice = fields.Float(string='To Invoice Quantity', store=True, readonly=True,
                                  digits='Product Unit of Measure', default=0.0)
    amount_to_invoice = fields.Monetary(string='To-Invoice Amount', readonly=True, store=True, default=0.0)
    quantity_invoiced = fields.Float(string='Invoiced Quantity',
                                     digits='Product Unit of Measure', readonly=True, store=True, default=0.0)
    amount_invoiced = fields.Monetary(string='Invoiced Amount', readonly=True, store=True, default=0.0)
    purchase_created = fields.Boolean(string="Purchase Created", default=False)
    line_approved = fields.Boolean(string="Approved", default=False)

    @api.depends('amount_to_invoice')
    def _get_invoiced(self):
        for rec in self:
            if rec.amount_to_invoice > 0:
                rec.invoice_status = 'to_invoice'
            elif rec.amount_to_invoice == 0 and rec.price_total > rec.amount_invoiced:
                rec.invoice_status = 'no'
            elif rec.amount_to_invoice == 0 and rec.price_total == rec.amount_invoiced:
                rec.invoice_status = 'invoiced'

    invoice_status = fields.Selection([('no', 'Nothing to Invoice'),
                                       ('to_invoice', 'Waiting Invoice'),
                                       ('invoiced', 'Fully Invoiced'),
                                       ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True,
                                      copy=False, default='no', help='Waiting Invoice when Amount To Invoice is positive; Fully Invoiced when the full line total is invoiced; otherwise Nothing to Invoice.')

    _sql_constraints = [
        (
            'contract_product_uniq',
            'unique (contract_id, product_id)',
            'Duplicate products in Contract line not allowed !',
        ),
    ]

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

        self.update(vals)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            lines.mapped('contract_id')._refresh_statistics_now()
        return lines

    def write(self, vals):
        relevant = {
            'contract_id', 'line_type', 'product_id', 'product_qty', 'planned_hours',
            'price_unit', 'project_task_id', 'sale_subcontract_id', 'account_analytic_id',
        }
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self.mapped('contract_id') if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self.mapped('contract_id'))._refresh_statistics_now()
        return result

    def unlink(self):
        contracts = self.mapped('contract_id')
        result = super().unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result

    def create_purchase_order(self):
        # create Purchase order
        for rec in self:
            po = self.env['purchase.order'].with_context(skip_contract_statistics_refresh=True).create({
                'partner_id': rec.supplier_id.id,
                'company_id': rec.company_id.id,
            })

            po_line = self.env['purchase.order.line'].with_context(skip_contract_statistics_refresh=True).create({
                'order_id': po.id,
                'name': rec.description,
                'product_id': rec.product_id.id,
                'product_qty': 1,
                'product_uom_id': rec.product_id.uom_po_id.id,
                'price_unit': rec.price_unit,
                'date_planned': fields.Date.today(),
                'analytic_distribution': {str(rec.contract_id.account_analytic_id.id): 100}
            })

            message = _(
                "This Purchase Order has been created from Contracting Number : <a href=# data-oe-model=contracting.order data-oe-id=%d>%s</a>") % (
                          rec.contract_id.id, rec.contract_id.description)
            po.message_post(body=message)
            po.button_confirm()
            rec.with_context(skip_contract_statistics_refresh=True).write({'purchase_created': True})
            rec.contract_id._refresh_statistics_now()

            return {
                "type": "ir.actions.act_window",
                "res_model": "purchase.order",
                "views": [[False, "form"]],
                "res_id": po.id,
            }

    def action_approve(self):
        for rec in self:
            rec.write({'line_approved': True})

    def _update_statistics(self):
        if not self:
            return

        # Invoiced clearance totals are aggregated by PostgreSQL for the whole recordset.
        clearance_groups = self.env['contracting.clearance.line'].read_group(
            [('state', '=', 'invoiced'), ('contract_line_id', 'in', self.ids)],
            ['contract_line_id', 'qty_to_invoice:sum', 'amount_to_invoice:sum'],
            ['contract_line_id'],
            lazy=False,
        )
        invoiced = {
            group['contract_line_id'][0]: (
                group.get('qty_to_invoice', 0.0) or 0.0,
                group.get('amount_to_invoice', 0.0) or 0.0,
            )
            for group in clearance_groups if group.get('contract_line_id')
        }

        for rec in self:
            rec.quantity_invoiced, rec.amount_invoiced = invoiced.get(rec.id, (0.0, 0.0))

        # Material / overhead purchases: one query for all involved analytic accounts.
        purchase_lines_by_key = {}
        purchase_based = self.filtered(lambda line: line.line_type in ('material', 'overhead'))
        analytic_ids = set(purchase_based.mapped('account_analytic_id').ids)
        product_ids = purchase_based.mapped('product_id').ids
        if analytic_ids and product_ids:
            analytic_domain = Domain.OR([
                Domain('analytic_distribution', 'ilike', f'"{analytic_id}"')
                for analytic_id in analytic_ids
            ])
            purchase_domain = Domain.AND([
                Domain('state', 'in', ('purchase', 'done')),
                Domain('product_id', 'in', product_ids),
                analytic_domain,
            ])
            purchase_lines = self.env['purchase.order.line'].search(purchase_domain)
            for purchase_line in purchase_lines:
                distribution = purchase_line.analytic_distribution or {}
                distribution_ids = set()
                for key in distribution:
                    distribution_ids.update(
                        int(part) for part in str(key).split(',') if part.isdigit()
                    )
                for analytic_id in analytic_ids.intersection(distribution_ids):
                    key = (analytic_id, purchase_line.product_id.id)
                    qty, amount = purchase_lines_by_key.get(key, (0.0, 0.0))
                    purchase_lines_by_key[key] = (
                        qty + (purchase_line.qty_invoiced or 0.0),
                        amount + ((purchase_line.qty_invoiced or 0.0) * (purchase_line.price_unit or 0.0)),
                    )

        for rec in self:
            if rec.line_type in ('material', 'overhead'):
                rec.quantity_billed, rec.amount_billed = purchase_lines_by_key.get(
                    (rec.account_analytic_id.id, rec.product_id.id), (0.0, 0.0)
                )
                rec.qty_to_invoice = (rec.quantity_billed - rec.quantity_invoiced) or 0.0
                rec.amount_to_invoice = (rec.amount_billed - rec.amount_invoiced) or 0.0

            elif rec.line_type == 'labour':
                if rec.project_task_id:
                    if rec.project_task_id.allocated_hours != rec.planned_hours:
                        rec.project_task_id.allocated_hours = rec.planned_hours
                    rec.quantity_billed = rec.project_task_id.effective_hours
                    rec.remaining_hours = rec.planned_hours - rec.quantity_billed
                else:
                    rec.quantity_billed = rec.remaining_hours = 0

                if rec.quantity_billed > 0 and rec.quantity_invoiced > 0:
                    rec.qty_to_invoice = rec.quantity_billed - rec.quantity_invoiced
                    rec.amount_to_invoice = rec.qty_to_invoice * rec.price_unit
                elif rec.quantity_billed > 0 and rec.quantity_invoiced == 0:
                    rec.qty_to_invoice = rec.quantity_billed
                    rec.amount_to_invoice = rec.quantity_billed * rec.price_unit
                else:
                    rec.qty_to_invoice = rec.amount_to_invoice = 0

            elif rec.line_type == 'subcontract':
                if rec.sale_subcontract_id:
                    rec.quantity_billed = rec.product_qty
                    rec.amount_billed = rec.sale_subcontract_id.amount_invoiced
                else:
                    rec.quantity_billed = rec.amount_billed = 0

                rec.amount_to_invoice = (rec.amount_billed - rec.amount_invoiced) or 0.0
                rec.qty_to_invoice = 1 if rec.amount_to_invoice > 0 else 0

    @api.depends('contract_id', 'product_id')
    def _compute_name(self):
        for line in self:
            if not (line.product_id or line.contract_id):
                continue

            name = line.contract_id.internal_reference + ' - ' + line.product_id.name
            line.name = name
