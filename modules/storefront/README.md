# storefront

A merch store paid with points. Officers manage products and orders. Members buy with their points balance, signed in with Discord or Clerk.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `storefront_blueprint`; product, order and store routes |
| `member_api.py` | Member routes on the same blueprint: `/members/...`, `/orders/<email>`, `/wallet/<email>`, `/checkout` |
| `service.py` | Product and order queries, category clean-up, the catalog price check |
| `models.py` | Products, orders, order items |

## Surface

- Routes: `/api/storefront`, behind the `storefront` switch. Product and order changes need an officer of the org. `/members/...` routes need a Discord session of a server member. `/checkout`, `/wallet/<email>`, `/orders/<email>` and `POST /orders` need a Clerk or platform token. Product lists and `/store` are open.
- Jobs: none.
- Tools: none.
- Tables: `products`, `orders`, `order_items`.

## Known gaps

- Views in `api.py` and `member_api.py` open their own session, query and commit. `service.py` has only the shared queries.
- Checkout reads the balance and writes the order with no row lock. See Known faults in `docs/roadmap.md`.
