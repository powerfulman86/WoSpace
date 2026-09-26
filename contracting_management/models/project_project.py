# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contracting_order_ids = fields.One2many(
        'contracting.order',
        'project_id',
        string='Contracting Orders',
        readonly=True,
        copy=False,
    )
    is_contracting_project = fields.Boolean(
        string='Contracting Project',
        default=False,
        copy=False,
        index=True,
        help='Enabled automatically for projects created by the Contracting module.',
    )

    def _get_linked_contracting_orders(self):
        return self.env['contracting.order'].sudo().search([
            ('project_id', 'in', self.ids),
        ])

    def action_confirm_contracting_delete(self):
        self.ensure_one()
        if not self._get_linked_contracting_orders():
            return self.unlink()
        return {
            'name': _('Confirm Project Deletion'),
            'type': 'ir.actions.act_window',
            'res_model': 'contracting.project.delete.confirm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
            },
        }

    def unlink(self):
        if not self.env.context.get('confirm_contracting_project_delete'):
            linked_orders = self._get_linked_contracting_orders()
            if linked_orders:
                linked_project_ids = set(linked_orders.mapped('project_id').ids)
                names = ', '.join(self.filtered(lambda project: project.id in linked_project_ids).mapped('name'))
                raise UserError(_(
                    'The project(s) %s are linked to Contracting Orders and cannot be deleted directly. '
                    'Open the project and use "Delete Contracting Project" to confirm deletion.'
                ) % names)
        return super().unlink()
