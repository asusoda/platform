// Store products and orders.

export type Product = {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  image_url: string | null;
  category: string | null;
  organization_id: number;
  created_at: string | null;
  updated_at: string | null;
};

export type OrderItem = { id: number; product_id: number; quantity: number; price_at_time: number };

export type Order = {
  id: number;
  user_id: number;
  total_amount: number;
  status: string;
  message: string | null;
  created_at: string;
  updated_at: string | null;
  organization_id: number;
  user_name: string;
  user_email: string | null;
  items: OrderItem[];
  // The points the order took, less refunds. 0 for a cancelled order and for a member order placed before holds.
  points_held: number;
};
