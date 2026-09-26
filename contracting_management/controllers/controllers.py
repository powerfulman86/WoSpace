# -*- coding: utf-8 -*-
# from odoo import http


# class ContractingManagement(http.Controller):
#     @http.route('/contracting__management/contracting__management/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/contracting__management/contracting__management/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('contracting__management.listing', {
#             'root': '/contracting__management/contracting__management',
#             'objects': http.request.env['contracting__management.contracting__management'].search([]),
#         })

#     @http.route('/contracting__management/contracting__management/objects/<model("contracting__management.contracting__management"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('contracting__management.object', {
#             'object': obj
#         })
