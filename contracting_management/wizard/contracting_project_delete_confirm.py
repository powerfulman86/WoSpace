# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class ContractingProjectDeleteConfirm(models.TransientModel):
    _name = 'contracting.project.delete.confirm'
    _description = 'Confirm Contracting Project Deletion'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        readonly=True,
    )

    def action_confirm_delete(self):
        self.ensure_one()
        project = self.project_id.exists()
        if not project:
            return {'type': 'ir.actions.act_window_close'}

        contracts = self.env['contracting.order'].sudo().search([
            ('project_id', '=', project.id),
        ])
        if not contracts:
            raise UserError(_('This project is no longer linked to a Contracting Order.'))

        # Explicit confirmation is complete. Clear the existing contract link without
        # invoking its stage automation, otherwise the project would be recreated.
        contracts.with_context(skip_contracting_stage_automation=True).write({'project_id': False})
        project.with_context(confirm_contracting_project_delete=True).unlink()
        return {'type': 'ir.actions.act_window_close'}
