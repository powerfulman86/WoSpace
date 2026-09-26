# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleContractingStage(models.Model):
    _name = 'contracting.order.stage'
    _description = 'Contracting Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    description = fields.Text(
        "Requirements", help="Enter here the internal requirements for this stage. It will appear "
                             "as a tooltip over the stage's name.", translate=True)
    sequence = fields.Integer(default=1)
    in_progress = fields.Boolean(string='In Progress', default=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)


class SaleContractingTemplate(models.Model):
    _name = "contracting.order.template"
    _description = "Contracting Template"
    _inherit = "mail.thread"
    _check_company_auto = True
    _rec_name = 'name'
    _rec_names_search = ['code', 'name']

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    code = fields.Char(required=True, size=3)
    description = fields.Text(translate=True, string="Terms and Conditions")
    contracting_count = fields.Integer(compute='_compute_contracting_count', help='Number of contracting orders using this contracting template.')
    color = fields.Integer()
    company_id = fields.Many2one(comodel_name='res.company',
                                 required=True, index=True,
                                 default=lambda self: self.env.company)
    template_sequence_id = fields.Many2one('ir.sequence', 'Template Sequence', copy=False, readonly=True)

    product_id = fields.Many2one('product.product', 'Service Product',
                                 domain="[('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                 check_company=True,
                                 help='Default product used for Sales Orders')
    template_lines = fields.One2many(comodel_name="contracting.order.template.line", inverse_name="template_id",
                                     string="Template Lines", required=False, )
    analytic_plan_id = fields.Many2one(comodel_name="account.analytic.plan", string="Analytic Plan", copy=False)

    _sql_constraints = [
        (
            'default_code_uniq',
            'unique(code, company_id)',
            'Internal Reference must be unique per company!',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            vals['template_sequence_id'] = self.env['ir.sequence'].create({
                'name': _('contract_template_Sequence_') + vals['name'],
                'prefix': vals['code'] + '/%(y)s/',
                'padding': 4,
                'use_date_range': True,
                'company_id': company_id,
            }).id
            vals['analytic_plan_id'] = self.env['account.analytic.plan'].create({
                'name': vals['name'],
            }).id
        return super().create(vals_list)

    def _compute_contracting_count(self):
        contracting_data = self.env['contracting.order']._read_group(
            domain=[('template_id', 'in', self.ids)],
            groupby=['template_id'],
            aggregates=['__count'],
        )
        mapped_data = {template.id: count for template, count in contracting_data}
        for template in self:
            template.contracting_count = mapped_data.get(template.id, 0)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f"{rec.code} - {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or ''


class SaleContractingTemplateLine(models.Model):
    _name = "contracting.order.template.line"
    _description = "Contracting Template Line"

    template_id = fields.Many2one('contracting.order.template', string='Template Reference', required=True,
                                  ondelete='cascade', index=True, copy=False)

    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(related='template_id.company_id', string='Company', store=True, readonly=True,
                                 index=True)
    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="['&',('sale_ok', '=', True),('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', required=True, check_company=True)
    description = fields.Char(string='Description', copy=False, )
    line_type = fields.Selection(selection=[('material', 'Material'),
                                            ('labour', 'Labour'),
                                            ('subcontract', 'Sub Contract'),
                                            ('overhead', 'Over-Head'),
                                            ], string="Type", required=True, default='labour')
