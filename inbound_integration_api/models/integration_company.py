# -*- coding: utf-8 -*-

from odoo import api, fields, models


class IntegrationCompany(models.Model):
    _name = "integration.company"
    _description = "Inbound Integration Company"
    _order = "name"

    name = fields.Char(string="Company Name", required=True, index=True)
    active = fields.Boolean(default=True)
    order_ids = fields.One2many(
        "integration.order",
        "integration_company_id",
        string="Orders",
    )
    order_count = fields.Integer(compute="_compute_order_count")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "A company with this name already exists."),
    ]

    @api.depends("order_ids")
    def _compute_order_count(self):
        for company in self:
            company.order_count = len(company.order_ids)

    @api.model
    def _find_or_create_by_name(self, name):
        """Return the company matching name (case-insensitive), creating it if missing."""
        name = (name or "").strip()
        if not name:
            return self.browse()
        company = (
            self.sudo()
            .with_context(active_test=False)
            .search([("name", "=ilike", name)], limit=1)
        )
        if company:
            return company
        return self.sudo().create({"name": name})

    def action_view_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "inbound_integration_api.action_integration_order"
        )
        action["domain"] = [("integration_company_id", "=", self.id)]
        action["context"] = {"default_integration_company_id": self.id}
        return action
