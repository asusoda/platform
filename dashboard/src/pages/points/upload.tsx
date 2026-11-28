import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button, Dialog, ErrorNote, Field, FormActions, Input, OkNote, Table, Td, Th, Tr } from '../../components/ui';
import { api } from '../../lib/api';
import type { PointsImport } from '../../lib/types';
import { importRunning, pointsImportQuery, refreshPoints } from './shared';

export function UploadDialog({ prefix, open, onClose }: { prefix: string; open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [event, setEvent] = useState('');
  const [points, setPoints] = useState('');
  const [importId, setImportId] = useState<number | null>(null);
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append('file', file as File);
      form.append('event_name', event);
      form.append('event_points', points);
      return api<{ message: string; import_id: number }>(`/api/points/${prefix}/uploadEventCSV`, { method: 'POST', body: form });
    },
    onSuccess: (body) => {
      setImportId(body.import_id);
      void client.invalidateQueries({ queryKey: ['points', prefix, 'imports'], exact: true });
    },
  });
  // The query keeps polling after the dialog closes, and the Points page shows the run while it runs
  const run = useQuery(pointsImportQuery(prefix, importId));
  const status = run.data?.status;
  useEffect(() => {
    // Each batch of the import adds points, so the totals load again as it runs and when it ends
    if (run.data) refreshPoints(client, prefix);
  }, [client, prefix, run.data?.rows_done, status]);

  const close = () => {
    if (!importRunning(run.data)) {
      upload.reset();
      setImportId(null);
      setFile(null);
      setEvent('');
      setPoints('');
    }
    onClose();
  };
  return (
    <Dialog open={open} onClose={close} title="Upload event check-ins" description="Gives points to each checked-in row, once per email." wide={Boolean(importId)}>
      {importId !== null ? (
        <div className="space-y-4">
          {run.error ? <ErrorNote error={run.error} /> : run.data ? <ImportResult run={run.data} /> : <ImportProgress done={0} total={null} />}
          <FormActions>
            <Button onClick={close}>{importRunning(run.data) ? 'Close, keep importing' : 'Close'}</Button>
          </FormActions>
        </div>
      ) : (
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            upload.mutate();
          }}
        >
          <Field label="CSV file" hint="Columns: Email, First Name, Last Name and Checked-In Date.">
            <Input
              type="file"
              accept=".csv,text/csv"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="h-auto py-1.5 file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-panel-2 file:px-2 file:py-1 file:text-sm"
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Event">
              <Input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="Build night" required />
            </Field>
            <Field label="Points for each member" hint="A whole number.">
              <Input type="number" step={1} value={points} onChange={(e) => setPoints(e.target.value)} placeholder="10" required />
            </Field>
          </div>
          <FormActions error={upload.error}>
            <Button variant="primary" disabled={!file || !event || !points || upload.isPending}>
              <Upload className="size-4" /> Upload
            </Button>
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
          </FormActions>
        </form>
      )}
    </Dialog>
  );
}

// A bar of rows done out of rows total.
export function ImportProgress({ done, total }: { done: number; total: number | null }) {
  const share = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div className="space-y-1.5">
      <div
        className="h-1.5 overflow-hidden rounded-full bg-panel-2"
        role="progressbar"
        aria-label="Import progress"
        aria-valuemin={0}
        aria-valuemax={total ?? 0}
        aria-valuenow={done}
      >
        <div className="h-full rounded-full bg-fg transition-[width] duration-300" style={{ width: `${share}%` }} />
      </div>
      <p className="text-xs text-muted tabular-nums">{total === null ? 'Waiting to start' : `${done} of ${total} rows`}</p>
    </div>
  );
}

// The state of one run: the progress while it runs, then the counts and the rows that failed.
function ImportResult({ run }: { run: PointsImport }) {
  if (importRunning(run)) return <ImportProgress done={run.rows_done} total={run.rows_total} />;
  const counts = `${run.awarded} awarded, ${run.skipped} duplicate ${run.skipped === 1 ? 'row' : 'rows'} skipped, ${run.errors.length} failed.`;
  return (
    <div className="space-y-4">
      {run.status === 'failed' ? <ErrorNote error={`The import stopped. ${counts}`} /> : <OkNote>Import done. {counts}</OkNote>}
      {run.errors.length ? (
        <div className="max-h-72 overflow-y-auto rounded-lg border border-line">
          <Table>
            <thead>
              <tr>
                <Th className="w-16">Row</Th>
                <Th>Email</Th>
                <Th>Problem</Th>
              </tr>
            </thead>
            <tbody>
              {run.errors.map((e, i) => (
                <Tr key={`${e.row}-${i}`}>
                  <Td className="text-muted tabular-nums">{e.row}</Td>
                  <Td className="max-w-40 truncate">{e.email ?? <span className="text-muted">None</span>}</Td>
                  <Td className="text-pretty">{e.message}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      ) : null}
    </div>
  );
}
