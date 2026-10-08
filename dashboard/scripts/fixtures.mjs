// API responses for a fictional org, used by screenshots.mjs. Every name, id and token here is made up.

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const ORG = { id: 1, name: 'Robotics Club', prefix: 'robotics', guild_id: '1290000000000000000', icon_url: null };

export const BRANDING = { logo_url: null, accent_color: '#2563eb' };

const MODULES = [
  { name: 'points', description: 'Points, leaderboards and event check-ins', enabled: true },
  { name: 'storefront', description: 'Merch store paid with points', enabled: false },
  { name: 'calendar', description: 'Notion to Google Calendar sync and the public events feed', enabled: true },
  { name: 'leetcode', description: "Daily LeetCode post in the org's channel, with solve checks", enabled: false },
  { name: 'compute', description: "GPU and CPU pods on the org's RunPod account that members SSH into", enabled: true },
  { name: 'alerts', description: 'Job and hackathon listings posted to Discord webhooks', enabled: true },
];

const SCOPES = {
  'knowledge:read': "Search the organization's knowledge and public sources",
  'knowledge:write': "Write and delete the organization's knowledge sources",
  'agents:read': 'Read conversations, memories and profiles of members the agent talks to',
  'agents:write': 'Write conversations, memories, profiles and pending actions for members',
  'calendar:read': "Read the org's upcoming events",
  'points:read': "Read the org's points leaderboard (names and totals, no emails or student IDs)",
  'apps:read': 'List apps on RunPod, their pods and deployments',
  'apps:deploy': 'Deploy a new image tag of an app',
};

// All responses, with times relative to now so the dashboard shows "2h ago" and "in 3d".
export function fixtures(now = Date.now()) {
  const at = (offset) => new Date(now + offset).toISOString();

  const tokens = [
    {
      id: 11,
      name: 'club-assistant',
      kind: 'agent',
      scopes: ['knowledge:read', 'agents:read', 'agents:write', 'calendar:read'],
      display: 'plat_4hQ2',
      created_by: 'officer',
      created_at: at(-40 * DAY),
      expires_at: null,
      last_used_at: at(-3 * MINUTE),
    },
    {
      id: 12,
      name: 'rover-deploy',
      kind: 'app',
      scopes: ['apps:read', 'apps:deploy'],
      display: 'plat_9xLm',
      created_by: 'officer',
      created_at: at(-25 * DAY),
      expires_at: null,
      last_used_at: at(-5 * HOUR),
    },
    {
      id: 13,
      name: 'workshop-helper',
      kind: 'agent',
      scopes: ['knowledge:read', 'points:read'],
      display: 'plat_Tb7c',
      created_by: 'officer',
      created_at: at(-12 * DAY),
      expires_at: null,
      last_used_at: at(-26 * HOUR),
    },
    {
      id: 14,
      name: 'docs-sync',
      kind: 'app',
      scopes: ['knowledge:write'],
      display: 'plat_e2Rw',
      created_by: 'officer',
      created_at: at(-60 * DAY),
      expires_at: null,
      last_used_at: at(-2 * DAY),
    },
  ];

  const audit = (id, offset, action, rest = {}) => ({
    id,
    created_at: at(offset),
    source: 'http',
    action,
    org: 'robotics',
    actor_kind: 'officer',
    actor_id: '1290000000000000101',
    status: 200,
    details: null,
    ...rest,
  });

  const activity = [
    audit(212, -12 * MINUTE, 'PUT /api/organizations/<int:org_id>/modules'),
    audit(211, -48 * MINUTE, 'POST /api/compute/<prefix>/pods/<pod_id>/sessions', { status: 201 }),
    audit(210, -2 * HOUR, 'POST /api/apps/<name>/deploy', { actor_kind: 'token', actor_id: 'rover-deploy', status: 202 }),
    audit(209, -3 * HOUR, 'PUT /api/alerts/<prefix>/feeds/<key>'),
    audit(208, -6 * HOUR, 'POST /api/organizations/<int:org_id>/tokens', { status: 201 }),
    audit(207, -9 * HOUR, 'PUT /api/dashboard/<prefix>/branding'),
    audit(206, -26 * HOUR, 'POST /api/points/<prefix>/import', { status: 201 }),
    audit(205, -2 * DAY, 'PUT /api/organizations/<int:org_id>/secrets/<name>'),
  ];

  const job = (id, offset, name, result) =>
    audit(id, offset, `job ${name}`, { source: 'job', actor_kind: 'job', actor_id: null, status: null, details: { result } });

  const jobs = [
    job(320, -4 * MINUTE, 'alerts.run_feeds', 'posted 3'),
    job(319, -35 * MINUTE, 'compute.run_schedules', 'started 1 pod'),
    job(318, -61 * MINUTE, 'auth.clean_tokens', 'ran'),
    job(317, -2 * HOUR, 'calendar.sync', 'synced 14 events'),
    job(316, -5 * HOUR, 'knowledge.crawl', 'failed'),
    job(315, -7 * HOUR, 'alerts.run_feeds', 'posted 1'),
  ];

  const pods = [
    { pod_id: '7kq2x9ab', name: 'Workshop GPU (A40)', public: true },
    { pod_id: 'm3v8c1tz', name: 'Rover vision training', public: false },
    { pod_id: 'q9w4e2rd', name: 'Simulation (CPU)', public: false },
  ];

  const sessions = [
    { pod_id: '7kq2x9ab', title: 'Intro to PyTorch', start_at: at(2 * DAY + 3 * HOUR), stop_at: at(2 * DAY + 5 * HOUR) },
    { pod_id: 'q9w4e2rd', title: 'ROS 2 navigation lab', start_at: at(4 * DAY + 2 * HOUR), stop_at: at(4 * DAY + 5 * HOUR) },
    { pod_id: '7kq2x9ab', title: 'Object detection with YOLO', start_at: at(9 * DAY), stop_at: at(9 * DAY + 2 * HOUR) },
    { pod_id: 'm3v8c1tz', title: 'Vision team training run', start_at: at(11 * DAY), stop_at: at(11 * DAY + 8 * HOUR) },
  ];

  const feeds = [
    {
      key: 'internships',
      kind: 'github_jobs',
      config: { repo: 'example-org/summer-internships', label: 'Internship' },
      every_hours: 3,
      enabled: true,
      webhook_set: true,
      seeded_at: at(-30 * DAY),
      last_run_at: at(-4 * MINUTE),
      last_error: null,
      posted: 186,
    },
    {
      key: 'hackathons',
      kind: 'hackathons',
      config: {},
      every_hours: 24,
      enabled: true,
      webhook_set: true,
      seeded_at: at(-30 * DAY),
      last_run_at: at(-7 * HOUR),
      last_error: null,
      posted: 41,
    },
    {
      key: 'new-grad',
      kind: 'github_jobs',
      config: { repo: 'example-org/new-grad-roles', label: 'New grad' },
      every_hours: 6,
      enabled: false,
      webhook_set: true,
      seeded_at: at(-90 * DAY),
      last_run_at: at(-20 * DAY),
      last_error: null,
      posted: 73,
    },
  ];

  const run = (title, workflow, branch, event, conclusion, offset, status = 'completed') => ({
    workflow,
    branch,
    event,
    status,
    conclusion,
    title,
    url: null,
    started_at: at(offset),
  });

  const ci = {
    repos: [
      {
        repo: 'robotics-club/rover-firmware',
        error: null,
        runs: [
          run('Tune PID gains for the drive motors', 'build', 'main', 'push', 'success', -25 * MINUTE),
          run('Add IMU calibration step', 'build', 'imu-calibration', 'pull_request', null, -6 * MINUTE, 'in_progress'),
        ],
      },
      {
        repo: 'robotics-club/website',
        error: null,
        runs: [run('Update the build season schedule', 'deploy', 'main', 'push', 'success', -3 * HOUR)],
      },
      {
        repo: 'robotics-club/match-scout',
        error: null,
        runs: [run('Bump the model version', 'test', 'main', 'push', 'failure', -9 * HOUR)],
      },
    ],
  };

  const overview = {
    organization: { id: ORG.id, name: ORG.name, prefix: ORG.prefix, branding: BRANDING },
    modules: MODULES,
    sections: {
      members: { total: 214 },
      points: { total: 18420, last_30_days: 2310 },
      storefront: { products: 12, pending_orders: 3 },
      compute: { pods, sessions },
      alerts: {
        feeds: feeds.map((f, i) => ({
          key: f.key,
          kind: f.kind,
          enabled: f.enabled,
          every_hours: f.every_hours,
          last_run_at: f.last_run_at,
          last_error: f.last_error,
          posted_7_days: [14, 3, 0][i],
        })),
      },
      apps: {
        apps: [
          { name: 'rover-telemetry', repo: 'robotics-club/rover-telemetry', tag: 'v1.8.2', status: 'healthy', deployed_at: at(-2 * HOUR), error: null },
          { name: 'parts-inventory', repo: 'robotics-club/parts-inventory', tag: 'v0.4.0', status: 'healthy', deployed_at: at(-6 * DAY), error: null },
          { name: 'match-scout', repo: 'robotics-club/match-scout', tag: 'v2.0.0-rc1', status: 'deploying', deployed_at: at(-3 * MINUTE), error: null },
        ],
      },
      knowledge: { sources: 18, crawled: 6, failing: [] },
      agents: { conversations: 1290, active_7_days: 342, members_7_days: 87, memories: 2140, pending_actions: 2 },
      accounts: { linked: { google: 41, canvas: 36, microsoft: 12 } },
      tokens: {
        tokens: tokens.map(({ name, kind, scopes, last_used_at }) => ({ name, kind, scopes, last_used_at })),
        cli_tokens: 58,
      },
    },
    problems: [],
    activity,
    jobs,
    generated_at: at(-20 * 1000),
  };

  const secret = (name, description, setOffset) => ({
    name,
    description,
    set: setOffset !== null,
    updated_at: setOffset === null ? null : at(setOffset),
    updated_by: setOffset === null ? null : '1290000000000000101',
  });

  return {
    '/api/organizations/': [ORG],
    [`/api/dashboard/${ORG.prefix}/branding`]: BRANDING,
    [`/api/dashboard/${ORG.prefix}/overview`]: overview,
    [`/api/dashboard/${ORG.prefix}/ci`]: ci,
    [`/api/alerts/${ORG.prefix}/feeds`]: { feeds },
    [`/api/organizations/${ORG.id}/tokens`]: { tokens, scopes: SCOPES },
    [`/api/organizations/${ORG.id}/audit`]: { entries: [...activity, ...jobs].sort((a, b) => b.id - a.id) },
    [`/api/organizations/${ORG.id}/modules`]: { modules: MODULES },
    [`/api/organizations/${ORG.id}/secrets`]: {
      configured: true,
      secrets: [
        secret('github_token', "GitHub token that can read the contents of the org's private app repos", -8 * DAY),
        secret('google_service_account', "Google service account key (JSON) that owns this org's calendar", -30 * DAY),
        secret('notion_api_key', "Notion integration token for this org's events database", -30 * DAY),
        secret('runpod_api_key', "RunPod API key the org's apps are deployed and billed with", -45 * DAY),
      ],
    },
  };
}
