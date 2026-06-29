# Requirements Document

## Introduction

Este documento descreve os requisitos do sistema de gerenciamento de cotas R.A.G.E. (Recência, Ação, Granularidade, Escopo) para o ADK Agent Orchestrator. A feature introduz um **Classificador R.A.G.E.** — um agente ADK dedicado de pré-roteamento — que intercepta toda requisição, avalia os 4 eixos da Matriz R.A.G.E. e decide custo em cotas, modelo LLM e modalidade de execução (síncrona ou assíncrona) antes de delegar ao root agent. O armazenamento de cotas é feito via arquivo YAML/JSON por usuário com contadores in-memory por processo. O campo `quota_status` é adicionado ao `ExecutionContractDTO` existente para expor consumo, limite e próximo reset ao cliente.

## Glossário

- **R.A.G.E.**: Acrônimo dos 4 eixos de classificação: Recência e Volume de Dados, Ação e Complexidade Cognitiva, Granularidade, Escopo de Contexto (RAG).
- **Classificador R.A.G.E.**: Agente ADK de pré-roteamento responsável por avaliar toda requisição de entrada pelos 4 eixos e produzir uma `RageDecision`.
- **RageDecision**: Estrutura de dados imutável que encapsula eixos avaliados, custo calculado em cotas, modelo LLM selecionado e modalidade de execução.
- **Cota**: Unidade de consumo abstrata exposta ao usuário final (não tokens nem créditos).
- **QuotaStore**: Componente responsável por ler o arquivo de configuração de limites por usuário e manter contadores in-memory por processo.
- **QuotaConfig**: Arquivo YAML ou JSON estático por usuário contendo o limite mensal de cotas configurado externamente ao código.
- **QuotaStatus**: DTO filho de `ExecutionContractDTO` com cotas consumidas, limite e timestamp do próximo reset.
- **Modalidade Síncrona**: Execução imediata com resposta em tempo real.
- **Modalidade Assíncrona**: Execução via Batch API com SLA de até 12 horas e desconto de 30–50% no custo de cotas.
- **Urgência Operacional**: Sinalização semântica presente na requisição (ex.: "máquina parada", "alarme crítico") que força execução síncrona independentemente do custo.
- **Fallback de Cota Esgotada**: Comportamento de redirecionar a requisição para banco de dados padrão quando o usuário não possui cotas disponíveis.
- **ExecutionContractDTO**: DTO versionado existente em `contracts/dto.py` que representa a visão completa de execução para clientes UI/API.
- **Root Agent**: Agente ADK raiz definido em `agents/root.py` que recebe a requisição após a classificação R.A.G.E. e delega para workflows e especialistas.

---

## Requisitos

### Requisito 1 — Classificação R.A.G.E. por Eixos

**User Story:** Como operador industrial, quero que toda requisição seja avaliada pelos 4 eixos da Matriz R.A.G.E. antes do processamento, para que o custo em cotas reflita fielmente a complexidade real da análise solicitada.

#### Critérios de Aceite

1. THE Classificador R.A.G.E. SHALL avaliar o eixo **[R] Recência e Volume** classificando como custo zero quando a requisição acessa apenas dados de curto prazo e como custo positivo quando acessa histórico de longo prazo.
2. THE Classificador R.A.G.E. SHALL avaliar o eixo **[A] Ação e Complexidade Cognitiva** classificando ações determinísticas (listagem, filtro, ordenação) como custo zero e ações de diagnóstico ou dedução como custo positivo com seleção de modelo LLM avançado (Sonnet ou GPT-4o).
3. THE Classificador R.A.G.E. SHALL avaliar o eixo **[G] Granularidade** classificando análise pontual em um único ativo como custo zero e análise comparativa ou de múltiplos ativos como custo positivo.
4. THE Classificador R.A.G.E. SHALL avaliar o eixo **[E] Escopo de Contexto (RAG)** classificando como custo zero quando o contexto se limita a dados de vibração e temperatura e como custo positivo (premium) quando inclui leitura de manuais PDF, CMMS ou ERP.
5. WHEN os 4 eixos são avaliados, THE Classificador R.A.G.E. SHALL produzir uma `RageDecision` imutável contendo os resultados por eixo, o custo total em cotas, o modelo LLM selecionado e a modalidade de execução recomendada.
6. THE Classificador R.A.G.E. SHALL atribuir custo de 0 cotas para requisições de Busca Simples, 0 cotas para Resumo de Contexto Base, 1 cota para Análise Investigativa Simples, 1 a 2 cotas para Análise Comparativa/Frota e 3 cotas para Análise de Causa Raiz (RCA) conforme a tabela de decisão definida.

---

### Requisito 2 — Agente ADK de Pré-Roteamento (Interceptação)

**User Story:** Como desenvolvedor do sistema, quero que o Classificador R.A.G.E. seja um agente ADK dedicado posicionado antes do root agent, para que toda requisição seja obrigatoriamente interceptada e classificada antes do processamento downstream.

#### Critérios de Aceite

1. THE Classificador R.A.G.E. SHALL ser implementado como um agente ADK Python (`google.adk.agents.llm_agent.Agent`) instanciado na fábrica em `agents/specialists.py` seguindo o padrão do projeto.
2. WHEN uma requisição é recebida pelo sistema, THE Classificador R.A.G.E. SHALL ser invocado antes da delegação ao Root Agent.
3. WHEN o Classificador R.A.G.E. produz uma `RageDecision`, THE Root Agent SHALL receber a decisão via estado de sessão ADK antes de iniciar o processamento.
4. THE Classificador R.A.G.E. SHALL registrar a `RageDecision` no estado de sessão ADK sob a chave `rage_decision` para acesso por agentes downstream.

---

### Requisito 3 — Armazenamento e Verificação de Cotas

**User Story:** Como administrador do sistema, quero definir limites mensais de cotas por usuário em arquivos de configuração externos ao código, para que os limites sejam ajustáveis sem reimplantação.

#### Critérios de Aceite

1. THE QuotaStore SHALL ler o limite de cotas do usuário a partir de um arquivo YAML ou JSON por usuário localizado em um diretório configurável.
2. THE QuotaStore SHALL manter o contador de cotas consumidas no período corrente em memória por processo.
3. WHEN o arquivo de configuração do usuário não é encontrado, THE QuotaStore SHALL aplicar o limite padrão configurado em `OrchestratorSettings`.
4. WHEN uma `RageDecision` com custo maior que zero é recebida, THE QuotaStore SHALL verificar se o usuário possui cotas suficientes antes de autorizar a execução.
5. IF o custo da `RageDecision` excede as cotas disponíveis do usuário, THEN THE QuotaStore SHALL retornar status de cota insuficiente sem debitar cotas.
6. WHEN a execução é concluída com sucesso, THE QuotaStore SHALL debitar as cotas correspondentes ao custo da `RageDecision` do contador in-memory do usuário.
7. THE QuotaStore SHALL expor o estado atual (consumido, limite, timestamp do próximo reset) através de uma interface de consulta síncrona.

---

### Requisito 4 — Princípio de Não-Surpresa (UX de Cotas)

**User Story:** Como operador industrial, quero ser informado sobre o consumo de cotas antes que elas sejam debitadas, para que eu não seja surpreendido por débitos não autorizados.

#### Critérios de Aceite

1. WHEN a `RageDecision` indica custo maior que zero, THE Classificador R.A.G.E. SHALL incluir na resposta ao usuário o número de cotas que serão consumidas antes de prosseguir com a execução.
2. THE sistema SHALL usar o termo "Cotas de Uso" na comunicação com o usuário, nunca "tokens" nem "créditos de IA".
3. WHEN a `RageDecision` indica custo maior ou igual a 2 cotas e a requisição não possui sinalização de urgência operacional, THE Classificador R.A.G.E. SHALL oferecer ao usuário a opção de execução assíncrona com o custo reduzido calculado.
4. WHEN o usuário confirma a execução assíncrona, THE Classificador R.A.G.E. SHALL incluir na confirmação o custo em cotas com desconto e o SLA de até 12 horas.

---

### Requisito 5 — Roteamento Síncrono vs. Assíncrono

**User Story:** Como operador industrial, quero que análises custosas sejam oferecidas no modo assíncrono para economizar cotas, exceto quando houver urgência operacional, para que eu possa equilibrar custo e velocidade de resposta.

#### Critérios de Aceite

1. WHEN a `RageDecision` indica custo maior ou igual a 2 cotas, THE Classificador R.A.G.E. SHALL incluir na `RageDecision` a recomendação de modalidade assíncrona com custo reduzido entre 30% e 50% do custo original.
2. WHEN a requisição contém sinalização de urgência operacional, THE Classificador R.A.G.E. SHALL forçar modalidade síncrona independentemente do custo calculado.
3. THE sistema SHALL reconhecer as expressões "máquina parada" e "alarme crítico" como sinalizações de urgência operacional válidas.
4. WHEN a modalidade assíncrona é selecionada, THE Root Agent SHALL encaminhar a execução ao Batch API correspondente ao modelo selecionado na `RageDecision`.
5. WHILE a execução assíncrona está pendente, THE sistema SHALL manter o status da tarefa como "pending" no `ExecutionContractDTO` até a conclusão ou falha.

---

### Requisito 6 — Fallback por Cota Esgotada

**User Story:** Como operador industrial, quero receber uma resposta útil mesmo quando minhas cotas estiverem esgotadas, para que o sistema permaneça operacional com funcionalidades básicas.

#### Critérios de Aceite

1. IF o usuário não possui cotas suficientes para a `RageDecision` calculada, THEN THE sistema SHALL redirecionar a requisição para consulta direta ao banco de dados padrão sem invocar LLM avançado.
2. IF o usuário não possui cotas suficientes, THEN THE sistema SHALL incluir no `ExecutionContractDTO` um aviso explícito informando que as cotas foram esgotadas e o timestamp do próximo reset.
3. WHEN o fallback é ativado por cota esgotada, THE sistema SHALL registrar o evento com severidade "warning" na lista de `events` do `ExecutionContractDTO`.

---

### Requisito 7 — Campo `quota_status` no ExecutionContractDTO

**User Story:** Como desenvolvedor de UI, quero acessar o status de cotas do usuário diretamente no `ExecutionContractDTO`, para que o frontend possa exibir consumo e limite em tempo real sem chamadas adicionais.

#### Critérios de Aceite

1. THE `ExecutionContractDTO` SHALL incluir o campo `quota_status` do tipo `QuotaStatusDTO` em todas as respostas geradas após a ativação da feature.
2. THE `QuotaStatusDTO` SHALL conter os campos: cotas consumidas no período (`consumed`), limite configurado (`limit`), cotas disponíveis (`available`) e timestamp ISO 8601 UTC do próximo reset (`next_reset_at`).
3. WHEN a execução é concluída, THE sistema SHALL preencher `quota_status` com os valores atualizados após o débito de cotas.
4. WHERE o usuário possui perfil de administrador, THE `QuotaStatusDTO` SHALL incluir adicionalmente o campo `user_id` do usuário consultado para suporte a painéis administrativos.
5. THE `QuotaStatusDTO` SHALL ser um dataclass imutável (`frozen=True`) seguindo o padrão existente em `contracts/dto.py`.

---

### Requisito 8 — Configuração e Integração com OrchestratorSettings

**User Story:** Como desenvolvedor do sistema, quero que as configurações de cota sejam gerenciadas através do mecanismo de settings existente, para que o comportamento seja controlável via variáveis de ambiente sem alterar o código.

#### Critérios de Aceite

1. THE `OrchestratorSettings` SHALL incluir o campo `quota_config_dir` com valor padrão configurável via variável de ambiente `ADK_QUOTA_CONFIG_DIR`.
2. THE `OrchestratorSettings` SHALL incluir o campo `quota_default_limit` com o limite mensal padrão de cotas aplicado quando nenhum arquivo de configuração do usuário é encontrado, configurável via variável de ambiente `ADK_QUOTA_DEFAULT_LIMIT`.
3. THE `OrchestratorSettings` SHALL incluir o campo `quota_async_discount_pct` com o percentual de desconto para execução assíncrona (entre 30 e 50), configurável via variável de ambiente `ADK_QUOTA_ASYNC_DISCOUNT_PCT`.
4. WHEN `ADK_QUOTA_ASYNC_DISCOUNT_PCT` é definido com valor fora do intervalo 30–50, THE `OrchestratorSettings` SHALL lançar `ValueError` descrevendo o intervalo permitido.
5. THE `OrchestratorSettings` SHALL incluir o campo `quota_reset_day` com o dia do mês em que as cotas são resetadas (1–28), configurável via variável de ambiente `ADK_QUOTA_RESET_DAY`, com padrão 1.
