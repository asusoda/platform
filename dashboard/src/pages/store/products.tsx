import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ImageOff, Package, Pencil, Plus } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, DeleteButton, EmptyState, ErrorNote, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { send } from '../../lib/api';
import { compact, timeAgo } from '../../lib/format';
import type { Product } from '../../lib/types';
import type { useStore } from './shared';

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

export function ProductsTab({
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
                    <DeleteButton
                      label={`Delete ${p.name}`}
                      question={`Delete ${p.name}? Members can no longer buy it.`}
                      onDelete={() => remove.mutate(p)}
                      disabled={remove.isPending}
                    />
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
