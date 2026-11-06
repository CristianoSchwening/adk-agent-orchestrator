# E12 — Visibilidade de PDFs inspirada em casos públicos

## Origem

O Acórdão 2836/2026 do TCU auditou o sistema Galileu e descreveu
testes adversariais em documentos jurídicos. Os detalhes técnicos das
peças 19–26 e 35 têm acesso restrito; **não usamos PDFs reais**.
O caso TRT-8 ATOrd 0001062-55.2025.5.08.0130 documenta
**texto branco sobre fundo branco**. Também houve notícia pública
do TRT-2 sobre contestação com texto oculto branco e pequeno.

Referências:
- https://portal.tcu.gov.br/imprensa/noticias/auditoria-analisa-uso-de-ia-no-tribunal-regional-do-trabalho-de-porto-alegre
- https://ww2.trt2.jus.br/noticias/noticias/noticia/comando-para-ia-oculto-em-contestacao-gera-multa-por-litigancia-de-ma-fe-a-advogados

## Hipótese

O detector do E11, limitado a texto com render_type=3, não detecta
instruções em branco sobre branco. A nova instrumentação identifica
esse vetor com uma verificação de contraste **apenas em páginas de
fundo branco conhecido e construídas pelo experimento**.

Seis PDFs fictícios com duas páginas cada:
controle, render_mode=3, branco-sobre-branco ativo,
branco-sobre-branco benigno, citação visível e página imagem sem OCR.

A sinalização de cor branca não implica intenção maliciosa.
O caso benigno é intencionalmente sinalizado para evidenciar
**falsos positivos técnicos** ao generalizar de visibilidade para risco.

## Executar Windows

    git pull origin main
    .venv\Scripts\python.exe -m pytest tests/test_e12_pdf_visibility.py -q --basetemp=data/pytest_temp
    .venv\Scripts\python.exe -m experiments.e12_pdf_visibility.run

PDFs: data/experiments/e12/E12_*.pdf
Relatório: data/executions/e12/visibility_report.json

## Limites

O E12 não usa o classificador Gemini ou o agente jurídico, não edita
PDFs nem garante reconstrução segura em documentos arbitrários.
A projeção é **somente diagnóstica**, sem aprovação para entrega
automática ao agente. Não há julgamento de malícia ou decisão judicial.
Não é validação independente das peças do TCU.
