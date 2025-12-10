# -*- coding: utf-8 -*-
{
    'name': "l10n_sv_dte",
    'summary': "Integración DTE El Salvador con Punto de Venta (POS)",
    'description': """
        Integración de facturación electrónica (DTE) de El Salvador con el módulo de Punto de Venta de Odoo.
        Permite generar documentos tributarios válidos desde el POS.
    """,
    'author': "ortiz",
    'website': "https://www.yourcompany.com",
    'category': 'Accounting/Localizations',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'sale',
        'point_of_sale',
        'stock_account',
        'pos_hr',
        'base_setup',
        'web_editor',
        'l10n_sv',
        'l10n_sv_dpto',
        'l10n_sv_munic',
    ],
    'data': [
        'views/account_move.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
          
            'l10n_pos_dte/static/src/js/PaymentScreen/payment_screen.js',
        ],
       
    },
    'images': ['static/description/icon.png'],
    'installable': True,
}