# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class IntegrationBatchClosing(models.Model):
    _name = "integration.batch.closing"
    _description = "Inbound Integration Batch Closing"
    _order = "id desc"
    _rec_name = "batch_id"

    batch_id = fields.Char(
        string="Batch ID",
        required=True,
        index=True,
        copy=False,
        help="External batch identifier. Unique; repeated requests update this record.",
    )
    courier_name = fields.Char(string="Courier Name")
    courier_batch_number = fields.Char(string="Courier Batch Number", index=True)
    status = fields.Char(string="Status", index=True)
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
    ended_by = fields.Char(string="Ended By")

    # Order summary
    total_orders = fields.Integer(string="Total Orders")
    delivered_collected = fields.Integer(string="Delivered / Collected")
    to_be_reshipped = fields.Integer(string="To Be Reshipped")
    amount_to_be_collected = fields.Monetary(string="Amount To Be Collected")

    # Financial
    base_commission = fields.Monetary(string="Base Commission")
    additional = fields.Monetary(string="Additional")
    bonus = fields.Monetary(string="Bonus")
    net_due = fields.Monetary(string="Net Due")
    total_received = fields.Monetary(string="Total Received")

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    transaction_ids = fields.One2many(
        "integration.batch.transaction",
        "batch_closing_id",
        string="Transactions",
        copy=True,
    )

    _sql_constraints = [
        (
            "batch_id_uniq",
            "unique(batch_id)",
            "A batch closing with this Batch ID already exists.",
        ),
    ]

    @api.depends("batch_id", "courier_name", "courier_batch_number")
    def _compute_display_name(self):
        for batch in self:
            parts = []
            if batch.batch_id:
                parts.append(_("Batch %s") % batch.batch_id)
            if batch.courier_batch_number:
                parts.append("#%s" % batch.courier_batch_number)
            if batch.courier_name:
                parts.append(batch.courier_name)
            batch.display_name = " - ".join(parts) if parts else _("New Batch Closing")

    @api.model
    def _parse_datetime(self, value):
        if not value:
            return False
        if isinstance(value, str):
            value = value.replace("Z", "").replace("T", " ")
            return fields.Datetime.to_datetime(value)
        return value

    @api.model
    def _prepare_image_value(self, image):
        """Accept base64 string or null; ignore empty values."""
        if image in (None, False, ""):
            return False
        if isinstance(image, str):
            if "," in image and image.startswith("data:"):
                image = image.split(",", 1)[1]
            return image
        return image

    @api.model
    def upsert_from_payload(self, payload):
        """
        Create or update a batch closing from an inbound Batch Closing payload.

        Returns:
            tuple(record, action) where action is 'created' or 'updated'
        """
        batch_id = payload.get("batch_id")
        if batch_id is None or batch_id == "":
            raise ValueError(_("batch_id is required."))

        batch_id = str(batch_id).strip()
        order_summary = payload.get("order_summary") or {}
        financial = payload.get("financial") or {}
        transactions = payload.get("transactions") or []

        if not isinstance(order_summary, dict):
            raise ValueError(_("order_summary must be an object."))
        if not isinstance(financial, dict):
            raise ValueError(_("financial must be an object."))
        if not isinstance(transactions, list):
            raise ValueError(_("transactions must be a list."))

        transaction_commands = [(5, 0, 0)]
        for item in transactions:
            if not isinstance(item, dict):
                raise ValueError(_("Each transaction must be an object."))
            transaction_commands.append(
                (
                    0,
                    0,
                    {
                        "amount": item.get("amount") or 0.0,
                        "method": item.get("method"),
                        "image": self._prepare_image_value(item.get("image")),
                    },
                )
            )

        vals = {
            "batch_id": batch_id,
            "courier_name": payload.get("courier_name"),
            "courier_batch_number": (
                str(payload.get("courier_batch_number"))
                if payload.get("courier_batch_number") is not None
                else False
            ),
            "status": payload.get("status"),
            "start_date": self._parse_datetime(payload.get("start_date")),
            "end_date": self._parse_datetime(payload.get("end_date")),
            "ended_by": payload.get("ended_by"),
            "total_orders": order_summary.get("total_orders") or 0,
            "delivered_collected": order_summary.get("delivered_collected") or 0,
            "to_be_reshipped": order_summary.get("to_be_reshipped") or 0,
            "amount_to_be_collected": order_summary.get("amount_to_be_collected") or 0.0,
            "base_commission": financial.get("base_commission") or 0.0,
            "additional": financial.get("additional") or 0.0,
            "bonus": financial.get("bonus") or 0.0,
            "net_due": financial.get("net_due") or 0.0,
            "total_received": financial.get("total_received") or 0.0,
            "transaction_ids": transaction_commands,
        }

        batch = self.sudo().search([("batch_id", "=", batch_id)], limit=1)
        if batch:
            batch.write(vals)
            return batch, "updated"
        batch = self.sudo().create(vals)
        return batch, "created"
