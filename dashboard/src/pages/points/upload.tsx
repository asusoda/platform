import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload } from 'lucide-react';
import { useState } from 'react';
import { Button, Dialog, Field, FormActions, Input, OkNote } from '../../components/ui';
import { api } from '../../lib/api';

export function UploadDialog({ prefix, open, onClose }: { prefix: string; open: boolean; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [event, setEvent] = useState('');
  const [points, setPoints] = useState('');
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append('file', file as File);
      form.append('event_name', event);
      form.append('event_points', points);
      return api<{ message: string }>(`/api/points/${prefix}/uploadEventCSV`, { method: 'POST', body: form });
    },
  });
  const client = useQueryClient();
  const close = () => {
    // The import runs in the background, so the lists load again when the dialog closes
    if (upload.isSuccess) client.invalidateQueries({ queryKey: ['points', prefix] });
    upload.reset();
    setFile(null);
    setEvent('');
    setPoints('');
    onClose();
  };
  return (
    <Dialog
      open={open}
      onClose={close}
      title="Upload event check-ins"
      description="Gives the points to each row with a check-in date, one time for each email. A member that is not found is added."
    >
      {upload.isSuccess ? (
        <div className="space-y-4">
          <OkNote>The server adds the points in the background. Reload this page in a minute to see them.</OkNote>
          <Button onClick={close}>Close</Button>
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
