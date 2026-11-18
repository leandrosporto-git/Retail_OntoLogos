# Questões de competência

As questões de competência (CQs) delimitam o que a ontologia e o software precisam responder
(Grüninger e Fox, 1995). Cada CQ abaixo vira um teste automatizado em `tests/test_questoes_competencia.py`.

**Origem:** as CQs da versão 0.2.0 (ontologia V_Zero) seguem o documento de definições de estoque obsoleto
usado como base do projeto e as decisões de validação de 17/11/2026. Elas substituem as CQs da versão 0.1.0,
que vinham da seção 4.2 do relatório técnico MCC 06/2026 (Porto e Lifschitz) e continuam cobertas: classificação
(CQ01, CQ02), indicadores e evidências (CQ03, CQ04), fatores (CQ05, CQ06), destinação (CQ11) e regras (CQ09).

**Unidade de diagnóstico:** produto-cor × escopo de rede × data de referência (a posição na rede).

| Código | Pergunta | Teste (critério de aceite) |
| --- | --- | --- |
| CQ01 | Toda posição na rede com saldo positivo tem um diagnóstico? | Exatamente um diagnóstico por posição com saldo > 0; nenhum para saldo ≤ 0 |
| CQ02 | Qual é a situação de giro e idade de cada produto-cor? | Os casos de controle (`CTRL-*`) saem na situação esperada |
| CQ03 | Quais evidências e qual regra sustentam o diagnóstico? | Todo diagnóstico tem evidência C01 (saldo), C02 e C03 (dias e meses) ou C04 (dados insuficientes), e aponta a regra na versão vigente |
| CQ04 | A situação respeita os limites de 180 dias e 24 meses? | A situação gravada bate com os valores calculados; limites estritos (24 meses e 180 dias exatos ficam Ativo) |
| CQ05 | Quais motivos se somam à situação? | Marca descontinuada e produto com defeito são registrados mesmo para produto Ativo |
| CQ06 | Há oportunidade local de transferência? | Só em filial de venda aberta há mais de 12 meses, sem venda local há mais de 180 dias, com destino que vendeu recentemente |
| CQ07 | Quais vendas contam? | Só vendas válidas, das filiais do escopo, com nomes anteriores de filial traduzidos para o código atual |
| CQ08 | Qual é o custo de oportunidade e em que ordem atuar? | O custo confere com a fórmula; a prioridade 1, 2, 3... segue o custo em ordem decrescente |
| CQ09 | Toda recomendação é rastreável? | Toda recomendação considera um diagnóstico ou motivo, sugere uma ação e aponta a regra versionada; todo potencialmente obsoleto e todo motivo (exceto defeito) tem recomendação |
| CQ10 | O que fica fora por dado inconsistente ou incompleto? | Saldo negativo gera alerta e não recebe diagnóstico; sem data de lançamento, só Diagnóstico pendente |
| CQ11 | Qual destinação cada motivo recebe? | Cancelado → recolher e enviar à filial de defeito; bloqueio → manter no CD (causa provável da falta de venda); contínuo → revisar classificação |

## Situações de giro e idade

| Situação | Mais de 180 dias sem venda válida na rede | Mais de 24 meses desde o lançamento |
| --- | --- | --- |
| Ativo | não | não |
| Antigo com giro | não | sim |
| Sem giro em atenção | sim | não |
| Potencialmente obsoleto | sim | sim |
| Diagnóstico pendente | sem data de lançamento ou janela de vendas incompleta | |

Os limites ficam em `regras/parametros.yaml`. Potencialmente obsoleto recomenda avaliar destinação e write-off
por ação comercial, **sem baixa automática**.

**Custo de oportunidade (proposta original do projeto, não vem do documento de definições):**
valor a custo × taxa anual de custo de capital (15%) × dias sem venda / 365.
