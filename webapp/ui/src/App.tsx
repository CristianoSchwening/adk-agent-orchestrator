import { useState } from 'react'
import { Bot, BrainCircuit, FileUp, GlobeIcon, Sparkles } from 'lucide-react'
import {
  Attachment,
  AttachmentInfo,
  AttachmentPreview,
  AttachmentRemove,
  Attachments,
} from '@/components/ai-elements/attachments'
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionAddScreenshot,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputHeader,
  type PromptInputMessage,
  PromptInputSelect,
  PromptInputSelectContent,
  PromptInputSelectItem,
  PromptInputSelectTrigger,
  PromptInputSelectValue,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
} from '@/components/ai-elements/prompt-input'
import './App.css'

const models = [
  { id: 'orchestrator-pro', name: 'Orchestrator Pro' },
  { id: 'research-swarm', name: 'Research Swarm' },
  { id: 'code-reviewer', name: 'Code Reviewer' },
]

const capabilities = [
  'Attach PDFs, logs, screenshots, and specs as agent context',
  'Route prompts with the selected model profile and tools',
  'Keep multiline drafting, Enter-to-send, and Shift+Enter support',
]

function PromptInputAttachmentsDisplay() {
  const attachments = usePromptInputAttachments()

  if (attachments.files.length === 0) {
    return null
  }

  return (
    <Attachments variant="inline" className="max-h-28 overflow-y-auto">
      {attachments.files.map((attachment) => (
        <Attachment
          data={attachment}
          key={attachment.id}
          onRemove={() => attachments.remove(attachment.id)}
        >
          <AttachmentPreview />
          <AttachmentInfo showMediaType />
          <AttachmentRemove />
        </Attachment>
      ))}
    </Attachments>
  )
}

function App() {
  const [model, setModel] = useState(models[0].id)
  const [webSearch, setWebSearch] = useState(false)
  const [messages, setMessages] = useState<PromptInputMessage[]>([])
  const [status, setStatus] = useState<'ready' | 'submitted'>('ready')

  const handleSubmit = (message: PromptInputMessage) => {
    if (!message.text && !message.files?.length) return

    setStatus('submitted')
    setMessages((current) => [message, ...current].slice(0, 3))
    window.setTimeout(() => setStatus('ready'), 650)
  }

  const selectedModel = models.find((item) => item.id === model)?.name ?? models[0].name

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="eyebrow">
          <Sparkles className="size-4" />
          Estágio 4 — AI Elements PromptInput
        </div>
        <div className="hero-grid">
          <div className="hero-copy">
            <h1>Input bar moderna para orquestração de agentes</h1>
            <p>
              A nova barra combina input multiline, anexos de contexto, seletor de
              modelo e menu de ações em uma experiência equivalente aos produtos de
              AI atuais.
            </p>
            <div className="capability-grid">
              {capabilities.map((capability) => (
                <div className="capability-card" key={capability}>
                  <FileUp className="size-4" />
                  <span>{capability}</span>
                </div>
              ))}
            </div>
          </div>

          <aside className="agent-card" aria-label="Selected orchestration profile">
            <Bot className="size-6" />
            <div>
              <span>Perfil ativo</span>
              <strong>{selectedModel}</strong>
            </div>
          </aside>
        </div>
      </section>

      <section className="composer-panel" aria-label="Prompt composer demo">
        <div className="composer-header">
          <div>
            <span>Context upload habilitado</span>
            <h2>Envie arquivos como contexto para os agentes</h2>
          </div>
          <BrainCircuit className="size-6" />
        </div>

        {messages.length > 0 ? (
          <div className="message-stack" aria-label="Recent submissions">
            {messages.map((message, index) => (
              <article className="message-card" key={`${message.text}-${index}`}>
                <p>{message.text || 'Prompt enviado com anexos de contexto.'}</p>
                {message.files?.length ? (
                  <span>{message.files.length} arquivo(s) anexado(s)</span>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            Arraste arquivos para a página ou use o menu de ações para anexar contexto.
          </div>
        )}

        <PromptInput
          accept="image/*,.pdf,.txt,.md,.json,.csv,.log"
          globalDrop
          multiple
          onSubmit={handleSubmit}
          className="composer"
        >
          <PromptInputHeader>
            <PromptInputAttachmentsDisplay />
          </PromptInputHeader>
          <PromptInputBody>
            <PromptInputTextarea placeholder="Descreva a tarefa para a orquestração. Use Shift+Enter para quebrar linha." />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputTools>
              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger />
                <PromptInputActionMenuContent>
                  <PromptInputActionAddAttachments label="Anexar contexto" />
                  <PromptInputActionAddScreenshot label="Anexar screenshot" />
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>
              <PromptInputButton
                onClick={() => setWebSearch((enabled) => !enabled)}
                tooltip={{ content: 'Usar web como ferramenta', shortcut: '⌘K' }}
                variant={webSearch ? 'default' : 'ghost'}
              >
                <GlobeIcon className="size-4" />
                <span>Web</span>
              </PromptInputButton>
              <PromptInputSelect value={model} onValueChange={(value) => value && setModel(value)}>
                <PromptInputSelectTrigger className="model-trigger">
                  <PromptInputSelectValue />
                </PromptInputSelectTrigger>
                <PromptInputSelectContent>
                  {models.map((item) => (
                    <PromptInputSelectItem key={item.id} value={item.id}>
                      {item.name}
                    </PromptInputSelectItem>
                  ))}
                </PromptInputSelectContent>
              </PromptInputSelect>
            </PromptInputTools>
            <PromptInputSubmit status={status} />
          </PromptInputFooter>
        </PromptInput>
      </section>
    </main>
  )
}

export default App
