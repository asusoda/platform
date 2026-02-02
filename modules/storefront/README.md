# Storefront Module

This module handles the storefront functionality, including product management and order processing.

## Database Structure

### Products Table
- `id` (Integer, Primary Key)
- `name` (String, Required)
- `description` (Text)
- `price` (Float, Required)
- `stock` (Integer, Required)
- `image_url` (String)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Orders Table
- `id` (Integer, Primary Key)
- `user_id` (String, Required)
- `total_amount` (Float, Required)
- `status` (String, Default: 'pending')
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Order Items Table
- `id` (Integer, Primary Key)
- `order_id` (Integer, Foreign Key)
- `product_id` (Integer, Foreign Key)
- `quantity` (Integer, Required)
- `price_at_time` (Float, Required)

## API Endpoints

### Products

#### Get All Products
- **GET** `/<org_prefix>/products`
- Returns a list of all products for an organization
- No authentication required

#### Get Single Product
- **GET** `/<org_prefix>/products/<product_id>`
- Returns details of a specific product
- No authentication required

#### Create Product
- **POST** `/<org_prefix>/products`
- Creates a new product
- **Requires dual authentication** (Clerk or Discord)
- Request body:
  ```json
  {
    "name": "Product Name",
    "description": "Product Description",
    "price": 29.99,
    "stock": 100,
    "image_url": "https://example.com/image.jpg"
  }
  ```

#### Update Product
- **PUT** `/<org_prefix>/products/<product_id>`
- Updates an existing product
- **Requires dual authentication** (Clerk or Discord)
- Request body: Same as create product, all fields optional

#### Delete Product
- **DELETE** `/<org_prefix>/products/<product_id>`
- Deletes a product
- **Requires dual authentication** (Clerk or Discord)

### Orders

#### Get All Orders
- **GET** `/<org_prefix>/orders`
- Returns a list of all orders
- **Requires dual authentication** (Clerk or Discord)

#### Get Single Order
- **GET** `/<org_prefix>/orders/<order_id>`
- Returns details of a specific order
- **Requires dual authentication** (Clerk or Discord)

#### Update Order Status
- **PUT** `/<org_prefix>/orders/<order_id>`
- Updates an order's status
- **Requires dual authentication** (Clerk or Discord)
- Request body:
  ```json
  {
    "status": "completed"
  }
  ```

#### Delete Order
- **DELETE** `/<org_prefix>/orders/<order_id>`
- Deletes an order
- **Requires dual authentication** (Clerk or Discord)

#### Create Order
- **POST** `/<org_prefix>/orders`
- Creates a new order
- Requires authentication
- Request body:
  ```json
  {
    "user_id": "discord_user_id",
    "total_amount": 99.99,
    "items": [
      {
        "product_id": 1,
        "quantity": 2,
        "price": 49.99
      }
    ]
  }
  ```

## Authentication

Protected endpoints support **dual authentication** - both Clerk (for website users) and Discord (for admin dashboard) tokens are accepted.

### Supported Authentication Methods

1. **Clerk Authentication** (Website Users)
   - Used by the public-facing website
   - Requires Clerk session token
   - Returns user email for identification

2. **Discord Authentication** (Admin Dashboard)
   - Used by the admin dashboard
   - Supports both session cookies and JWT tokens
   - Validates against Discord bot for permissions

### Usage

Include the authentication token in the request header:

```
Authorization: Bearer <token>
```

The system automatically detects the token type and validates accordingly:
- Clerk tokens are validated first
- If Clerk validation fails, Discord authentication is attempted
- Session cookies are also supported for Discord authentication

## Error Handling

All endpoints use the `@error_handler` decorator to provide consistent error responses. Common error responses include:

- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error 