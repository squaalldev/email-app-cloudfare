export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export const apiUrl = (path: string) => {
  if (!API_BASE) return path;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE}${path}`;
};
