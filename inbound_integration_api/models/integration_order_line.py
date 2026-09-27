# -*- coding: utf-8 -*-

from odoo import api, fields, models


class IntegrationOrderLine(models.Model):
    _name = "integration.order.line"
    _description = "Inbound Integration Order Line"
    _order = "id"

    order_id = fields.Many2one(
        "integration.order",
        string="Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
    )
    product_name = fields.Char(
        string="Product Name (External)",
        help="Product name as received from the external system.",
    )
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    returned_quantity = fields.Float(string="Returned Quantity", default=0.0)
    currency_id = fields.Many2one(
        related="order_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self.product_name:
            self.product_name = self.product_id.display_name
