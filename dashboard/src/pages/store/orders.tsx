import { ReceiptText } from 'lucide-react';
import { Badge, Card, CardHeader, EmptyState, ErrorNote, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { compact, type Tone, timeAgo } from '../../lib/format';
import type { Order } from '../../lib/types';
import type { useStore } from './shared';

const statusTone: Record<string, Tone> = {
  pending: 'warn',
  processing: 'active',
  shipped: 'active',
  delivered: 'ok',
  completed: 'ok',
  cancelled: 'muted',
};

export function OrdersTab({ orders, onOpen }: { orders: ReturnType<typeof useStore>['orders']; onOpen: (o: Order) => void }) {
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
