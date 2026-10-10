# Plano de interação humana e retomada de execução

Data: 09/10/2026. Plano implementado com solicitações e respostas dentro da conversa.

## Implementação e validação

- A entrada de revisão contém explicitamente a candidata e a tarefa original. Testes capturam a requisição enviada ao modelo do crítico.
- O gate humano usa `RequestInput` do ADK, mantém a execução em `awaiting_human` e só libera a continuação com uma resposta validada pelo servidor. Rejeição cancela; alterações produzem uma nova candidata e nova aprovação.
- Sessões e eventos são persistidos pelo serviço de banco do ADK em SQLite, e snapshots/respostas são gravados atomicamente. Travas do sistema operacional por execução impedem respostas concorrentes e são liberadas se o processo morrer.
- A API consulta e retoma a mesma sessão, preservando tarefa e tentativa. As respostas são persistidas antes da continuação; reenvios iguais não repetem ações.
- A solicitação aparece como mensagem na aba Chat, com candidata, critérios, campo de resposta e ações. As decisões ficam no histórico. A aba abre automaticamente quando há pendência; recarga recupera a execução e o rascunho.
- Esclarecimento usa um campo textual na conversa. Quando a tarefa exige aprovação, o esclarecimento é seguido de uma nova proposta e aprovação explícita.
- Os testes cobrem o ADK real com modelos determinísticos, API, persistência, reenvios, tipos de resposta e renderização. A validação no navegador percorreu solicitação de alterações, recarga, aprovação e conclusão sem modelos externos.

## Diagnóstico confirmado

- `webapp-react/src/hooks/useContract.ts` permite iniciar uma execução, carregar demo e repetir a requisição original. Não envia respostas humanas nem retoma a sessão anterior.
- `src/orchestrator/server.py` não expõe consulta de execução, consulta de solicitação humana ou endpoint de resposta/retomada.
- `src/orchestrator/tools/human.py::request_human_approval` recebe uma decisão pronta e devolve um dicionário. Não solicita entrada ao humano e não interrompe a execução. Como a ferramenta é chamada pelo LLM, seus argumentos não são evidência de uma decisão humana.
- `create_human_in_the_loop_workflow` encadeia contexto, agente de aprovação e follow-up, sem um gate determinístico que aguarde a resposta humana e selecione a próxima rota.
- O runtime é criado dentro de cada `run_once_contract`, com serviços de sessão e artefatos em memória. Uma nova requisição não recupera automaticamente a sessão da execução anterior.
- Os estados de contrato e execução não distinguem explicitamente `awaiting_human`; o dispatcher não trata uma interrupção como uma tarefa pausada com retomada.
- Os testes existentes verificam a ferramenta com uma decisão fornecida diretamente, a composição do workflow e a seleção da estratégia. Não comprovam interação humana pela interface.

O trecho do `review_critic_agent` solicitando que se cole uma resposta candidata não comprova uma interrupção HITL. O crítico deve receber a candidata gerada pelo autor, com o objetivo e os critérios. A mensagem é indício de uma falha nessa entrada. O trecho não foi encontrado nos arquivos de execução persistidos consultados; a solicitação específica deve ser reproduzida por teste com captura da entrada do crítico.

## Comportamento esperado

Uma execução só aguarda o humano por uma solicitação estruturada e explícita. A interface apresenta o conteúdo a avaliar e recebe a decisão ou informação solicitada. O servidor registra a resposta e retoma a mesma sessão, na mesma tentativa, sem repetir tarefas concluídas. Uma frase livre produzida por um modelo não constitui aprovação nem cria uma pausa automaticamente.

Fluxo: execução → solicitação persistida → estado `awaiting_human` → resposta na interface → validação e registro → retomada da sessão → conclusão, revisão ou rejeição.

## Etapa 1 — Garantir a entrada do crítico

1. Capturar em teste a requisição efetivamente enviada ao modelo do crítico, usando o ADK real e um modelo determinístico.
2. Definir uma entrada explícita de revisão com tarefa original, objetivo, critérios, dependências e candidata. Não depender exclusivamente do histórico de mensagens ou de referências implícitas ao estado.
3. Usar essa entrada em todas as rodadas e separar a candidata da crítica anterior. Não passar rótulos de roteamento como conteúdo de trabalho.
4. Se a candidata estiver ausente, registrar uma falha interna de contexto com diagnóstico específico e permitir recuperação controlada. Não pedir ao usuário que copie uma resposta que deveria ter sido produzida pelo sistema.

Aceite: o crítico recebe a candidata em cada rodada; dois testes com candidatas diferentes comprovam que não usa uma resposta anterior; a ausência da candidata gera diagnóstico interno, sem solicitação humana fictícia.

## Etapa 2 — Contrato e armazenamento de solicitações humanas

1. Introduzir uma entidade de solicitação com `request_id`, sessão, invocação/interrupção ADK, plano e revisão, execução, tarefa e tentativa, tipo (`approval` ou `clarification`), pergunta, conteúdo candidato, opções e campos esperados, estado e datas.
2. Registrar a resposta separadamente, com decisão/conteúdo, origem humana e identidade disponível no servidor. Preservar histórico; não sobrescrever a candidata aprovada.
3. Acrescentar `awaiting_human` aos estados relevantes e uma coleção de solicitações no contrato público, atualizando DTOs, mapper, schemas, frontend e compatibilidade com registros antigos.
4. Compartilhar os serviços de sessão entre requisições e persistir sessões/eventos ADK e solicitações, para suportar recarga da página e reinício do servidor. Os JSONs de plano e tarefa, isoladamente, não bastam para reconstruir uma interrupção ADK.
5. Persistir antes de responder à interface; não marcar execução pausada como concluída ou falhada. O timeout de um orçamento de execução não deve correr enquanto o humano responde.

Aceite: consultar uma execução pausada devolve a mesma solicitação após recarga e reinício; contratos antigos continuam legíveis; a ausência de solicitações mantém o comportamento atual.

## Etapa 3 — Pausa, decisão e retomada no backend

1. Implementar um gate determinístico para `requires_approval`, usando a primitiva de interrupção suportada pelo ADK instalado. Validar `RequestInput`, resposta por `function_response`, identidade da invocação e comportamento de retomada em um teste de integração antes de integrar o dispatcher.
2. A criação da solicitação deve ocorrer antes da ação que depende de autorização, depois de haver conteúdo concreto para revisão. Um LLM pode preparar a pergunta, mas não pode responder pelo humano.
3. Persistir a fase da tarefa. Na retomada, o dispatcher deve recuperar a tarefa pausada, manter tentativa e IDs de chamadas e consumir a interrupção; não selecionar novamente apenas tarefas prontas nem iniciar uma nova execução.
4. Expor `GET /api/runs/{run_id}` e `POST /api/runs/{run_id}/human-requests/{request_id}/response`, com resposta contendo o contrato atualizado. O MVP pode usar consulta periódica durante a execução; streaming não é pré-requisito.
5. Validar associação da solicitação à sessão, execução e revisão atuais. Usar transição atômica e chave de idempotência para impedir processamento duplicado ou retomadas concorrentes.
6. Definir rotas explícitas: `approved` libera apenas a continuação autorizada; `needs_changes` devolve feedback à elaboração e exige nova aprovação da nova candidata; `rejected` encerra o caminho dependente, sem realizar a ação rejeitada. Replanejamento não pode contornar uma rejeição.
7. Permitir `clarification` somente quando informação externa realmente faltar, por solicitação estruturada com campos definidos. Manter isso separado de aprovação e de falhas internas de contexto.

Aceite: nenhum follow-up dependente ocorre antes da resposta humana; rejeição não libera execução; correções invalidam aprovação anterior; respostas duplicadas não repetem ações; uma revisão antiga não pode aprovar uma candidata nova; tarefas concluídas não são executadas novamente na retomada.

## Etapa 4 — Interface

1. Exibir “Aguardando sua resposta” em vez de erro ou conclusão. Apresentar a solicitação como mensagem no componente de conversação, com pergunta, tarefa, candidata e critérios legíveis, sem janela modal.
2. Para aprovação, oferecer “Aprovar”, “Solicitar alterações” e “Rejeitar”, com comentário obrigatório para alterações/rejeição. Para esclarecimento, renderizar os campos definidos pelo contrato.
3. Adicionar `respondToHumanRequest` e consulta de execução ao hook. “Tentar novamente” continua sendo reinício de execução; “Enviar resposta” retoma a sessão existente.
4. Desabilitar apenas o envio em andamento, preservar dados em erro de rede e mostrar confirmação ou erro local. Não simular aprovação no navegador.
5. Recuperar a execução selecionada ao recarregar a página e atualizar seu estado até nova pausa ou término. Mostrar solicitação e decisão no histórico e no inspector.
6. Garantir operação por teclado, mensagens acessíveis e layout móvel; não exigir copiar respostas internas para outro campo.

Aceite: usuário responde pelo front e acompanha a mesma execução continuar; refresh mantém a pendência; falha de rede permite reenvio idempotente; decisões antigas aparecem como histórico, sem botões ativos.

## Etapa 5 — Verificação e entrega

- Integração ADK: pausa → resposta → retomada com identidade da interrupção e estado preservados.
- API: aprovação, rejeição, alterações, esclarecimento, associação inválida, solicitação obsoleta, duplicidade, concorrência e recuperação após reinício.
- Front: mensagem pendente na conversa, campos/decisões, validação, carregamento, erro e recarga; regressão para execuções sem HITL.
- Ponta a ponta: tarefa anterior concluída → etapa humana pausada → decisão na interface → continuação autorizada, sem repetir tarefa anterior. Testes determinísticos não dependem de modelos externos.
- Manter em PRs separadas: entrada do crítico; contrato/persistência e pausa-retomada; interface e teste ponta a ponta. O front só será considerado funcional com o ciclo completo conectado.

## Ordem e limites

Executar as etapas na ordem acima. Priorizar a entrada do crítico antes do HITL, pois adicionar um formulário humano não resolve perda de contexto entre agentes. Não criar arquivos fictícios `plan.md`, `session.json` ou `workspace.json`, nem interpretar mensagens de esclarecimento do modelo como aprovação. O plano não inclui publicação, merge ou execução com modelos pagos.
