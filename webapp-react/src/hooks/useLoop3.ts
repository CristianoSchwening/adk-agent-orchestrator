import { useState, useEffect, useCallback, useRef } from 'react'
import type { Loop3Config, ScheduleConfig, ExecutionSummary } from '@/types/loop3'

const POLL_MS = 3000  // poll history every 3s when schedule is active

export function useLoop3() {
  const [config, setConfig]   = useState<Loop3Config | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/loop3/config')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: Loop3Config = await res.json()
      setConfig(data)
      return data
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return null
    }
  }, [])

  const trigger = useCallback(async (objective: string, workflow: string): Promise<ExecutionSummary | null> => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/loop3/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective, workflow }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const summary: ExecutionSummary = await res.json()
      await fetchConfig()
      return summary
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return null
    } finally {
      setLoading(false)
    }
  }, [fetchConfig])

  const setSchedule = useCallback(async (cfg: Omit<ScheduleConfig, 'created_at' | 'next_run_at'>) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/loop3/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchConfig()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [fetchConfig])

  const stopSchedule = useCallback(async () => {
    try {
      await fetch('/api/loop3/schedule', { method: 'DELETE' })
      await fetchConfig()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [fetchConfig])

  // Initial fetch
  useEffect(() => { fetchConfig() }, [fetchConfig])

  // Poll while schedule is active
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (config?.schedule?.active) {
      pollRef.current = setInterval(fetchConfig, POLL_MS)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [config?.schedule?.active, fetchConfig])

  return { config, loading, error, fetchConfig, trigger, setSchedule, stopSchedule }
}
