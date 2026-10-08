// A current problem of the org. resolved_at is set when an officer marked it resolved.
export type Notification = {
  id: string;
  module: string;
  subject: string;
  message: string;
  // The org page that fixes the problem, relative to /<org>/.
  link: string;
  resolved_at: string | null;
  resolved_by: string | null;
};

export type NotificationList = { notifications: Notification[]; open: number };
