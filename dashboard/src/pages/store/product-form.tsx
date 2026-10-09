import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Field, FormActions, Input, Textarea } from '../../components/ui';
import { send } from '../../lib/api';
import type { Product } from '../../lib/types';

type ProductDraft = { name: string; category: string; price: string; stock: string; image: string; description: string };

const toDraft = (p: Product | null): ProductDraft => ({
  name: p?.name ?? '',
  category: p?.category ?? '',
  price: p ? String(p.price) : '',
  stock: p ? String(p.stock) : '',
  image: p?.image_url ?? '',
  description: p?.description ?? '',
});

export function ProductForm({ prefix, product, onDone }: { prefix: string; product: Product | null; onDone: () => void }) {
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
