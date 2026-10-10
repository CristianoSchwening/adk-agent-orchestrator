import { useState, useCallback, useEffect, useRef } from 'react'
import type { ExecutionContractDTO, HumanDecision } from '@/types/contract'
import { readStoredValue, writeStoredValue } from '@/lib/storage'

interface UseContractReturn {
  contract: ExecutionContractDTO | null
  loading: boolean
  error: string | null
  loadDemo: (objective: string, workflow: string) => Promise<void>
  run: (objective: string, kevMode: 'off' | 'decision') => Promise<void>
  retry: () => Promise<void>
  clear: () => void
  sending: boolean
  responseError: string | null
  respondToHumanRequest: (requestId: string, decision: HumanDecision, comment: string,
                         key: string) => Promise<boolean>
}

interface RequestSnapshot {
  url: string
  objective: string
  workflow: string
  kevMode?: 'off' | 'decision'
}

export function useContract(): UseContractReturn {
  const [contract, setContract] = useState<ExecutionContractDTO | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [responseError, setResponseError] = useState<string | null>(null)
  const sendingRef = useRef(false)
  const activeRunRef = useRef<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const lastRequestRef = useRef<RequestSnapshot | null>(null)
  const acceptContract = useCallback((data: ExecutionContractDTO) => {
    setContract(current => current?.run_id === data.run_id &&
      Date.parse(current?.task.updated_at ?? '') > Date.parse(data.task.updated_at ?? '') ? current : data)
    activeRunRef.current = data.run_id ?? null
    writeStoredValue('adk-active-run', data.run_id ?? null)
  }, [])

  const post = useCallback(async (
    url: string,
    objective: string,
    workflow: string,
    kevMode?: 'off' | 'decision',
  ) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    lastRequestRef.current = { url, objective, workflow, kevMode }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective, workflow, ...(kevMode ? { kev_mode: kevMode } : {}) }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const message = await res.text()
        throw new Error(message || `HTTP ${res.status}: ${res.statusText}`)
      }
      const data: ExecutionContractDTO = await res.json()
      if (!controller.signal.aborted) acceptContract(data)
    } catch (e) {
      if (controller.signal.aborted) return
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (controllerRef.current === controller) setLoading(false)
    }
  }, [acceptContract])

  const respondToHumanRequest = useCallback(async (
    requestId: string, decision: HumanDecision, comment: string, key: string,
  ) => {
    const runId = activeRunRef.current
    if (!runId || sendingRef.current) return false
    sendingRef.current = true
    setSending(true)
    setResponseError(null)
    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/human-requests/${encodeURIComponent(requestId)}/response`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comment, idempotency_key: key }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: ExecutionContractDTO = await res.json()
      if (activeRunRef.current === runId) acceptContract(data)
      return true
    } catch (e) {
      if (activeRunRef.current === runId) setResponseError(e instanceof Error ? e.message : String(e))
      return false
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }, [acceptContract])

  const loadDemo = useCallback(
    (objective: string, workflow: string) => post('/api/run/demo', objective, workflow),
    [post],
  )

  const run = useCallback(
    (objective: string, kevMode: 'off' | 'decision') => post('/api/run', objective, 'auto', kevMode),
    [post],
  )

  const retry = useCallback(async () => {
    const request = lastRequestRef.current
    if (request) await post(request.url, request.objective, request.workflow, request.kevMode)
  }, [post])

  const clear = useCallback(() => {
    controllerRef.current?.abort()
    setContract(null)
    setError(null)
    setLoading(false)
    activeRunRef.current = null
    writeStoredValue('adk-active-run', null)
    setResponseError(null)
  }, [])

  useEffect(() => () => controllerRef.current?.abort(), [])

  useEffect(() => {
    const runId = readStoredValue('adk-active-run')
    if (!runId) return
    const controller = new AbortController()
    activeRunRef.current = runId
    fetch(`/api/runs/${encodeURIComponent(runId)}`, { signal: controller.signal })
      .then(async res => {
        if (!res.ok) throw new Error('Não foi possível recuperar a execução salva.')
        const data: ExecutionContractDTO = await res.json()
        if (!controller.signal.aborted && activeRunRef.current === runId) acceptContract(data)
      }).catch(e => { if (!controller.signal.aborted) setError(String(e)) })
    return () => controller.abort()
  }, [acceptContract])

  useEffect(() => {
    const runId = contract?.run_id
    if (!runId || loading || !['running', 'awaiting_human'].includes(contract.task.status)) return
    const controller = new AbortController()
    const timer = setInterval(async () => {
      if (sendingRef.current) return
      try {
        const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { signal: controller.signal })
        if (res.ok) {
          const data: ExecutionContractDTO = await res.json()
          if (!controller.signal.aborted && !sendingRef.current && activeRunRef.current === runId) acceptContract(data)
        }
      } catch { /* Preserve the pending message while offline. */ }
    }, 3000)
    return () => { clearInterval(timer); controller.abort() }
  }, [contract?.run_id, contract?.task.status, loading, acceptContract])

  return { contract, loading, error, loadDemo, run, retry, clear,
           sending, responseError, respondToHumanRequest }
}
