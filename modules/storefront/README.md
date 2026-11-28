# storefront

A merch store paid with points. Officers manage products and orders. Members buy with their points balance, signed in with Discord or Clerk.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `storefront_blueprint`; product, order and store routes |
| `member_api.py` | Member routes on the same blueprint: `/members/...`, `/orders/<email>`, `/wallet/<email>`, `/checkout` |
| `service.py` | Product and order queries and changes, category clean-up, catalog pricing of an order, `place_order` (the balance lock, the points charge or hold), the refund and `held_points`; declares `store:read` and `store:write` |
| `tools.py` | The `store.*` tools |
| `models.py` | Products, orders, order items |

## Surface

- Routes: `/api/storefront`, behind the `storefront` switch. Product and order changes need an officer of the org. `/members/...` routes need a Discord session of a server member. `/checkout`, `/wallet/<email>`, `/orders/<email>` and `POST /orders` need a Clerk or platform token. Product lists and `/store` are open.
- Jobs: none.
- Tools: `store.products`, `store.orders` (scope `store:read`); `store.save_product`, `store.update_orders`, `store.delete_products` (confirm), `store.delete_orders` (confirm) (scope `store:write`). Each one that takes `ids` takes up to 100. A cancel or a delete gives a refund as the routes do. A product that is in an order cannot be deleted.
- Webhook events: `order.created`, from `create_order()`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `products`, `orders`, `order_items`.

## Known gaps

- Views in `api.py` and `member_api.py` open their own session, query and commit. `service.py` has only the shared queries.
- Each order lists its `points_held` with one query for the whole list (`held_points`), from the `Storefront Purchase` and `Refund` rows of `points`. An order id in the event name is the only link between an order and its points rows.
