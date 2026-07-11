import { useState, useCallback } from 'react'
import type { ExecutionContractDTO } from '@/types/contract'

interface UseContractReturn {
  contract: ExecutionContractDTO | null
  loading: boolean
  error: string | null
  loadDemo: (objective: string, workflow: string) => Promise<void>
  run: (objective: string, workflow: string) => Promise<void>
}

export function useContract(): UseContractReturn {
  const [contract, setContract] = useState<ExecutionContractDTO | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const post = useCallback(async (url: string, objective: string, workflow: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective, workflow }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: ExecutionContractDTO = await res.json()
      setContract(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
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

  return { contract, loading, error, loadDemo, run }
}
