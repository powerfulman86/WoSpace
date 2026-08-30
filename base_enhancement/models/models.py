# from odoo import models, fields, api


# class base_enhancement(models.Model):
#     _name = 'base_enhancement.base_enhancement'
#     _description = 'base_enhancement.base_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

