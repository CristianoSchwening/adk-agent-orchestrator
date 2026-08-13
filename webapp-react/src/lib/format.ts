export function formatDuration(milliseconds?: number | null) {
  if (milliseconds == null) return '—'
  if (milliseconds < 1000) return `${milliseconds} ms`
  const seconds = milliseconds / 1000
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`
}

export function formatTime(iso?: string | null) {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function humanizeStatus(status?: string | null) {
  const labels: Record<string, string> = {
    completed: 'Concluída', running: 'Em execução', failed: 'Falhou', pending: 'Pendente',
    published: 'Publicada', superseded: 'Substituída', draft: 'Rascunho',
  }
  return labels[status ?? ''] ?? status ?? 'Desconhecido'
}
