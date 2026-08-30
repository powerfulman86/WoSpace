# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Stock Card Report",
    "summary": "Add stock card report on Inventory Reporting.",
    "version": "19.0.1.0.0",
    "category": "Warehouse",
    "website": "https://github.com/OCA/stock-logistics-reporting",
    "author": "Ecosoft, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/stock_card_report.xml",
        "reports/stock_location_card_report.xml",
        "reports/stock_card_report_line_views.xml",
        "reports/stock_location_card_report_line_views.xml",
        "wizard/stock_card_report_wizard_view.xml",
        "wizard/stock_location_card_report_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_card_report/static/src/css/report.css",
            "stock_card_report/static/src/js/stock_card_report_backend.js",
        ],
    },
    "installable": True,
}
