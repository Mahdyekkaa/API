# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IntegrationOrder(models.Model):
    _name = "integration.order"
    _description = "Inbound Integration Order"
    _order = "id desc"
    _rec_name = "oid"

    oid = fields.Char(
        string="OID",
        required=True,
        index=True,
        copy=False,
        help="External order identifier. Unique; repeated requests update this record.",
    )
    integration_company_id = fields.Many2one(
        "integration.company",
        string="Company Name",
        index=True,
        ondelete="restrict",
    )
    consignee_id = fields.Many2one(
        "res.partner",
        string="Consignee Name",
        index=True,
    )
    consignee_phone = fields.Char(string="Consignee Phone")
    governorate = fields.Char(string="Governorate")
    shipping_fees = fields.Monetary(string="Shipping Fees")
    settlement_amount = fields.Monetary(string="Settlement Amount")
    cod_collected = fields.Monetary(string="COD Collected")
    courier = fields.Char(string="Courier")
    order_type = fields.Char(string="Order Type")
    order_status = fields.Selection(
        [
            ("delivered", "Delivered"),
            ("returned", "Returned"),
            ("paid", "Paid"),
        ],
        string="Status",
        index=True,
    )
    delivery_outcome = fields.Selection(
        [
            ("delivered", "Delivered"),
            ("returned", "Returned"),
        ],
        string="Delivery Outcome",
        compute="_compute_delivery_outcome",
        store=True,
        readonly=False,
        index=True,
        help="Last delivered/returned status; kept after the order becomes Paid.",
    )
    fee_request_id = fields.Many2one(
        "integration.fee.request",
        string="Fee Request",
        index=True,
        ondelete="set null",
        copy=False,
    )
    num_products = fields.Float(
        string="Num Products",
        compute="_compute_amounts",
        store=True,
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        store=True,
    )
    total = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
    )
    batch_status = fields.Char(string="Batch Status")
    batch_number = fields.Char(string="Batch Number", index=True)
    batch_closing_id = fields.Many2one(
        "integration.batch.closing",
        string="Batch Closing",
        index=True,
        ondelete="set null",
        copy=False,
    )
    courier_expense = fields.Monetary(string="Courier Expense")
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
    date_created = fields.Datetime(string="Created At")
    date_picked_up = fields.Datetime(string="Picked Up At")
    date_delivered = fields.Datetime(string="Delivered At")
    line_ids = fields.One2many(
        "integration.order.line",
        "order_id",
        string="Order Lines",
        copy=True,
    )
    line_count = fields.Integer(compute="_compute_line_count")

    _sql_constraints = [
        ("oid_uniq", "unique(oid)", "An integration order with this OID already exists."),
    ]

    @api.depends("oid", "consignee_id")
    def _compute_display_name(self):
        for order in self:
            if order.oid and order.consignee_id:
                order.display_name = _("OID %s - %s") % (order.oid, order.consignee_id.name)
            elif order.oid:
                order.display_name = _("OID %s") % order.oid
            else:
                order.display_name = _("New Integration Order")

    @api.depends("order_status")
    def _compute_delivery_outcome(self):
        for order in self:
            if order.order_status in ("delivered", "returned"):
                order.delivery_outcome = order.order_status

    @api.depends("line_ids.quantity", "cod_collected", "shipping_fees")
    def _compute_amounts(self):
        for order in self:
            order.num_products = sum(order.line_ids.mapped("quantity"))
            order.subtotal = order.cod_collected
            order.total = order.cod_collected - order.shipping_fees

    @api.constrains("fee_request_id", "delivery_outcome")
    def _check_fee_request_outcome(self):
        invalid = self.filtered(lambda o: o.fee_request_id and not o.delivery_outcome)
        if invalid:
            raise ValidationError(
                _("Only delivered or returned orders can be added to a fee request: %s")
                % ", ".join(invalid.mapped("oid"))
            )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for order in self:
            order.line_count = len(order.line_ids)

    @api.model
    def _parse_datetime(self, value):
        """Parse ISO-8601 datetime strings into Odoo Datetime values."""
        if not value:
            return False
        if isinstance(value, str):
            value = value.replace("Z", "").replace("T", " ")
            return fields.Datetime.to_datetime(value)
        return value

    @api.model
    def _find_product_by_name(self, product_name):
        """Match a standard product by name or internal reference."""
        Product = self.env["product.product"].sudo()
        name = (product_name or "").strip()
        if not name:
            return Product
        product = Product.search(
            ["|", ("name", "=", name), ("default_code", "=", name)],
            limit=1,
        )
        if product:
            return product
        return Product.search(
            ["|", ("name", "ilike", name), ("default_code", "ilike", name)],
            limit=1,
        )

    @api.model
    def _find_or_create_product_by_name(self, product_name):
        """Return a matching product, creating a consumable one if missing."""
        name = (product_name or "").strip()
        if not name:
            raise ValueError(_("product_name is required for each product line."))
        product = self._find_product_by_name(name)
        if product:
            return product
        return self.env["product.product"].sudo().create(
            {
                "name": name,
                "type": "consu",
            }
        )

    @api.model
    def _parse_order_status(self, value):
        """Map an inbound status (case-insensitive) to a selection key."""
        if value in (None, False, ""):
            return False
        status = str(value).strip().lower()
        allowed = dict(self._fields["order_status"].selection)
        if status not in allowed:
            raise ValueError(
                _("Invalid order_status '%(value)s'. Allowed values: %(allowed)s.")
                % {"value": value, "allowed": ", ".join(allowed.values())}
            )
        return status

    @api.model
    def _find_or_create_consignee(self, name, phone):
        """Return the consignee partner matching name (and phone), creating it if missing."""
        Partner = self.env["res.partner"].sudo()
        name = (name or "").strip()
        phone = (phone or "").strip()
        if not name:
            return Partner
        partners = Partner.search([("name", "=ilike", name)])
        partner = Partner
        if phone:
            partner = partners.filtered(lambda p: phone in (p.phone, p.mobile))[:1]
            if not partner:
                partner = partners.filtered(lambda p: not p.phone and not p.mobile)[:1]
                if partner:
                    partner.phone = phone
        else:
            partner = partners[:1]
        if partner:
            return partner
        return Partner.create({"name": name, "phone": phone or False})

    @api.model
    def _find_or_create_by_oid(self, oid):
        """Return the order matching oid, creating a delivered one if missing."""
        order = self.sudo().search([("oid", "=", oid)], limit=1)
        if order:
            return order
        return self.sudo().create({"oid": oid, "order_status": "delivered"})

    @api.model
    def upsert_from_payload(self, payload):
        """
        Create or update an integration order from an inbound Order Details payload.

        Returns:
            tuple(record, action) where action is 'created' or 'updated'
        """
        oid = payload.get("oid")
        if oid is None or oid == "":
            raise ValueError(_("OID is required."))

        oid = str(oid).strip()
        order_status = self._parse_order_status(payload.get("order_status"))
        status_dates = payload.get("status_dates") or {}
        products = payload.get("products") or []

        if not isinstance(products, list):
            raise ValueError(_("products must be a list."))

        line_commands = []
        for item in products:
            if not isinstance(item, dict):
                raise ValueError(_("Each product line must be an object."))
            product_name = item.get("product_name")
            product = self._find_or_create_product_by_name(product_name)
            line_commands.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_name": product_name,
                        "quantity": item.get("quantity") or 0,
                        "returned_quantity": item.get("returned_quantity") or 0,
                    },
                )
            )

        vals = {
            "oid": oid,
            "integration_company_id": self.env["integration.company"]
            ._find_or_create_by_name(payload.get("company_name"))
            .id,
            "consignee_id": self._find_or_create_consignee(
                payload.get("consignee_name"), payload.get("consignee_phone")
            ).id,
            "consignee_phone": payload.get("consignee_phone"),
            "governorate": payload.get("governorate"),
            "shipping_fees": payload.get("shipping_fees") or 0.0,
            "settlement_amount": payload.get("settlement_amount") or 0.0,
            "cod_collected": payload.get("cod_collected") or 0.0,
            "courier": payload.get("courier"),
            "order_type": payload.get("order_type"),
            "order_status": order_status,
            "batch_status": payload.get("batch_status"),
            "batch_number": (
                str(payload.get("batch_number"))
                if payload.get("batch_number") is not None
                else False
            ),
            "courier_expense": payload.get("courier_expense") or 0.0,
            "date_created": self._parse_datetime(status_dates.get("created")),
            "date_picked_up": self._parse_datetime(status_dates.get("picked_up")),
            "date_delivered": self._parse_datetime(status_dates.get("delivered")),
            "line_ids": [(5, 0, 0)] + line_commands,
        }
        vals["batch_closing_id"] = (
            self.env["integration.batch.closing"]
            ._find_by_courier_batch(vals["batch_number"], vals["courier"])
            .id
        )

        order = self.sudo().search([("oid", "=", oid)], limit=1)
        if order:
            order.write(vals)
            return order, "updated"
        order = self.sudo().create(vals)
        return order, "created"
