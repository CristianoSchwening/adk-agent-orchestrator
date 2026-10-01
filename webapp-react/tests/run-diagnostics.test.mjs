import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true, watch: null, hmr: false } })
after(() => server.close())
const { RunDiagnostics } = await server.ssrLoadModule('/src/components/layout/RunDiagnostics.tsx')

const task = {
  task_id: 'TASK-1', status: 'failed', attempt: 1,
  error: 'replan:acceptance_criteria_failed', result: null,
  output_status: 'present', execution_output: '<script>unsafe()</script>',
  evaluation: {
    trigger: 'acceptance_criteria_failed', rationale: 'Falta uma fonte verificável',
    criteria_catalog: [{ criterion_id: 'source', text: 'Incluir fonte' }],
    criteria: [{ criterion_id: 'source', status: 'failed', rationale: 'Sem citação', evidence: 'Texto sem fonte' }],
  },
}
const run = { run_id: 'RUN-1', plan_id: 'PLAN-1', status: 'failed', tasks: [task] }
const render = contract => renderToStaticMarkup(React.createElement(RunDiagnostics, { contract }))

test('renders rejected criteria, escaped output and terminal limit', () => {
  const html = render({ task_run: { ...run, terminal_error: { code: 'replan_limit_exhausted', used: 2, limit: 2 } } })
  for (const text of ['Conteúdo reprovado', 'Incluir fonte', 'Sem citação', 'Texto sem fonte', '2 de 2']) assert.ok(html.includes(text))
  assert.ok(html.includes('&lt;script&gt;unsafe()&lt;/script&gt;'))
  assert.ok(!html.includes('<script>'))
  assert.ok(html.includes('Ver conteúdo produzido'))
})

test('legacy null results are not labeled empty', () => {
  const html = render({ task_run: { ...run, tasks: [{ task_id: 'OLD', status: 'failed', result: null, attempt: 1 }] } })
  assert.ok(html.includes('Diagnóstico não registrado.'))
  assert.ok(html.includes('Conteúdo não registrado'))
  assert.ok(!html.includes('Saída vazia'))
})

test('shows history, evaluator failures and empty or absent outputs distinctly', () => {
  const html = render({ task_run_history: [run], task_run: {
    ...run, run_id: 'RUN-2', tasks: [
      { ...task, task_id: 'EMPTY', output_status: 'empty', execution_output: '', evaluation: null, error: 'evaluation_failed', evaluation_error: 'Invalid JSON' },
      { ...task, task_id: 'ABSENT', output_status: 'absent', execution_output: null },
    ],
  } })
  for (const text of ['RUN-1', 'RUN-2', 'Erro do avaliador', 'Invalid JSON', 'Saída vazia', 'Saída ausente']) assert.ok(html.includes(text))
})
