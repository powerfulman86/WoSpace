# from odoo import http


# class ProductEnhancement(http.Controller):
#     @http.route('/product_enhancement/product_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/product_enhancement/product_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('product_enhancement.listing', {
#             'root': '/product_enhancement/product_enhancement',
#             'objects': http.request.env['product_enhancement.product_enhancement'].search([]),
#         })

#     @http.route('/product_enhancement/product_enhancement/objects/<model("product_enhancement.product_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('product_enhancement.object', {
#             'object': obj
#         })

