import { useMutation } from '@tanstack/react-query';
import { FileUp, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { Badge, Button, cx, Dot, Field, FormActions, Input, Mono, Spinner } from '../components/ui';
import { api } from '../lib/api';
import { bytes } from '../lib/format';
import type { UploadResult } from '../lib/types';

// Limits from modules/knowledge/documents.py.
export const UPLOAD_TYPES = ['.txt', '.md', '.markdown', '.csv', '.html', '.htm', '.pdf', '.docx'];
const MAX_FILES = 20;
const MAX_FILE_BYTES = 10_000_000;
const MAX_TOTAL_BYTES = 25_000_000;
const mb = (n: number) => `${n / 1_000_000} MB`;
const FOLDER_PATTERN = /^[a-z0-9][a-z0-9_-]{0,40}$/;

function typeOk(file: File): boolean {
  const name = file.name.toLowerCase();
  return UPLOAD_TYPES.some((t) => name.endsWith(t));
}

export function UploadForm({
  prefix,
  categories,
  canPublish,
  onUploaded,
  onCancel,
}: {
  prefix: string;
  categories: string[];
  canPublish: boolean;
  onUploaded: () => void;
  onCancel: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [folder, setFolder] = useState('upload');
  const [category, setCategory] = useState('documents');
  const [publish, setPublish] = useState(false);
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const f of files) form.append('files', f);
      form.append('folder', folder);
      form.append('category', category.trim());
      if (publish) form.append('public', 'true');
      return api<UploadResult>(`/api/dashboard/${prefix}/knowledge/documents`, { method: 'POST', body: form });
    },
    onSuccess: onUploaded,
  });

  const total = files.reduce((n, f) => n + f.size, 0);
  const tooBig = files.filter((f) => f.size > MAX_FILE_BYTES);
  const wrongType = files.filter((f) => !typeOk(f));
  const folderOk = FOLDER_PATTERN.test(folder);
  const problem =
    files.length > MAX_FILES
      ? `Pick at most ${MAX_FILES} files.`
      : total > MAX_TOTAL_BYTES
        ? `The files together are ${bytes(total)}; the limit is ${mb(MAX_TOTAL_BYTES)}.`
        : null;
  const ready = files.length > 0 && !problem && folderOk && category.trim() && !upload.isPending;
  const add = (list: FileList | null) => {
    if (!list) return;
    const names = new Set(files.map((f) => f.name));
    setFiles([...files, ...[...list].filter((f) => !names.has(f.name))]);
    upload.reset();
  };

  if (upload.data) {
    const r = upload.data;
    return (
      <div className="space-y-4">
        <p className="text-sm">
          {r.indexed} indexed, {r.unchanged} unchanged, {r.failed} failed.
        </p>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {r.files.map((f) => (
            <li key={f.key + f.file} className="flex items-start gap-2.5 px-3 py-2 text-sm">
              <span className="mt-1.5">
                <Dot tone={f.error ? 'bad' : f.changed ? 'ok' : 'muted'} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate">{f.file}</div>
                {f.error ? (
                  <div className="text-xs text-bad">{f.error}</div>
                ) : (
                  <div className="text-xs text-muted">
                    <Mono>{f.key}</Mono> · {f.chunks} passages{f.changed ? '' : ', unchanged'}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
        <FormActions>
          <Button variant="primary" onClick={onCancel}>
            Done
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setFiles([]);
              upload.reset();
            }}
          >
            Upload more
          </Button>
        </FormActions>
      </div>
    );
  }

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) upload.mutate();
      }}
    >
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
        className={cx(
          'flex w-full cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors',
          dragging ? 'border-fg bg-panel-2' : 'border-line hover:bg-panel-2/50',
        )}
      >
        <FileUp className="size-6 text-muted" />
        <span className="text-sm font-medium">Drop files here or choose files</span>
        <span className="text-xs text-muted">
          PDF, Word (.docx), Markdown, HTML, text or CSV. Up to {MAX_FILES} files, {mb(MAX_FILE_BYTES)} each.
        </span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={UPLOAD_TYPES.join(',')}
        className="hidden"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = '';
        }}
      />
      {files.length ? (
        <ul className="max-h-48 divide-y divide-line overflow-y-auto rounded-lg border border-line">
          {files.map((f) => (
            <li key={f.name} className="flex items-center gap-2 px-3 py-1.5 text-sm">
              <span className="min-w-0 flex-1 truncate">{f.name}</span>
              {!typeOk(f) ? <Badge tone="bad">type not read</Badge> : null}
              {f.size > MAX_FILE_BYTES ? <Badge tone="bad">too large</Badge> : null}
              <span className="text-xs text-muted tabular-nums">{bytes(f.size)}</span>
              <button
                type="button"
                className="text-xs text-muted hover:text-fg"
                onClick={() => setFiles(files.filter((x) => x !== f))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {wrongType.length || tooBig.length ? (
        <p className="text-xs text-muted">Files marked in red fail; the others are still indexed.</p>
      ) : null}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          label="Folder"
          hint={folderOk ? `Keys are ${folder}/<file name>. The same name again replaces the file.` : 'Lower case letters, digits, _ and -.'}
        >
          <Input value={folder} onChange={(e) => setFolder(e.target.value.trim())} className="font-mono" aria-invalid={!folderOk} />
        </Field>
        <Field label="Category" hint="Agents can search one category at a time.">
          <Input value={category} onChange={(e) => setCategory(e.target.value)} list="upload-categories" required />
        </Field>
      </div>
      <datalist id="upload-categories">
        {categories.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {canPublish ? (
        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line p-3 text-sm">
          <input type="checkbox" className="mt-0.5 size-4 accent-current" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
          <span>
            <span className="block font-medium">Public</span>
            <span className="mt-0.5 block text-xs text-muted">Every organization's agents can search these documents.</span>
          </span>
        </label>
      ) : null}
      <FormActions error={problem ?? upload.error}>
        <Button variant="primary" disabled={!ready}>
          {upload.isPending ? <Spinner className="size-3.5" /> : <Upload className="size-4" />}
          {upload.isPending ? 'Indexing' : files.length > 1 ? `Upload ${files.length} files` : 'Upload'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
