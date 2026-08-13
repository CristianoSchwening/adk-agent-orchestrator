export interface WorkflowOption {
  value: string
  label: string
  description: string
}

export const WORKFLOW_OPTIONS: WorkflowOption[] = [
  { value: 'loop2_verification', label: 'Verificação iterativa', description: 'Executa, avalia e refina até atingir o nível de qualidade esperado.' },
  { value: 'progressive_multi_agent_response', label: 'Resposta multiagente', description: 'Publica contribuições progressivas de especialistas coordenados.' },
  { value: 'sequential', label: 'Sequencial', description: 'Processa as etapas em uma cadeia ordenada.' },
  { value: 'parallel', label: 'Paralelo', description: 'Distribui o trabalho entre especialistas simultaneamente.' },
  { value: 'review_critic', label: 'Revisão crítica', description: 'Submete a execução à revisão de um agente crítico.' },
  { value: 'iterative_refinement', label: 'Refinamento iterativo', description: 'Melhora progressivamente a resposta em ciclos controlados.' },
]

export const AUTOMATION_WORKFLOWS = WORKFLOW_OPTIONS.filter(({ value }) =>
  ['loop2_verification', 'progressive_multi_agent_response', 'sequential'].includes(value),
)

export const DEFAULT_WORKFLOW = WORKFLOW_OPTIONS[0].value

export function workflowLabel(value?: string | null) {
  return WORKFLOW_OPTIONS.find((workflow) => workflow.value === value)?.label ?? value ?? 'Automático'
}
