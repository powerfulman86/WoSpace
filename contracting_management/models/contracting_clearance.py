# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractingClearance(models.Model):
    _name = 'contracting.clearance'
    _description = 'Sale Contracting Clearance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'internal_reference'
    _check_company_auto = True

    @api.depends('order_line.amount_to_invoice')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            actual_amount = amount_total = 0.0
            for line in order.order_line:
                amount_total += line.amount_to_invoice
                actual_amount += line.amount_actual

            order.update({'clearance_total_amount': amount_total, 'clearance_actual_amount': actual_amount})

    internal_reference = fields.Char(string='Clearance Reference', copy=False, readonly=True, index=True,
                                     default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Locked'),
        ('invoiced', 'Invoiced'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string='Created By')
    description = fields.Text(string='Description', )
    clearance_date = fields.Date(string="Date", required=True, default=fields.Date.today(), readonly=True)
    contract_id = fields.Many2one(comodel_name="contracting.order", string="Contract", required=False, readonly=True, check_company=True, index=True)
    partner_id = fields.Many2one(string='Customer', related="contract_id.partner_id", store=True)
    currency_id = fields.Many2one(string='Currency', related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(string='Company', related='contract_id.company_id', store=True)
    account_analytic_id = fields.Many2one(related='contract_id.account_analytic_id', string='Analytic Account',
                                          store=True)
    cost_expected = fields.Monetary(string="Expected Cost", default=0.00)

    retention_amount = fields.Monetary(string="Retention Amount", default=0.00)

    down_payment = fields.Monetary(string="Down Payment", default=0.00)
    amount_deduct_from_ap = fields.Monetary(string="To Be Consumed", default=0.00)
    amount_deduct_from_ap_min = fields.Monetary(string="Min.", store=True)
    amount_deduct_from_ap_remain = fields.Monetary(string="remain", readonly=True,
                                                   related='contract_id.remain_down_payment', store=True)
    amount_deduct_from_ap_after_current = fields.Monetary(string="After Current", readonly=True,
                                                          compute='_compute_remain_down_payment_after_current_payment',
                                                          store=True, help='Remaining advance-payment deduction after the current clearance: remaining advance deduction minus the deduction applied on this clearance.')

    amount_to_invoice = fields.Monetary(string="To-Invoice Amount", default=0.00, readonly=True, )
    amount_to_invoice_expected = fields.Monetary(string="To-Invoice Amount Expected", default=0.00, readonly=True, )
    amount_to_invoice_actual = fields.Monetary(string="To-Invoice Amount Actual", default=0.00, readonly=True)

    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=4, help='Computed from the clearance lines by the clearance total calculation.')
    order_line = fields.One2many(comodel_name="contracting.clearance.line", inverse_name="clearance_id", string="Lines",
                                 required=False)
    sale_order = fields.Many2one("sale.order", string="Payment Order", readonly=True, tracking=True,
                                 copy=False, )
    invoice_status = fields.Selection(
        related='sale_order.invoice_status',
        string='Invoice Status',
        store=True,
    )
    clearance_total_amount = fields.Monetary(string="Total Amount", default=0.00, readonly=True, store=True,
                                             compute='_amount_all', help='Sum of Amount To Invoice across all clearance lines.')
    clearance_actual_amount = fields.Monetary(string="Actual Amount", default=0.00, readonly=True, store=True,
                                              compute='_amount_all', help='Sum of Actual Amount across all clearance lines.')

    @api.onchange('amount_to_invoice_actual')
    def calculate_clearance_retention(self):
        for rec in self:
            rec.retention_amount = rec.amount_to_invoice_actual * (rec.contract_id.retention_rate / 100)
            rec.amount_deduct_from_ap = rec.amount_to_invoice_actual * (rec.contract_id.advance_payment_rate / 100)
            rec.amount_deduct_from_ap_min = rec.amount_to_invoice_actual * (rec.contract_id.advance_payment_rate / 100)

    @api.depends('amount_deduct_from_ap_remain', 'amount_deduct_from_ap')
    def _compute_remain_down_payment_after_current_payment(self):
        for rec in self:
            rec.amount_deduct_from_ap_after_current = rec.amount_deduct_from_ap_remain - rec.amount_deduct_from_ap

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get('internal_reference', _('New')) == _('New'):
                vals['internal_reference'] = self.env['ir.sequence'].next_by_code('contracting.clearance') or _('New')
        records = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            records.mapped('contract_id')._refresh_statistics_now()
        return records

    def write(self, vals):
        relevant = {
            'state', 'contract_id', 'amount_deduct_from_ap', 'retention_amount',
            'amount_to_invoice_actual', 'amount_to_invoice', 'order_line',
        }
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self.mapped('contract_id') if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self.mapped('contract_id'))._refresh_statistics_now()
        return result

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete Contract Clearance which is not draft'))
        contracts = self.mapped('contract_id')
        result = super(ContractingClearance, self).unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result

    @api.constrains("amount_deduct_from_ap")
    def _constrains_amount_deduct_from_ap(self):
        for rec in self:
            if rec.amount_deduct_from_ap > rec.amount_deduct_from_ap_remain:
                raise UserError(_('You can not Consume Down Payment More Than Remain In Contract'))

    @api.constrains("amount_to_invoice_actual")
    def _constrains_amount_to_invoice_actual(self):
        for rec in self:
            if rec.amount_to_invoice_actual <= 0:
                raise UserError(_('Payment Amount Must Be Greater Than 0'))

    def action_done(self):
        self.ensure_one()
        self.check_advance_payment()
        self.check_invoice_availability()
        # self.check_clearance_clearance_status()
        self.write({'state': 'done'})

    def action_cancel(self):
        self.ensure_one()
        if self.sale_order:
            if self.sale_order.state == 'cancel':
                self._reverse_invoicing()
        self.write({'state': 'cancel'})

    def action_cancel_invoiced(self):
        self.ensure_one()
        if self.sale_order:
            order_valid_invoices = self.sale_order.invoice_ids.filtered(lambda so: so.state != 'cancel')
            if self.sale_order.state == 'cancel' and len(order_valid_invoices) == 0:
                self._reverse_invoicing()
                self.write({'state': 'cancel'})
            else:
                raise UserError(_('Sales Order and related invoice Must Be Canceled First !'))
        else:
            self.write({'state': 'cancel'})

    def button_unlock(self):
        # we need to be able to cancel clearance
        # but make sure invoice cancelled first
        self.ensure_one()
        self.write({'state': 'done'})

    def _reverse_invoicing(self):
        self.contract_id.write({
            'consumed_down_payment': self.contract_id.consumed_down_payment - self.amount_deduct_from_ap
        })

    def _apply_invoiced_after_payment(self):
        self.contract_id.write({
            'consumed_down_payment': self.contract_id.consumed_down_payment + self.amount_deduct_from_ap
        })

    def _prepare_contract_payment_order(self):
        if self.amount_to_invoice_actual > self.amount_to_invoice_expected:
            prepaid_amount = self.amount_to_invoice_actual - self.amount_to_invoice_expected
        else:
            prepaid_amount = 0

        amount_to_invoice_actual = self.amount_to_invoice_actual - prepaid_amount
        amount_deduct_from_ap = self.amount_deduct_from_ap
        retention_amount = self.retention_amount

        deposit_product = self.company_id.contracting_prepaid_product_id

        prepaid_product = self.company_id.contracting_prepaid_product_id
        retention_product = self.company_id.contracting_retention_product_id
        template_product = self.contract_id.template_id.product_id

        if not deposit_product:
            raise ValidationError(_("Down Payment Product Must Be Defined In Order To Create Down Payment Order"))

        if not prepaid_product:
            raise ValidationError(_("Prepaid Product Must Be Defined In Order To Create Contract Payment Order"))

        if not retention_product:
            raise ValidationError(_("Retention Product Must Be Defined In Order To Create Contract Payment Order"))

        if not template_product:
            raise ValidationError(_("Please Define Contract Template Service product ."))

        res = dict()
        for rec in self:
            order_lines = []

            fpos_id = self.env['account.fiscal.position'].with_company(rec.company_id
                                                                       )._get_fiscal_position(rec.partner_id)

            # deposit product
            order_lines.append((0, 0, {
                'product_id': deposit_product.id,
                'name': deposit_product.name,
                'product_uom_id': deposit_product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': - amount_deduct_from_ap,
                'is_analytic': False,
            }))

            # retention amount
            order_lines.append((0, 0, {
                'product_id': retention_product.id,
                'name': retention_product.name,
                'product_uom_id': retention_product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': - retention_amount,
                'is_analytic': False,
            }))

            # template product
            order_lines.append((0, 0, {
                'product_id': template_product.id,
                'name': template_product.name,
                'product_uom_id': template_product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': amount_to_invoice_actual,
                'analytic_distribution': {str(rec.account_analytic_id.id): 100.0},
            }))

            # prepaid amount
            order_lines.append((0, 0, {
                'product_id': prepaid_product.id,
                'name': prepaid_product.name,
                'product_uom_id': prepaid_product.uom_id.id,
                'product_uom_qty': 1,
                'price_unit': prepaid_amount,
                'is_analytic': False,
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
                'fiscal_position_id': fpos_id,
                'user_id': rec.user_id.id,
                'company_id': rec.company_id.id,
            }

        return res

    def check_invoice_availability(self):
        # 1st limit amount to invoice to available remain amount
        contract_remain_payment = self.contract_id.contract_total_amount - self.contract_id.current_income
        if self.amount_to_invoice_actual > contract_remain_payment:
            raise UserError(_("Contract only eligible to invoice %s , Can't Proceed") % contract_remain_payment)

        # 2nd check if after invoice will be available amount in advance payment and contract still have amount
        # not very obvious condition , lets check later

        # 3rd never accept loss
        loss_amount = self.amount_to_invoice_actual - contract_remain_payment
        if loss_amount > 0:
            raise UserError(_("Contract To Invoice Amount Will Exceed Project Income , Can't Proceed"))

        remain_after_current_payment = self.contract_id.contract_total_amount - (
                self.contract_id.current_income + self.amount_to_invoice_actual)
        if remain_after_current_payment < self.amount_deduct_from_ap_after_current:
            raise UserError(
                _("Contract Remain Amount After Current Payment Will Be Less Than Remain Down Payment,\n Please Consume All Remain Down Payment"))

    def check_advance_payment(self):
        # 1st check if advance payment deduct less than min or bigger than max
        total_remain_deduct_ap = self.amount_deduct_from_ap_min + self.amount_deduct_from_ap_remain
        if not (self.amount_deduct_from_ap_min <= self.amount_deduct_from_ap <= total_remain_deduct_ap):
            raise UserError(_("Amount Deduct From advance payment not in range of amount , Can't Proceed"))

    def prepare_contract_payment_order(self):
        self.ensure_one()
        values = self._prepare_contract_payment_order()
        order = self.env['sale.order'].create(values[self.id])
        order.message_post(body=(
                _("This Sale order has been created from the Contract Clearance") + " <a href=# data-oe-model=contracting.clearance data-oe-id=%d>%s</a>" % (
            self.id, self.display_name)))
        order.order_line._compute_tax_id()
        order.action_confirm()
        self.sale_order = order.id
        self.write({'state': 'invoiced'})
        self._apply_invoiced_after_payment()
        self.contract_id.update_statistics()
        return order.id

    def check_clearance_clearance_status(self):
        # we need to calculate if project clearance will make income with value greater than contract amount
        # if so stop user from validating clearance

        for rec in self:
            contract_remain_payment = rec.contract_id.contract_total_amount - rec.contract_id.current_income
            if rec.amount_to_invoice_expected > contract_remain_payment:
                raise UserError(_('Clearance Amount exceeds Contract Total Amount , Please Review'))

    def action_created_order(self):
        self.ensure_one()
        return {
            'name': _('Sales Order'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'target': 'current',
            'res_id': self.sale_order.id,
        }


class ContractingClearanceLine(models.Model):
    _name = 'contracting.clearance.line'
    _description = 'Sale Contracting Clearance Line'
    _order = 'clearance_id, sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    clearance_id = fields.Many2one(comodel_name="contracting.clearance", string="Clearance", required=True,
                                   ondelete='cascade', index=True, copy=False)
    state = fields.Selection(string='Status', related='clearance_id.state', store=True)
    partner_id = fields.Many2one(string='Customer', related="clearance_id.partner_id", store=True)
    currency_id = fields.Many2one(string='Currency', related='clearance_id.currency_id', store=True)
    company_id = fields.Many2one(string='Company', related='clearance_id.company_id', store=True)
    contract_line_id = fields.Many2one(comodel_name="contracting.order.line", string="Contract line", required=False, index=True)
    line_type = fields.Selection(related='contract_line_id.line_type', string="Type", store=True)
    product_id = fields.Many2one(related='contract_line_id.product_id', string='Product', store=True)
    uom_id = fields.Many2one(related='contract_line_id.uom_id', string='Uom', store=True)
    price_unit = fields.Float('To Invoice', required=True, digits='Product Price', default=0.0)

    qty_to_invoice = fields.Float(string='To Invoice Quantity', store=True, readonly=True,
                                  digits='Product Unit of Measure', default=0.0)
    amount_to_invoice = fields.Monetary(string='To-Invoice Amount', readonly=True, store=True, default=0.0)
    amount_actual = fields.Monetary(string='Actual Amount', default=0.0)

    def _related_contracts(self):
        return self.mapped('clearance_id.contract_id')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_contract_statistics_refresh'):
            lines._related_contracts()._refresh_statistics_now()
        return lines

    def write(self, vals):
        relevant = {'clearance_id', 'contract_line_id', 'qty_to_invoice', 'amount_to_invoice', 'amount_actual'}
        should_refresh = bool(relevant.intersection(vals))
        contracts_before = self._related_contracts() if should_refresh else self.env['contracting.order']
        result = super().write(vals)
        if should_refresh and not self.env.context.get('skip_contract_statistics_refresh'):
            (contracts_before | self._related_contracts())._refresh_statistics_now()
        return result

    def unlink(self):
        contracts = self._related_contracts()
        result = super().unlink()
        if not self.env.context.get('skip_contract_statistics_refresh'):
            contracts._refresh_statistics_now()
        return result
