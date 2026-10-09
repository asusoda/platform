// Points members and entries.

// A member of the org with their total, from GET /api/points/<org>/users.
export type PointsMember = {
  id: number;
  uuid: string;
  name: string | null;
  username: string | null;
  email: string | null;
  asu_id: string | null;
  academic_standing: string | null;
  major: string | null;
  discord_linked: boolean;
  points: number;
  joined_at: string | null;
  created_at: string | null;
};

// One point entry. Negative points pay for a store order.
export type PointEntry = {
  id: number;
  points: number;
  event: string | null;
  awarded_by_officer: string | null;
  timestamp: string | null;
  last_updated: string | null;
  user_id: number;
  organization_id: number;
};

export type PointsHistory = {
  user: { id: number; name: string | null; email: string | null; username: string | null };
  total_points: number;
  points_history: Omit<PointEntry, 'user_id' | 'organization_id'>[];
};
