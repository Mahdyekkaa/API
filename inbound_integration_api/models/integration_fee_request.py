# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class IntegrationFeeRequest(models.Model):
    _name = "integration.fee.request"
    _description = "Inbound Integration Fee Request"
    _order = "id desc"
    _rec_name = "request_id"

    request_id = fields.Char(
        string="Request ID",
        required=True,
        index=True,
        copy=False,
        help="External request identifier. Unique; repeated requests update this record.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("paid", "Paid"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
        copy=False,
    )
    order_ids = fields.One2many(
        "integration.order",
        "fee_request_id",
        string="Orders",
    )
    order_count = fields.Integer(compute="_compute_order_count")
    delivered_amount = fields.Monetary(
        string="Delivered Orders Amount",
        compute="_compute_amounts",
        store=True,
    )
    returned_fees = fields.Monetary(
        string="Returned Orders Fees",
        compute="_compute_amounts",
        store=True,
    )
    requested_amount = fields.Monetary(string="Requested Amount")
    amount_to_transfer = fields.Monetary(
        string="Amount to Transfer",
        compute="_compute_amounts",
        store=True,
    )
    amount_mismatch = fields.Boolean(compute="_compute_amount_mismatch")
    request_date = fields.Datetime(
        string="Request Date",
        default=fields.Datetime.now,
    )
    payment_date = fields.Datetime(string="Payment Date", copy=False)
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

    _sql_constraints = [
        (
            "request_id_uniq",
            "unique(request_id)",
            "A fee request with this Request ID already exists.",
        ),
    ]

    @api.depends("order_ids")
    def _compute_order_count(self):
        for request in self:
            request.order_count = len(request.order_ids)

    @api.depends(
        "order_ids.delivery_outcome",
        "order_ids.total",
        "order_ids.shipping_fees",
    )
    def _compute_amounts(self):
        for request in self:
            delivered = request.order_ids.filtered(
                lambda o: o.delivery_outcome == "delivered"
            )
            returned = request.order_ids.filtered(
                lambda o: o.delivery_outcome == "returned"
            )
            request.delivered_amount = sum(delivered.mapped("total"))
            request.returned_fees = sum(returned.mapped("shipping_fees"))
            request.amount_to_transfer = (
                request.delivered_amount - request.returned_fees
            )

    @api.depends("requested_amount", "amount_to_transfer", "currency_id")
    def _compute_amount_mismatch(self):
        for request in self:
            request.amount_mismatch = bool(request.requested_amount) and (
                float_compare(
                    request.requested_amount,
                    request.amount_to_transfer,
                    precision_rounding=request.currency_id.rounding,
                )
                != 0
            )

    def action_request(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft fee requests can be requested."))
            if not request.order_ids:
                raise UserError(_("Add at least one order before requesting."))
        self.write({"state": "requested"})

    def action_mark_paid(self):
        for request in self:
            if request.state != "requested":
                raise UserError(_("Only requested fee requests can be marked as paid."))
        for request in self:
            request.order_ids.write({"order_status": "paid"})
            request.write(
                {
                    "state": "paid",
                    "payment_date": request.payment_date or fields.Datetime.now(),
                }
            )

    def action_reset_to_draft(self):
        for request in self:
            if request.state != "requested":
                raise UserError(_("Only requested fee requests can be reset to draft."))
        self.write({"state": "draft"})

    def action_view_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "inbound_integration_api.action_integration_order"
        )
        action["domain"] = [("fee_request_id", "=", self.id)]
        action["context"] = {"create": False}
        return action

    @api.model
    def _parse_datetime(self, value):
        if not value:
            return False
        if isinstance(value, str):
            value = value.replace("Z", "").replace("T", " ")
            return fields.Datetime.to_datetime(value)
        return value

    @api.model
    def upsert_from_payload(self, payload):
        """
        Create or update a fee request from an inbound Fee Request payload.

        Returns:
            tuple(record, action) where action is 'created' or 'updated'
        """
        request_id = payload.get("request_id")
        if request_id is None or request_id == "":
            raise ValueError(_("request_id is required."))
        request_id = str(request_id).strip()

        items = payload.get("oids") or []
        if not isinstance(items, list):
            raise ValueError(_("oids must be a list."))
        items = [item for item in items if item not in (None, "")]
        if not items:
            raise ValueError(_("oids must contain at least one order."))

        fee_request = self.sudo().search([("request_id", "=", request_id)], limit=1)
        if fee_request.state == "paid":
            raise ValueError(_("Fee request %s is already paid.") % request_id)

        # Savepoint: orders created below must not persist if validation fails,
        # since the controller turns errors into responses instead of re-raising.
        with self.env.cr.savepoint():
            return self._upsert_fee_request(fee_request, request_id, items, payload)

    @api.model
    def _upsert_fee_request(self, fee_request, request_id, items, payload):
        Order = self.env["integration.order"].sudo()
        orders = Order.browse()
        for item in items:
            if isinstance(item, dict):
                order, _action = Order.upsert_from_payload(item)
            else:
                order = Order._find_or_create_by_oid(str(item).strip())
            orders |= order

        not_eligible = orders.filtered(lambda o: not o.delivery_outcome)
        if not_eligible:
            raise ValueError(
                _("Orders must be delivered or returned: %s")
                % ", ".join(not_eligible.mapped("oid"))
            )

        taken = orders.filtered(
            lambda o: o.fee_request_id and o.fee_request_id != fee_request
        )
        if taken:
            raise ValueError(
                _("Orders already belong to another fee request: %s")
                % ", ".join(taken.mapped("oid"))
            )

        vals = {
            "request_id": request_id,
            "requested_amount": payload.get("requested_amount") or 0.0,
            "request_date": (
                self._parse_datetime(payload.get("request_date"))
                or fields.Datetime.now()
            ),
            "state": "requested",
            "order_ids": [(6, 0, orders.ids)],
        }

        if fee_request:
            fee_request.write(vals)
            return fee_request, "updated"
        fee_request = self.sudo().create(vals)
        return fee_request, "created"
