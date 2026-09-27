# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    inbound_integration_api_enabled = fields.Boolean(
        string="Enable Inbound Integration API",
        config_parameter="inbound_integration_api.enabled",
        default=True,
    )
    inbound_integration_api_auth_token = fields.Char(
        string="API Auth Token",
        config_parameter="inbound_integration_api.auth_token",
        help=(
            "Shared secret used by the external system. "
            "Send it as Authorization: Bearer <token> or as an API-Key / X-API-Key header."
        ),
    )
    inbound_integration_api_require_auth = fields.Boolean(
        string="Require Authentication",
        config_parameter="inbound_integration_api.require_auth",
        default=True,
        help="When enabled, inbound endpoints reject requests without a valid token.",
    )
