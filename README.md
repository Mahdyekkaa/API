pos# Odoo Inbound Integration API

Standalone Odoo 18 module that receives Order Details and Batch Closing payloads from an external system.

## Install

1. Add `/home/mahdy/work/odoo18/custom/odoo-inbound-api` to the Odoo addons path.
2. Update the apps list and install **Inbound Integration API**.
3. Open **Inbound Integration → Configuration → Settings** and set the API auth token.

Demo data (orders + batch closings + sample products) loads when the database is created with **Load demonstration data**, or when the module is installed on a demo database.

## Endpoints

| Method | URL | Purpose |
|--------|-----|---------|
| POST | `/api/integration/order-details` | Create/update order by `oid` |
| POST | `/api/integration/batch-closing` | Create/update batch by `batch_id` |

### Authentication

Send one of:

- `Authorization: Bearer <token>`
- `API-Key: <token>` / `X-API-Key: <token>`

### Success response

```json
{
  "success": true,
  "external_id": "229681",
  "odoo_record_id": 12345,
  "action": "created"
}
```

`action` is `created` (HTTP 201) or `updated` (HTTP 200). Repeated requests for the same `oid` / `batch_id` update the existing record.

### Matching rules

- **Orders**: unique on external `oid`
- **Products**: match `product.product` by exact name or `default_code`, then case-insensitive fallback
- **Batches**: unique on external `batch_id`
- **Currency**: company currency

## Postman

Import `postman/Inbound_Integration_API.postman_collection.json` into Postman.

1. Set collection variables `base_url` and `auth_token`.
2. Use **Demo Data** for test payloads, or **Real Data** and fill in business values.
3. Both folders call the same endpoints:
   - `POST /api/integration/order-details`
   - `POST /api/integration/batch-closing`
