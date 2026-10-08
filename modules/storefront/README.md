# storefront

A merch store paid with points. Officers manage products and orders; members buy with their points balance, signed in with Discord or Clerk.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Product, order, store, member and checkout routes |
| `models.py` | Products, orders, order items |

The product and order queries live in `core/db.py` (`DBConnect.get_storefront_products` and the others).

## Surface

- Routes: `/api/storefront`, gated by the `storefront` switch. Product and order changes need an officer of the org; `/members/...` routes need a Discord session of a guild member; `/checkout`, `/wallet/<email>`, `/orders/<email>` and `POST /orders` take a Clerk or Discord token; product lists and `/store` are open.
- Jobs: none.
- Tools: none.
- Tables: `products`, `orders`, `order_items`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
