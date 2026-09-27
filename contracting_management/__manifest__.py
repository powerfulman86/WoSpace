# -*- coding: utf-8 -*-
{
    'name': "Contracting Management",

    'summary': """
        Contracting Management Custom Module """,

    'description': """
        Contracting Management Custom Module
    """,

    'author': "CubicIt",
    'category': 'Projects',
    'version': '18.0.1.0.12',
    'license': 'AGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['base',
                'portal',
                'sale',
                'purchase',
                'stock',
                'project',
                'account',
                'hr_timesheet',
                'purchase_enhancement',
                'sale_enhancement',],

    # always loaded
    'data': [
        'security/res_groups.xml',
        'security/ir_rules.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/data.xml',
        'views/menu_contract_management.xml',
        'views/customers_view.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/contracting_down_payment_order.xml',
        'wizard/contracting_payment_order.xml',
        'wizard/contracting_project_delete_confirm.xml',
        'views/contracting_order_view.xml',
        'views/contracting_order_template.xml',
        'views/contracting_order_sub_view.xml',
        'views/project_task_view.xml',
        'views/contracting_variation_views.xml',
        'views/contracting_clearance_view.xml',
        'report/contracting_order_report.xml',
        'report/subcontracting_report.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
