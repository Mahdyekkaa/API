# -*- coding: utf-8 -*-

import json
import logging

from odoo import _, http
from odoo.http import request
from odoo.tools import consteq
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)


class InboundIntegrationController(http.Controller):
    """Inbound Order Details and Batch Closing endpoints."""

    def _json_response(self, payload, status=200):
        return Response(
            status=status,
            content_type="application/json; charset=utf-8",
            response=json.dumps(payload),
        )

    def _success_response(self, record, action, external_id):
        status = 201 if action == "created" else 200
        return self._json_response(
            {
                "success": True,
                "external_id": str(external_id),
                "odoo_record_id": record.id,
                "action": action,
            },
            status=status,
        )

    def _error_response(self, message, status=400, **extra):
        body = {
            "success": False,
            "error": message,
        }
        body.update(extra)
        return self._json_response(body, status=status)

    def _get_config(self):
        ICP = request.env["ir.config_parameter"].sudo()
        return {
            "enabled": ICP.get_param("inbound_integration_api.enabled", "True")
            not in ("False", "0", "false"),
            "require_auth": ICP.get_param(
                "inbound_integration_api.require_auth", "True"
            )
            not in ("False", "0", "false"),
            "auth_token": (
                ICP.get_param("inbound_integration_api.auth_token") or ""
            ).strip(),
        }

    def _extract_token(self):
        headers = request.httprequest.headers
        auth = headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        for header_name in ("API-Key", "X-API-Key", "Api-Key", "api-key"):
            value = headers.get(header_name)
            if value:
                return value.strip()
        environ = request.httprequest.environ
        for env_key in ("HTTP_API_KEY", "HTTP_TOKEN", "HTTP_X_API_KEY"):
            value = environ.get(env_key)
            if value:
                if str(value).lower().startswith("bearer "):
                    return str(value)[7:].strip()
                return str(value).strip()
        return ""

    def _authenticate(self):
        """
        Validate the inbound request against Settings > Inbound Integration API.

        Returns None on success, or an error Response on failure.
        """
        config = self._get_config()
        if not config["enabled"]:
            return self._error_response(
                _("Inbound Integration API is disabled."),
                status=403,
            )
        if not config["require_auth"]:
            return None
        if not config["auth_token"]:
            _logger.error("Inbound API auth is required but no token is configured.")
            return self._error_response(
                _("Authentication is not configured on the server."),
                status=401,
            )
        provided = self._extract_token()
        if not provided or not consteq(provided, config["auth_token"]):
            return self._error_response(
                _("Authentication failed or missing."),
                status=401,
            )
        return None

    def _parse_json_body(self):
        try:
            data = request.get_json_data()
        except Exception:
            raw = request.httprequest.get_data(as_text=True) or ""
            if not raw.strip():
                return None, self._error_response(
                    _("Request body is required."),
                    status=400,
                )
            try:
                data = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None, self._error_response(
                    _("Invalid JSON payload."),
                    status=400,
                )
        if data is None:
            return None, self._error_response(
                _("Request body is required."),
                status=400,
            )
        if not isinstance(data, dict):
            return None, self._error_response(
                _("JSON payload must be an object."),
                status=400,
            )
        return data, None

    @http.route(
        "/api/integration/order-details",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def order_details(self, **kwargs):
        auth_error = self._authenticate()
        if auth_error:
            return auth_error

        payload, parse_error = self._parse_json_body()
        if parse_error:
            return parse_error

        if payload.get("oid") in (None, ""):
            return self._error_response(_("OID is required."), status=400)

        try:
            order, action = (
                request.env["integration.order"].sudo().upsert_from_payload(payload)
            )
        except LookupError as err:
            return self._error_response(str(err), status=404)
        except ValueError as err:
            return self._error_response(str(err), status=400)
        except Exception:
            _logger.exception("order-details inbound failed")
            return self._error_response(
                _("Unexpected server error."),
                status=500,
            )

        return self._success_response(order, action, payload.get("oid"))

    @http.route(
        "/api/integration/batch-closing",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def batch_closing(self, **kwargs):
        auth_error = self._authenticate()
        if auth_error:
            return auth_error

        payload, parse_error = self._parse_json_body()
        if parse_error:
            return parse_error

        if payload.get("batch_id") in (None, ""):
            return self._error_response(_("batch_id is required."), status=400)

        try:
            batch, action = (
                request.env["integration.batch.closing"]
                .sudo()
                .upsert_from_payload(payload)
            )
        except ValueError as err:
            return self._error_response(str(err), status=400)
        except Exception:
            _logger.exception("batch-closing inbound failed")
            return self._error_response(
                _("Unexpected server error."),
                status=500,
            )

        return self._success_response(batch, action, payload.get("batch_id"))

    @http.route(
        "/api/integration/fee-request",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def fee_request(self, **kwargs):
        auth_error = self._authenticate()
        if auth_error:
            return auth_error

        payload, parse_error = self._parse_json_body()
        if parse_error:
            return parse_error

        if payload.get("request_id") in (None, ""):
            return self._error_response(_("request_id is required."), status=400)

        try:
            fee_request, action = (
                request.env["integration.fee.request"]
                .sudo()
                .upsert_from_payload(payload)
            )
        except LookupError as err:
            return self._error_response(str(err), status=404)
        except ValueError as err:
            return self._error_response(str(err), status=400)
        except Exception:
            _logger.exception("fee-request inbound failed")
            return self._error_response(
                _("Unexpected server error."),
                status=500,
            )

        return self._success_response(fee_request, action, payload.get("request_id"))
