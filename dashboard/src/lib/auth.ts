// Platform access and refresh tokens, kept in localStorage.

const ACCESS = 'platform.access_token';
const REFRESH = 'platform.refresh_token';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage blocked: the session lasts until the tab closes
  }
}

export const tokens = {
  access: () => read(ACCESS),
  refresh: () => read(REFRESH),
  set(access: string, refresh?: string) {
    write(ACCESS, access);
    if (refresh) write(REFRESH, refresh);
  },
  clear() {
    write(ACCESS, null);
    write(REFRESH, null);
  },
};
