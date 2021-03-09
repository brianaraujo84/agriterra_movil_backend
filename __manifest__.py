{ 'name': "agriterra_app_movil",

    'summary': """Aplicación móvil Agriterra""",

    'description': """
        Se crea el add on para extender funcionalidades de odoo para backend
    """,

    'author': "Anthony Araujo",
    'website': "https://wwww.retailsolutions-bo.com",
    'qweb': [],
    'category': 'Uncategorized',
    'version': '0.0.0.1',
    'depends': ['base','stock', 'mail'],
    # always loaded
    'data': [
        "security/res_groups.xml",
        "security/ir_rule.xml",
        "security/ir_model_access.xml",
        'security/ir.model.access.csv',
        "views/views.xml",
        'views/menu_items.xml',
        "data/parametricas.xml",
    ],
    # only loaded in demonstration mode
    'demo': [
        #'demo/demo.xml',
    ],
}
