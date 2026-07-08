import { useCallback, useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'nb-theme'

/* Resolve the initial theme. The inline script in index.html sets
 * document.documentElement.dataset.theme before React mounts (to prevent a
 * flash), so prefer that. Fall back to localStorage, then dark (the default —
 * the leadership-room read). */
function resolveInitial(): Theme {
  if (typeof document !== 'undefined') {
    const attr = document.documentElement.dataset.theme
    if (attr === 'dark' || attr === 'light') return attr
  }
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light') return stored
  }
  return 'dark'
}

interface UseTheme {
  theme: Theme
  toggle: () => void
  setTheme: (t: Theme) => void
}

export function useTheme(): UseTheme {
  const [theme, setThemeState] = useState<Theme>(resolveInitial)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* storage may be unavailable (private mode); the DOM attr still drives CSS */
    }
  }, [theme])

  const setTheme = useCallback((t: Theme) => setThemeState(t), [])
  const toggle = useCallback(() => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')), [])

  return { theme, toggle, setTheme }
}
