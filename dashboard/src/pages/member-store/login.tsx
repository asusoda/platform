import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { AuthFrame } from '../../components/auth-frame';
import { Button, Field, FormActions, Input, Select } from '../../components/ui';
import { memberApi, storePath } from './shared';

const STANDINGS = ['Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate'];

// Member sign-in for the store: links or creates the member and starts a session on the API.
export function MemberLoginPage() {
  const prefix = useParams().prefix ?? '';
  const navigate = useNavigate();
  const [draft, setDraft] = useState({ name: '', asu_id: '', username: '', email: '', academic_standing: '', major: '' });
  const login = useMutation({
    mutationFn: () => memberApi(`/api/points/${prefix}/member_login`, { method: 'POST', body: JSON.stringify(draft) }),
    onSuccess: () => navigate(storePath(prefix)),
  });
  const set = (k: keyof typeof draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  return (
    <AuthFrame>
      <div className="rounded-2xl border border-line bg-panel p-6 shadow-xs sm:p-8">
        <h1 className="text-xl font-semibold tracking-tight">Member sign-in</h1>
        <p className="mt-1.5 text-sm text-pretty text-muted">Sign in to order from the store with your points.</p>
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            login.mutate();
          }}
        >
          <Field label="Full name">
            <Input value={draft.name} onChange={set('name')} required autoFocus />
          </Field>
          <Field label="Student ID">
            <Input value={draft.asu_id} onChange={set('asu_id')} required />
          </Field>
          <Field label="Email">
            <Input type="email" value={draft.email} onChange={set('email')} />
          </Field>
          <Field label="Username" hint="Optional.">
            <Input value={draft.username} onChange={set('username')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Class standing">
              <Select value={draft.academic_standing} onChange={set('academic_standing')}>
                <option value="">Not set</option>
                {STANDINGS.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </Select>
            </Field>
            <Field label="Major">
              <Input value={draft.major} onChange={set('major')} />
            </Field>
          </div>
          <FormActions error={login.error}>
            <Button variant="primary" disabled={login.isPending || !draft.name || !draft.asu_id}>
              Sign in
            </Button>
            <Link to={storePath(prefix)} className="text-sm text-muted hover:text-fg">
              Back to the store
            </Link>
          </FormActions>
        </form>
      </div>
    </AuthFrame>
  );
}
