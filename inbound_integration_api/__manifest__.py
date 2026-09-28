# -*- coding: utf-8 -*-
{
    "name": "Inbound Integration API",
    "version": "18.0.1.1.0",
    "category": "Productivity",
    "summary": "Inbound Order Details and Batch Closing API for external courier integrations",
    "description": """
Inbound Integration API
=======================

Standalone application that exposes authenticated POST endpoints for:

* Order Details — create/update integration orders by external OID
* Batch Closing — create/update batch settlements by external batch_id

Authentication (Bearer token or API key) is configured under
Inbound Integration > Configuration > Settings.
    """,
    "depends": [
        "base_setup",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/integration_order_views.xml",
        "views/integration_company_views.xml",
        "views/integration_batch_closing_views.xml",
        "views/integration_fee_request_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "installable": True,
}
