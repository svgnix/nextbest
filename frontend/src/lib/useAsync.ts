import { useCallback, useEffect, useState } from 'react'

export type AsyncState<T> = {
  data: T | null
  status: 'loading' | 'ready' | 'error'
  reload: () => void
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  const run = useCallback(() => {
    let alive = true
    setStatus('loading')
    fn()
      .then((d) => {
        if (!alive) return
        setData(d)
        setStatus('ready')
      })
      .catch(() => alive && setStatus('error'))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => run(), [run])

  return { data, status, reload: run }
}
