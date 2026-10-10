// Path helpers for the pod file manager. Paths are absolute POSIX paths.

export const joinPath = (directory, name) => (directory === "/" ? `/${name}` : `${directory}/${name}`);

export const parentPath = (path) => {
  const trimmed = path.replace(/\/+$/, "");
  const cut = trimmed.lastIndexOf("/");
  return cut <= 0 ? "/" : trimmed.slice(0, cut);
};

export const crumbs = (path) => {
  const parts = path.split("/").filter(Boolean);
  return [{ name: "/", path: "/" }, ...parts.map((name, i) => ({ name, path: `/${parts.slice(0, i + 1).join("/")}` }))];
};

export const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
};
