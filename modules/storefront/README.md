# storefront

A merch store paid with points. Officers manage products and orders; members buy with their points balance, signed in with Discord or Clerk.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `storefront_blueprint`; product, order and store routes |
| `member_api.py` | Member routes on the same blueprint: `/members/...`, `/orders/<email>`, `/wallet/<email>`, `/checkout` |
| `service.py` | Product and order queries, category clean-up, the catalog price check |
| `models.py` | Products, orders, order items |

## Surface

- Routes: `/api/storefront`, gated by the `storefront` switch. Product and order changes need an officer of the org; `/members/...` routes need a Discord session of a guild member; `/checkout`, `/wallet/<email>`, `/orders/<email>` and `POST /orders` take a Clerk or Discord token; product lists and `/store` are open.
- Jobs: none.
- Tools: none.
- Tables: `products`, `orders`, `order_items`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
