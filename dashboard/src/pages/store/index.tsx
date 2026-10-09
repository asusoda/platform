import { Package, Plus, ShoppingBag } from 'lucide-react';
import { useMemo, useState } from 'react';
import { TabBar, useTabParam } from '../../components/tabs';
import { Button, Dialog, PageHeader, Stat, StatGrid } from '../../components/ui';
import { compact } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { Order, Product } from '../../lib/types';
import { OrderDialog } from './order-form';
import { OrdersTab } from './orders';
import { ProductForm } from './product-form';
import { ProductsTab } from './products';
import { useStore } from './shared';

const TABS = [
  { id: 'products', label: 'Products' },
  { id: 'orders', label: 'Orders' },
] as const;

export function StorePage() {
  const { prefix } = useCurrentOrg();
  const [tab, setTab] = useTabParam(TABS);
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
      <StatGrid className="mb-6">
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
      </StatGrid>
      <TabBar
        label="Store"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        extra={(id) =>
          id === 'orders' && open.length ? <span className="ml-1.5 text-xs text-muted tabular-nums">{open.length}</span> : null
        }
      />
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
