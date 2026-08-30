{
    'name': "Account Enhancements",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,
    'author': "CubitIt",
    'summary': 'Invoices & Payments',
    'version': '0.1',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'images': ['static/description/icon.png'],
}
