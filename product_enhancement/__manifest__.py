{
    'name': "Product Enhancements",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "CubitIt",
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['product'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/product_product_views.xml',
        'views/product_template_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'images': ['static/description/icon.png'],
}
