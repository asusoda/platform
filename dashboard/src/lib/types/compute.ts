// Compute pods, sessions and files.

// A pod with its live RunPod status. machine is RunPod's machine object, passed through as is.
export type Pod = {
  id: string;
  name: string;
  status: string | null;
  is_public: boolean;
  allowed_users: string[];
  created_by: string | null;
  created_at: string | null;
  machine: Record<string, unknown> | null;
  cost_per_hour: number | string | null;
};

export type NewPod = {
  name?: string;
  image_name?: string;
  use_cpu_only: boolean;
  gpu_type_id?: string;
  cpu_flavor?: string;
  vcpu_count?: number;
  cloud_type: 'COMMUNITY' | 'SECURE';
  volume_in_gb: number;
  container_disk_in_gb: number;
  volume_mount_path: string;
  env: Record<string, string>;
  is_public: boolean;
  allowed_users: string[];
};

export type PodSession = {
  id: number;
  pod_id: string;
  title: string | null;
  start_at: string;
  stop_at: string;
  started: boolean;
  finished: boolean;
  created_by: string | null;
};

// An entry of a pod folder. modified is in Unix seconds.
export type PodFile = {
  name: string;
  type: 'directory' | 'file';
  size: number;
  modified: number;
  permissions: string;
};

// A member of the org named by Discord id. name is null when the member directory does not know it.
export type PodPerson = { discord_id: string; name: string | null };

// A certificate issued for a pod. username is the member's folder on the pod.
export type PodConnection = PodPerson & { username: string; is_admin: boolean; created_at: string | null };

// Who may connect to a pod and who got a certificate for it, newest first.
export type PodMembers = {
  pod_id: string;
  access: { is_public: boolean; allowed: PodPerson[] };
  recent: PodConnection[];
};

// A live SSH session on a pod. discord_id is null when no certificate for the pod has its username.
export type PodLiveSession = {
  username: string;
  is_admin: boolean;
  seconds: number;
  discord_id: string | null;
  name: string | null;
};

// The live sessions on a pod. When state is unknown, reason says why and sessions is empty.
export type PodConnected = {
  pod_id: string;
  state: 'known' | 'unknown';
  reason: string | null;
  sessions: PodLiveSession[];
};
