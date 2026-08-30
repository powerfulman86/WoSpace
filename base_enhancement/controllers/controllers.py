# from odoo import http


# class BaseEnhancement(http.Controller):
#     @http.route('/base_enhancement/base_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/base_enhancement/base_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('base_enhancement.listing', {
#             'root': '/base_enhancement/base_enhancement',
#             'objects': http.request.env['base_enhancement.base_enhancement'].search([]),
#         })

#     @http.route('/base_enhancement/base_enhancement/objects/<model("base_enhancement.base_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('base_enhancement.object', {
#             'object': obj
#         })

