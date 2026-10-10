export function readStoredValue(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

export function writeStoredValue(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch { /* The conversation still works when browser storage is unavailable. */ }
}
