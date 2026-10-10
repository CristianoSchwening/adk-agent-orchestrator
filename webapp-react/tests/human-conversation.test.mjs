import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true, watch: null, hmr: false } })
after(() => server.close())
const { HumanRequestMessage } = await server.ssrLoadModule('/src/components/progressive/HumanRequestMessage.tsx')
const request = { request_id: 'request-1', status: 'pending', kind: 'approval',
  message: 'Você aprova?', candidate: '<script>unsafe()</script>', criteria: ['Critério concreto'],
  created_at: '2026-10-09T18:00:00Z' }
const render = (props = {}) => renderToStaticMarkup(React.createElement(HumanRequestMessage,
  { request, onHumanResponse: async () => true, ...props }))

test('pending decision is a conversation message with candidate, criteria and response actions', () => {
  const html = render()
  for (const label of ['Aguardando sua resposta', 'Você aprova?', 'Critério concreto',
    'Aprovar', 'Solicitar alterações', 'Rejeitar', 'Sua resposta']) assert.ok(html.includes(label))
  assert.ok(html.includes('&lt;script&gt;unsafe()&lt;/script&gt;'))
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('role="dialog"'))
})

test('clarification provides a text response and no approval actions', () => {
  const html = render({ request: { ...request, kind: 'clarification' } })
  assert.ok(html.includes('Enviar resposta'))
  assert.ok(!html.includes('Solicitar alterações'))
  assert.ok(!html.includes('Rejeitar'))
})

test('answered request shows the human message without actionable controls', () => {
  const html = render({ request: { ...request, status: 'answered',
    response: { decision: 'needs_changes', comment: 'Troque a data.', source: 'human' } } })
  assert.ok(html.includes('Você · Alterações solicitadas'))
  assert.ok(html.includes('Troque a data.'))
  assert.ok(!html.includes('<textarea'))
  assert.ok(!html.includes('<button'))
})

test('sending disables decisions and displays network errors inline', () => {
  const html = render({ sending: true, responseError: 'Não foi possível enviar.' })
  assert.ok(html.includes('Retomando') || html.includes('retomando'))
  assert.ok(html.includes('disabled'))
  assert.ok(html.includes('role="alert"'))
  assert.ok(html.includes('Não foi possível enviar.'))
})
