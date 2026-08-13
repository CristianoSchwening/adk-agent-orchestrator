import { useState, useCallback, useEffect, useRef } from 'react'
import type { ExecutionContractDTO } from '@/types/contract'

interface UseContractReturn {
  contract: ExecutionContractDTO | null
  loading: boolean
  error: string | null
  loadDemo: (objective: string, workflow: string) => Promise<void>
  run: (objective: string, workflow: string) => Promise<void>
  retry: () => Promise<void>
  clear: () => void
}

interface RequestSnapshot {
  url: string
  objective: string
  workflow: string
}

export function useContract(): UseContractReturn {
  const [contract, setContract] = useState<ExecutionContractDTO | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const lastRequestRef = useRef<RequestSnapshot | null>(null)

  const post = useCallback(async (url: string, objective: string, workflow: string) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    lastRequestRef.current = { url, objective, workflow }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective, workflow }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const message = await res.text()
        throw new Error(message || `HTTP ${res.status}: ${res.statusText}`)
      }
      const data: ExecutionContractDTO = await res.json()
      setContract(data)
    } catch (e) {
      if (controller.signal.aborted) return
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (controllerRef.current === controller) setLoading(false)
    }
  }, [])

  const loadDemo = useCallback(
    (objective: string, workflow: string) => post('/api/run/demo', objective, workflow),
    [post],
  )

  const run = useCallback(
    (objective: string, workflow: string) => post('/api/run', objective, workflow),
    [post],
  )

  const retry = useCallback(async () => {
    const request = lastRequestRef.current
    if (request) await post(request.url, request.objective, request.workflow)
  }, [post])

  const clear = useCallback(() => {
    controllerRef.current?.abort()
    setContract(null)
    setError(null)
    setLoading(false)
  }, [])

  useEffect(() => () => controllerRef.current?.abort(), [])

  return { contract, loading, error, loadDemo, run, retry, clear }
}
