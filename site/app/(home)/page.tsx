import Link from 'next/link';
import type { ReactNode } from 'react';
import {
  ArrowRight,
  Bot,
  CalendarDays,
  Cpu,
  FileSearch,
  GraduationCap,
  KeyRound,
  Lock,
  Plug,
  Rocket,
  ScrollText,
  ShieldCheck,
  ShoppingBag,
  Ticket,
  Timer,
  Trophy,
} from 'lucide-react';
import { gitConfig } from '@/lib/shared';

const repoUrl = `https://github.com/${gitConfig.user}/${gitConfig.repo}`;

const clubModules = [
  { icon: Trophy, name: 'Points', text: 'Attendance points, leaderboards and CSV imports from events.' },
  { icon: ShoppingBag, name: 'Storefront', text: 'A merch store paid in points, with prices checked on the server.' },
  { icon: CalendarDays, name: 'Calendar', text: 'Notion events synced to Google Calendar with per-org credentials.' },
  { icon: Ticket, name: 'LeetCode and games', text: 'A daily LeetCode post and Jeopardy, run in the Discord server.' },
];

const buildModules = [
  {
    icon: Cpu,
    name: 'Compute',
    text: 'GPU and CPU pods on the org’s RunPod account. Members SSH in with 12-hour certificates through the godfather CLI.',
  },
  {
    icon: Bot,
    name: 'Agents',
    text: 'Conversations, memories and a profile graph per member, kept for an agent and pruned after 180 days.',
  },
  {
    icon: FileSearch,
    name: 'Knowledge',
    text: 'Hybrid search over documents and crawled public pages, with pgvector and full text.',
  },
  {
    icon: GraduationCap,
    name: 'ASU',
    text: '226 public ASU pages and 16 live queries such as dining and library hours, indexed for search.',
  },
  {
    icon: KeyRound,
    name: 'Accounts',
    text: 'Canvas, Google and Outlook sign-in bound to a member’s Discord account, so agents can act for them.',
  },
  {
    icon: Rocket,
    name: 'Apps',
    text: 'Deploy an org’s own apps to RunPod from a manifest in their repo, with health checks and rollback.',
  },
];

const guarantees = [
  { icon: ShieldCheck, name: 'Access checks on every org route', text: 'Member, officer and superadmin checks run before any handler.' },
  { icon: ScrollText, name: 'Audit log', text: 'Every change an officer or a token makes is recorded with who made it.' },
  { icon: Lock, name: 'Encrypted org secrets', text: 'RunPod keys, Google credentials and OAuth grants are encrypted at rest.' },
  { icon: Timer, name: 'Short-lived credentials', text: 'SSH certificates last 12 hours for one pod. Machine tokens are scoped and revocable.' },
];

const processes = [
  ['API', 'main.py', ':8000'],
  ['Web app', 'web/', ':5000'],
  ['Discord bot', 'bot_main.py', ''],
  ['Job worker', 'worker_main.py', ''],
  ['MCP server', 'mcp_main.py', ':8001'],
];

export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col">
      <Hero />
      <Section
        eyebrow="Modules"
        title="Turn on what your org uses."
        text="Each organization is a Discord server. Points, the store, calendar, LeetCode and compute switch on or off per organization. A module that is off returns 404 for that org and disappears from its web app."
      >
        <div className="grid gap-px overflow-hidden rounded-xl border bg-fd-border sm:grid-cols-2 lg:grid-cols-4">
          {clubModules.map((m) => (
            <Feature key={m.name} {...m} />
          ))}
        </div>
        <p className="mt-10 mb-4 text-sm font-medium text-fd-muted-foreground">For the things your org builds</p>
        <div className="grid gap-px overflow-hidden rounded-xl border bg-fd-border sm:grid-cols-2 lg:grid-cols-3">
          {buildModules.map((m) => (
            <Feature key={m.name} {...m} />
          ))}
        </div>
      </Section>
      <Section
        eyebrow="Compute"
        title="One pod per workshop series, not one per student."
        text="Officers create a pod and schedule its sessions. Platform starts it ten minutes before a session and stops it after, so a stopped pod only bills for disk. Each member gets their own account and folder on it."
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Terminal
            title="member"
            lines={[
              ['$', 'pip install godfather-cli'],
              ['$', 'godfather auth'],
              ['', 'Logged in to robotics'],
              ['$', 'godfather connect'],
              ['', 'Connecting to pod 7kq2x9ab...'],
            ]}
          />
          <Terminal
            title="officer"
            lines={[
              ['', 'POST /api/compute/robotics/pods/7kq2x9ab/sessions'],
              ['', '{'],
              ['', '  "title": "Intro to PyTorch",'],
              ['', '  "start_at": "2026-10-14T18:00:00-07:00",'],
              ['', '  "stop_at": "2026-10-14T20:00:00-07:00"'],
              ['', '}'],
              ['', '201 Created'],
            ]}
          />
        </div>
      </Section>
      <Section
        eyebrow="Agents"
        title="Give an agent scoped access to an org."
        text="Every module exposes its tools through one MCP server and /api/tools. An agent holds a machine token for one organization with only the scopes it needs, and every call is checked and audited."
      >
        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <ul className="space-y-3 text-sm">
            {['knowledge:read', 'agents:write', 'accounts:token', 'compute:connect', 'apps:deploy'].map((scope) => (
              <li key={scope} className="flex items-center gap-3 rounded-lg border bg-fd-card px-4 py-3">
                <Plug className="size-4 text-fd-muted-foreground" />
                <code className="font-mono">{scope}</code>
              </li>
            ))}
          </ul>
          <Terminal
            title="agent"
            lines={[
              ['$', 'curl $API/api/tools/knowledge.search \\'],
              ['', '  -H "Authorization: Bearer plat_..." \\'],
              ['', '  -d \'{"query": "when does Hayden library close"}\''],
              ['', '{"result": {"results": [{"title": "Library hours", ...}]}}'],
            ]}
          />
        </div>
      </Section>
      <Section
        eyebrow="Security"
        title="Built for data you are responsible for."
        text="Student data stays inside the organization it belongs to."
      >
        <div className="grid gap-6 sm:grid-cols-2">
          {guarantees.map((g) => (
            <div key={g.name} className="flex gap-4">
              <g.icon className="mt-0.5 size-5 shrink-0" />
              <div>
                <h3 className="font-medium">{g.name}</h3>
                <p className="mt-1 text-sm text-fd-muted-foreground">{g.text}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>
      <Section
        eyebrow="Self-hosted"
        title="Five processes. Postgres or SQLite."
        text="Run it with containers, or on a single RunPod pod with no Docker. Background work runs on a Procrastinate queue, or in threads on SQLite."
      >
        <div className="overflow-hidden rounded-xl border">
          {processes.map(([name, entry, port]) => (
            <div key={name} className="flex items-center justify-between border-b px-5 py-3 text-sm last:border-b-0">
              <span className="font-medium">{name}</span>
              <span className="flex gap-6 font-mono text-fd-muted-foreground">
                <span>{entry}</span>
                <span className="w-12 text-right">{port}</span>
              </span>
            </div>
          ))}
        </div>
      </Section>
      <CallToAction />
      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div className="grid-bg pointer-events-none absolute inset-0" />
      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pt-24 pb-20 text-center md:pt-32">
        <Link
          href={repoUrl}
          className="mb-8 inline-flex items-center gap-2 rounded-full border bg-fd-background px-3 py-1 text-xs text-fd-muted-foreground transition-colors hover:text-fd-foreground"
        >
          Open source, BSD-3
          <span className="h-3 w-px bg-fd-border" />
          Built at ASU
          <ArrowRight className="size-3" />
        </Link>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-6xl">
          Infrastructure for student organizations
        </h1>
        <p className="mt-6 max-w-2xl text-base text-pretty text-fd-muted-foreground md:text-lg">
          One deployment runs club operations, compute and agent backends for every organization on campus. Each
          organization is a Discord server and switches on only what it uses.
        </p>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/docs/quickstart"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-fd-foreground px-5 text-sm font-medium text-fd-background transition-opacity hover:opacity-85"
          >
            Get started
            <ArrowRight className="size-4" />
          </Link>
          <Link
            href="/docs"
            className="inline-flex h-10 items-center justify-center rounded-lg border bg-fd-background px-5 text-sm font-medium transition-colors hover:bg-fd-accent"
          >
            Read the docs
          </Link>
        </div>
        <div className="mt-16 w-full max-w-3xl text-left">
          <Terminal
            title="platform"
            lines={[
              ['$', 'flask --app main org create --name "Robotics Club" --prefix robotics --guild-id 1290000000000000000'],
              ['', 'Created Robotics Club (id 1, prefix robotics)'],
              ['$', 'flask --app main org modules robotics --off points,storefront'],
              ['', '  modules: points=off, storefront=off, calendar=on, leetcode=on, compute=on'],
            ]}
          />
        </div>
        <p className="mt-10 text-xs text-fd-muted-foreground">
          Runs the Software Developers Association and AI Society at Arizona State University.
        </p>
      </div>
    </section>
  );
}

function Section({
  eyebrow,
  title,
  text,
  children,
}: {
  eyebrow: string;
  title: string;
  text: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b">
      <div className="mx-auto max-w-5xl px-6 py-20 md:py-28">
        <p className="font-mono text-xs tracking-wider text-fd-muted-foreground uppercase">{eyebrow}</p>
        <h2 className="mt-3 max-w-2xl text-2xl font-semibold tracking-tight text-balance md:text-4xl">{title}</h2>
        <p className="mt-4 max-w-2xl text-fd-muted-foreground text-pretty">{text}</p>
        <div className="mt-12">{children}</div>
      </div>
    </section>
  );
}

function Feature({ icon: Icon, name, text }: { icon: typeof Cpu; name: string; text: string }) {
  return (
    <div className="bg-fd-background p-6">
      <Icon className="size-5" />
      <h3 className="mt-4 font-medium">{name}</h3>
      <p className="mt-2 text-sm text-fd-muted-foreground">{text}</p>
    </div>
  );
}

function Terminal({ title, lines }: { title: string; lines: [string, string][] }) {
  return (
    <div className="overflow-hidden rounded-xl border bg-fd-card shadow-sm">
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-fd-border" />
        <span className="size-2.5 rounded-full bg-fd-border" />
        <span className="size-2.5 rounded-full bg-fd-border" />
        <span className="ml-2 font-mono text-xs text-fd-muted-foreground">{title}</span>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-6">
        {lines.map(([prompt, text], i) => (
          <div key={i} className={prompt ? '' : 'text-fd-muted-foreground'}>
            {prompt ? <span className="mr-2 select-none text-fd-muted-foreground">{prompt}</span> : null}
            {text}
          </div>
        ))}
      </pre>
    </div>
  );
}

function CallToAction() {
  return (
    <section className="border-b">
      <div className="mx-auto flex max-w-5xl flex-col items-start gap-6 px-6 py-20 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">Run it for your organization.</h2>
          <p className="mt-2 text-fd-muted-foreground">Free and open source. Bring a Discord server.</p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/docs/quickstart"
            className="inline-flex h-10 items-center rounded-lg bg-fd-foreground px-5 text-sm font-medium text-fd-background hover:opacity-85"
          >
            Quickstart
          </Link>
          <Link
            href={repoUrl}
            className="inline-flex h-10 items-center rounded-lg border px-5 text-sm font-medium hover:bg-fd-accent"
          >
            GitHub
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-6 py-10 text-xs text-fd-muted-foreground sm:flex-row sm:justify-between">
      <span>Platform. Based on the platform of the Software Developers Association at ASU.</span>
      <span className="flex gap-4">
        <Link href="/docs" className="hover:text-fd-foreground">
          Docs
        </Link>
        <Link href={repoUrl} className="hover:text-fd-foreground">
          GitHub
        </Link>
        <Link href={`${repoUrl}/blob/main/LICENSE`} className="hover:text-fd-foreground">
          License
        </Link>
      </span>
    </footer>
  );
}
