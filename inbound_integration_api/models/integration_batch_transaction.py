# -*- coding: utf-8 -*-

from odoo import fields, models


class IntegrationBatchTransaction(models.Model):
    _name = "integration.batch.transaction"
    _description = "Inbound Integration Batch Transaction"
    _order = "id"

    batch_closing_id = fields.Many2one(
        "integration.batch.closing",
        string="Batch Closing",
        required=True,
        ondelete="cascade",
        index=True,
    )
    amount = fields.Monetary(string="Amount", required=True)
    method = fields.Char(string="Payment Method")
    image = fields.Binary(string="Payment Proof", attachment=True)
    currency_id = fields.Many2one(
        related="batch_closing_id.currency_id",
        store=True,
        readonly=True,
    )
