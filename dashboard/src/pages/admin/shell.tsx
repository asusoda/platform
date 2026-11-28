import { ArrowLeft, ShieldX } from 'lucide-react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { AuthFrame } from '../../components/auth-frame';
import { ADMIN_PATH, AdminMark, Crumb, Frame, HomeCrumb, SidebarNav, Switcher, useCurrentEntry } from '../../components/shell';
import { ErrorNote, LinkButton, Spinner } from '../../components/ui';
import { useOrganizations } from '../../lib/org';
import { useSuperadmin } from '../../lib/queries';
import { ADMIN_PAGES, ADMIN_SECTIONS } from './registry';

const SPACE = 'Superadmin';

// The page a signed-in officer who is not the superadmin sees on /admin. It makes no superadmin data call.
function NotAllowed() {
  return (
    <AuthFrame width="max-w-sm">
      <div className="flex flex-col items-center text-center">
        <span className="mb-4 flex size-10 items-center justify-center rounded-lg border border-line bg-panel-2 text-muted">
          <ShieldX className="size-5" />
        </span>
        <h1 className="text-xl font-semibold tracking-tight">Not allowed</h1>
        <p className="mt-1.5 text-sm text-muted">This page is for the Platform superadmin.</p>
        <LinkButton to="/" className="mt-6">
          <ArrowLeft className="size-4" /> Your orgs
        </LinkButton>
      </div>
    </AuthFrame>
  );
}

// The box at the top of the sidebar: Superadmin, and a select that opens an org.
function AdminSwitcher({ collapsed }: { collapsed: boolean }) {
  const { data } = useOrganizations();
  const navigate = useNavigate();
  const options = [{ value: ADMIN_PATH, label: SPACE }, ...(data ?? []).map((o) => ({ value: o.prefix, label: o.name }))];
  return (
    <Switcher
      collapsed={collapsed}
      name={SPACE}
      sub="admin"
      mark={<AdminMark className="size-7" />}
      value={ADMIN_PATH}
      options={options}
      onPick={(value) => navigate(value === ADMIN_PATH ? ADMIN_PATH : `/${value}`)}
    />
  );
}

function AdminSpace() {
  const page = useCurrentEntry(ADMIN_PAGES);
  const section = ADMIN_SECTIONS.find((s) => s.id === page?.section);
  const sectionTitle = section && 'title' in section ? section.title : undefined;
  const sections = ADMIN_SECTIONS.map((s) => ({
    id: s.id,
    title: 'title' in s ? s.title : undefined,
    items: ADMIN_PAGES.filter((p) => p.section === s.id).map(({ path, label, icon }) => ({
      to: path ? `${ADMIN_PATH}/${path}` : ADMIN_PATH,
      end: !path,
      label,
      icon,
    })),
  }));

  useEffect(() => {
    document.title = page ? `${page.label} - ${SPACE} - Platform` : 'Platform';
  }, [page]);

  return (
    <Frame
      page={page}
      header={(state) => <AdminSwitcher {...state} />}
      nav={(state) => <SidebarNav sections={sections} {...state} />}
      crumbs={
        <>
          <HomeCrumb to={ADMIN_PATH} mark={<AdminMark className="size-5" />} name={SPACE} />
          {sectionTitle && sectionTitle !== page?.label ? <Crumb className="hidden sm:flex">{sectionTitle}</Crumb> : null}
          {page ? <Crumb current>{page.label}</Crumb> : null}
        </>
      }
    />
  );
}

// The superadmin space at /admin. It renders its pages only for the superadmin.
export function AdminShell() {
  const superadmin = useSuperadmin();
  if (superadmin.isLoading) {
    return (
      <div role="status" aria-label="Loading" className="flex min-h-screen items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }
  if (superadmin.error) {
    return (
      <AuthFrame>
        <ErrorNote error={superadmin.error} />
      </AuthFrame>
    );
  }
  return superadmin.data ? <AdminSpace /> : <NotAllowed />;
}
