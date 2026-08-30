# from odoo import models, fields, api


# class sale_enhancement(models.Model):
#     _name = 'sale_enhancement.sale_enhancement'
#     _description = 'sale_enhancement.sale_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

