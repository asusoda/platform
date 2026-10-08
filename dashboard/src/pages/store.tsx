import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ImageOff, Package, Pencil, Plus, ReceiptText, ShoppingBag, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { ModuleGate } from '../components/module-gate';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  cx,
  Dialog,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageHeader,
  Select,
  SkeletonRows,
  Stat,
  Table,
  Td,
  Textarea,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { compact, type Tone, timeAgo, when } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { Order, Product } from '../lib/types';

const TABS = [
  { id: 'products', label: 'Products' },
  { id: 'orders', label: 'Orders' },
] as const;

// The statuses update_order_status accepts. A checkout order starts as completed, which officers cannot set.
const STATUSES = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];

// Statuses with nothing left for an officer to do.
const CLOSED = new Set(['delivered', 'cancelled']);

const statusTone: Record<string, Tone> = {
  pending: 'warn',
  processing: 'active',
  shipped: 'active',
  delivered: 'ok',
  completed: 'ok',
  cancelled: 'muted',
};

function useStore(prefix: string) {
  const products = useQuery({
    queryKey: ['store', prefix, 'products'],
    queryFn: () => api<Product[]>(`/api/storefront/${prefix}/products`),
  });
  const orders = useQuery({
    queryKey: ['store', prefix, 'orders'],
    queryFn: () => api<Order[]>(`/api/storefront/${prefix}/orders`),
  });
  return { products, orders };
}

function Thumb({ url, name }: { url: string | null; name: string }) {
  const [broken, setBroken] = useState(false);
  return (
    <span className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-line bg-panel-2 text-muted">
      {url && !broken ? (
        <img src={url} alt={name} className="size-full object-cover" onError={() => setBroken(true)} />
      ) : (
        <ImageOff className="size-4" aria-hidden />
      )}
    </span>
  );
}

type ProductDraft = { name: string; category: string; price: string; stock: string; image: string; description: string };

const toDraft = (p: Product | null): ProductDraft => ({
  name: p?.name ?? '',
  category: p?.category ?? '',
  price: p ? String(p.price) : '',
  stock: p ? String(p.stock) : '',
  image: p?.image_url ?? '',
  description: p?.description ?? '',
});

function ProductForm({ prefix, product, onDone }: { prefix: string; product: Product | null; onDone: () => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState(() => toDraft(product));
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: draft.name.trim(),
        category: draft.category,
        price: Number(draft.price),
        stock: Number(draft.stock),
        image_url: draft.image.trim(),
        description: draft.description,
      };
      return product
        ? send(`/api/storefront/${prefix}/products/${product.id}`, 'PUT', body)
        : send(`/api/storefront/${prefix}/products`, 'POST', body);
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['store', prefix] });
      onDone();
    },
  });
  const set = (k: keyof ProductDraft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  // The create route refuses a price or stock of 0.
  const minStock = product ? 0 : 1;
  const valid = draft.name.trim() && Number(draft.price) > 0 && Number.isInteger(Number(draft.stock)) && Number(draft.stock) >= minStock;
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name">
          <Input value={draft.name} onChange={set('name')} placeholder="Club hoodie" maxLength={100} required autoFocus />
        </Field>
        <Field label="Category" hint="Optional. Groups products in the store.">
          <Input value={draft.category} onChange={set('category')} placeholder="Apparel" maxLength={50} />
        </Field>
        <Field label="Price (points)">
          <Input type="number" min={0} step="any" value={draft.price} onChange={set('price')} placeholder="250" required />
        </Field>
        <Field label="Stock" hint={product ? undefined : 'At least 1 for a new product.'}>
          <Input type="number" min={minStock} step={1} value={draft.stock} onChange={set('stock')} placeholder="20" required />
        </Field>
      </div>
      <Field label="Image URL" hint="Optional. A public https link to the product photo.">
        <Input type="url" value={draft.image} onChange={set('image')} placeholder="https://..." maxLength={255} />
      </Field>
      <Field label="Description">
        <Textarea value={draft.description} onChange={set('description')} className="min-h-20" />
      </Field>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!valid || save.isPending}>
          {product ? 'Save product' : 'Add product'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function ProductsTab({
  prefix,
  products,
  onEdit,
  onAdd,
}: {
  prefix: string;
  products: ReturnType<typeof useStore>['products'];
  onEdit: (p: Product) => void;
  onAdd: () => void;
}) {
  const client = useQueryClient();
  const remove = useMutation({
    mutationFn: (p: Product) => send(`/api/storefront/${prefix}/products/${p.id}`, 'DELETE'),
    onSuccess: () => client.invalidateQueries({ queryKey: ['store', prefix] }),
  });
  const list = [...(products.data ?? [])].sort((a, b) => a.name.localeCompare(b.name));
  return (
    <Card>
      <CardHeader title="Products" hint="Members buy these with points in the member store." />
      {remove.error ? (
        <div className="border-b border-line p-4">
          <ErrorNote error={remove.error} />
        </div>
      ) : null}
      {products.error ? (
        <div className="p-4">
          <ErrorNote error={products.error} />
        </div>
      ) : products.isLoading ? (
        <SkeletonRows rows={5} />
      ) : list.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Product</Th>
              <Th className="text-right">Price</Th>
              <Th className="text-right">Stock</Th>
              <Th className="hidden text-right md:table-cell">Updated</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <Tr key={p.id}>
                <Td className="w-full max-w-0">
                  <div className="flex min-w-0 items-center gap-3">
                    <Thumb url={p.image_url} name={p.name} />
                    <div className="min-w-0">
                      <div className="truncate font-medium">{p.name}</div>
                      <div className="truncate text-xs text-muted">{p.category ?? 'No category'}</div>
                    </div>
                  </div>
                </Td>
                <Td className="text-right whitespace-nowrap tabular-nums">{compact(p.price)}</Td>
                <Td className="text-right">
                  {p.stock > 0 ? <span className="tabular-nums">{p.stock}</span> : <Badge tone="warn">sold out</Badge>}
                </Td>
                <Td className="hidden text-right text-xs whitespace-nowrap text-muted md:table-cell">{timeAgo(p.updated_at)}</Td>
                <Td className="pr-2 pl-0">
                  <div className="flex items-center justify-end">
                    <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${p.name}`} onClick={() => onEdit(p)}>
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Delete"
                      aria-label={`Delete ${p.name}`}
                      className="hover:text-bad"
                      disabled={remove.isPending}
                      onClick={() => {
                        if (confirm(`Delete ${p.name}? Members can no longer buy it.`)) remove.mutate(p);
                      }}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState
          icon={Package}
          title="No products yet"
          action={
            <Button variant="primary" onClick={onAdd}>
              <Plus className="size-4" /> Add product
            </Button>
          }
        >
          Add a product with a price in points. Members see it in the member store.
        </EmptyState>
      )}
    </Card>
  );
}

function OrderDialog({
  prefix,
  order,
  products,
  onClose,
}: {
  prefix: string;
  order: Order | null;
  products: Map<number, Product>;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={Boolean(order)}
      onClose={onClose}
      title={order ? `Order #${order.id}` : 'Order'}
      description={order ? `${order.user_name}${order.user_email ? `, ${order.user_email}` : ''}. Placed ${when(order.created_at)}.` : undefined}
      wide
    >
      {order ? <OrderForm key={order.id} prefix={prefix} order={order} products={products} onDone={onClose} /> : null}
    </Dialog>
  );
}

function OrderForm({ prefix, order, products, onDone }: { prefix: string; order: Order; products: Map<number, Product>; onDone: () => void }) {
  const client = useQueryClient();
  const [status, setStatus] = useState(order.status);
  const [message, setMessage] = useState(order.message ?? '');
  const changed = status !== order.status || message !== (order.message ?? '');
  const refresh = () => client.invalidateQueries({ queryKey: ['store', prefix] });
  const save = useMutation({
    // The route refuses a status it does not know, so the status goes only when it changed.
    mutationFn: () =>
      send(`/api/storefront/${prefix}/orders/${order.id}`, 'PUT', {
        ...(status !== order.status ? { status } : {}),
        message,
      }),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  const remove = useMutation({
    mutationFn: () => send(`/api/storefront/${prefix}/orders/${order.id}`, 'DELETE'),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  const options = STATUSES.includes(order.status) ? STATUSES : [order.status, ...STATUSES];
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="overflow-hidden rounded-lg border border-line">
        <Table>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th className="text-right">Qty</Th>
              <Th className="text-right">Points</Th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <Tr key={item.id}>
                <Td className="w-full max-w-0">
                  <div className="truncate">{products.get(item.product_id)?.name ?? `Product ${item.product_id} (deleted)`}</div>
                  <div className="text-xs text-muted tabular-nums">{compact(item.price_at_time)} each</div>
                </Td>
                <Td className="text-right tabular-nums">{item.quantity}</Td>
                <Td className="text-right tabular-nums">{compact(item.price_at_time * item.quantity)}</Td>
              </Tr>
            ))}
            <Tr>
              <Td className="font-medium">Total</Td>
              <Td />
              <Td className="text-right font-medium tabular-nums">{compact(order.total_amount)}</Td>
            </Tr>
          </tbody>
        </Table>
      </div>
      <div className="grid gap-5 sm:grid-cols-[200px_minmax(0,1fr)]">
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {options.map((s) => (
              <option key={s} value={s} disabled={!STATUSES.includes(s)}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Message to the member" hint="For example, where and when to pick up the order.">
          <Textarea value={message} onChange={(e) => setMessage(e.target.value)} className="min-h-20" />
        </Field>
      </div>
      <FormActions error={save.error ?? remove.error}>
        <Button variant="primary" disabled={!changed || save.isPending}>
          Save order
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="danger"
          className="ml-auto"
          disabled={remove.isPending}
          onClick={() => {
            const stock = CLOSED.has(order.status) ? 'Stock does not change.' : 'Its items go back into stock.';
            if (confirm(`Delete order #${order.id}? ${stock} The member does not get the points back.`)) remove.mutate();
          }}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </FormActions>
    </form>
  );
}

function OrdersTab({ orders, onOpen }: { orders: ReturnType<typeof useStore>['orders']; onOpen: (o: Order) => void }) {
  const list = [...(orders.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <Card>
      <CardHeader title="Orders" hint="Newest first. Select an order to change its status or add a message." />
      {orders.error ? (
        <div className="p-4">
          <ErrorNote error={orders.error} />
        </div>
      ) : orders.isLoading ? (
        <SkeletonRows rows={5} />
      ) : list.length ? (
        <Table>
          <thead>
            <tr>
              <Th className="w-16 pr-0">Order</Th>
              <Th>Member</Th>
              <Th className="hidden text-right sm:table-cell">Items</Th>
              <Th className="text-right">Points</Th>
              <Th className="hidden sm:table-cell">Status</Th>
              <Th className="hidden text-right md:table-cell">Placed</Th>
            </tr>
          </thead>
          <tbody>
            {list.map((o) => (
              <Tr key={o.id}>
                <Td className="pr-0 text-xs text-muted tabular-nums">#{o.id}</Td>
                <Td className="w-full max-w-0">
                  <button type="button" className="block w-full min-w-0 cursor-pointer text-left" onClick={() => onOpen(o)}>
                    <span className="block truncate font-medium">{o.user_name}</span>
                    <span className="flex min-w-0 items-center gap-2 text-xs text-muted">
                      <Badge tone={statusTone[o.status] ?? 'muted'} className="sm:hidden">
                        {o.status}
                      </Badge>
                      <span className="truncate">{o.user_email ?? ''}</span>
                    </span>
                  </button>
                </Td>
                <Td className="hidden text-right text-muted tabular-nums sm:table-cell">
                  {o.items.reduce((n, i) => n + i.quantity, 0)}
                </Td>
                <Td className="text-right tabular-nums">{compact(o.total_amount)}</Td>
                <Td className="hidden sm:table-cell">
                  <Badge tone={statusTone[o.status] ?? 'muted'}>{o.status}</Badge>
                </Td>
                <Td className="hidden text-right text-xs whitespace-nowrap text-muted md:table-cell">{timeAgo(o.created_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState icon={ReceiptText} title="No orders yet">
          Orders show here when members buy products in the member store.
        </EmptyState>
      )}
    </Card>
  );
}

function Store() {
  const { prefix } = useCurrentOrg();
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.id === params.get('tab'))?.id ?? 'products';
  const [editing, setEditing] = useState<Product | 'new' | null>(null);
  const [viewing, setViewing] = useState<Order | null>(null);
  const { products, orders } = useStore(prefix);
  const byId = useMemo(() => new Map((products.data ?? []).map((p) => [p.id, p])), [products.data]);
  const open = (orders.data ?? []).filter((o) => o.status === 'pending' || o.status === 'processing' || o.status === 'shipped');
  const add = () => setEditing('new');
  return (
    <>
      <PageHeader
        title="Store"
        description="Products members buy with points, and the orders they place."
        action={
          <Button variant="primary" onClick={add}>
            <Plus className="size-4" /> Add product
          </Button>
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Products" value={products.data ? products.data.length : '-'} icon={<Package className="size-4" />} />
        <Stat
          label="Sold out"
          value={products.data ? products.data.filter((p) => p.stock <= 0).length : '-'}
          sub={products.data ? `${compact(products.data.reduce((n, p) => n + Math.max(p.stock, 0), 0))} items in stock` : undefined}
        />
        <Stat label="Open orders" value={orders.data ? open.length : '-'} sub="Not delivered yet" icon={<ShoppingBag className="size-4" />} />
        <Stat
          label="Points spent"
          value={orders.data ? compact(orders.data.reduce((n, o) => n + o.total_amount, 0)) : '-'}
          sub={orders.data ? `${orders.data.length} orders` : undefined}
        />
      </div>
      <div role="tablist" aria-label="Store" className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams(t.id === 'products' ? {} : { tab: t.id }, { replace: true })}
            className={cx(
              '-mb-px h-9 cursor-pointer border-b-2 px-3 text-sm transition-colors',
              tab === t.id ? 'border-fg font-medium text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {t.label}
            {t.id === 'orders' && open.length ? <span className="ml-1.5 text-xs text-muted tabular-nums">{open.length}</span> : null}
          </button>
        ))}
      </div>
      {tab === 'orders' ? (
        <OrdersTab orders={orders} onOpen={setViewing} />
      ) : (
        <ProductsTab prefix={prefix} products={products} onEdit={setEditing} onAdd={add} />
      )}
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing && editing !== 'new' ? `Edit ${editing.name}` : 'Add product'}
        description="Prices are in points. A product with no stock does not show in the member store."
      >
        {editing !== null ? (
          <ProductForm
            key={editing === 'new' ? 'new' : editing.id}
            prefix={prefix}
            product={editing === 'new' ? null : editing}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>
      <OrderDialog prefix={prefix} order={viewing} products={byId} onClose={() => setViewing(null)} />
    </>
  );
}

export function StorePage() {
  return (
    <ModuleGate module="storefront" title="Store">
      <Store />
    </ModuleGate>
  );
}
