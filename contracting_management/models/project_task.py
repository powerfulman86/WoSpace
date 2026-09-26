# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    supplier_id = fields.Many2one('res.partner', string='Subcontractor', required=False,
                                  change_default=True, tracking=True,
                                  domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]",
                                  help="You can find a vendor by its Name, TIN, Email or Internal Reference.")
    is_subcontractor_task = fields.Boolean(string='Subcontractor Task', copy=False, default=False, readonly=True, )

    purchase_ids = fields.One2many(comodel_name="purchase.order", inverse_name="task_id", string="SubContractor Purce",
                                   required=False, )
    purchase_count = fields.Integer(string='Purchase Count', compute='_compute_purchase_ids', help='Number of purchase orders linked to this project task.')

    @api.depends('purchase_ids')
    def _compute_purchase_ids(self):
        for rec in self:
            rec.purchase_count = len(rec.purchase_ids)

    def create_purchase_order(self):
        # 1st giask data from contract lines
        subcontract = self.env['contracting.order.line'].search([('project_task_id', '=', self.id), ])
        if not len(subcontract.ids):
            raise ValidationError(_("SubContract Task Must Be Defined In Project Subcontract"))

        if not self.supplier_id:
            raise ValidationError(_("Task SubContractor Must Be Defined In order to Proceed With Purchase"))

        # create sales order
        po = self.env['purchase.order'].create({
            'partner_id': self.supplier_id.id,
            'company_id': self.company_id.id,
            'task_id': self.id,
        })

        self.env['purchase.order.line'].create({
            'order_id': po.id,
            'name': subcontract.product_id.name,
            'product_id': subcontract.product_id.id,
            'product_qty': 1,
            'product_uom_id': subcontract.product_id.uom_po_id.id,
            'price_unit': subcontract.price_unit,
            'date_planned': fields.Datetime.now(),
            'analytic_distribution': {str(subcontract.account_analytic_id.id): 100},
        })

        message = _(
            "This Purchase Order has been created from the Project Task : <a href=# data-oe-model=project.task data-oe-id=%d>%s</a>") % (
                      self.id, self.name)
        po.message_post(body=message)
        po.button_confirm()
        subcontract.write({'supplier_id': self.supplier_id})

    def action_view_purchase_orders(self):
        self.ensure_one()
        # action = self.env.ref('sale.view_order_tree').read()[0]
        return {
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'domain': [('task_id', '=', self.id)],
        }
