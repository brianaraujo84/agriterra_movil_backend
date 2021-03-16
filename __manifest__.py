{ 'name': "agriterra_app_movil",

    'summary': """Aplicación móvil Agriterra""",

    'description': """
        Se crea el add on para extender funcionalidades de odoo para backend
    """,

    'author': "Anthony Araujo",
    'website': "https://wwww.retailsolutions-bo.com",
    'category': 'Uncategorized',
    'version': '0.0.0.1',
    'depends': ['base','stock', 'mail','account'],
	'images': ['static/description/assets.gif'],
    # always loaded
    'data': [
        "security/res_groups.xml",
        "security/ir_rule.xml",
        "security/ir_model_access.xml",
        'security/ir.model.access.csv',
        'security/account_asset_security.xml',
        "views/views.xml",
        'views/menu_items.xml',
        "data/parametricas.xml",
		'views/partner_view.xml',
        'views/company_view.xml',
        'wizard/asset_depreciation_confirmation_wizard_views.xml',
        'wizard/asset_modify_views.xml',
        'views/account_asset_views.xml',
        'views/account_invoice_views.xml',
        'views/account_asset_templates.xml',
        'views/product_views.xml',
        # 'views/res_config_settings_views.xml',
        'report/account_asset_report_views.xml',
        'data/account_asset_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        #'demo/demo.xml',
    ],
    'qweb': [
        "static/src/xml/account_asset_template.xml",
    ],

}
