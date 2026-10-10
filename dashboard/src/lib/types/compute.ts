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
