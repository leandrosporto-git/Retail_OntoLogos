# Questões de competência

As questões de competência (CQs) delimitam o que a ontologia e o software precisam responder
(Grüninger e Fox, 1995). Cada CQ abaixo vira um teste automatizado em `tests/test_questoes_competencia.py`.

**Origem:** CQ01 a CQ05 vêm da seção 4.2 do relatório técnico MCC 06/2026 (Porto e Lifschitz).
CQ06 a CQ08 foram acrescentadas no planejamento do Projeto Final para cobrir o contexto
(loja e data), a ausência de dados e o custo de oportunidade.

| Código | Pergunta | Origem | Dados necessários | Teste (critério de aceite) |
| --- | --- | --- | --- | --- |
| CQ01 | Um produto pode ser classificado como estoque obsoleto? | Relatório técnico, 4.2 | Idade do estoque, vendas no período, quantidade disponível | Toda observação recebe exatamente um diagnóstico; os casos de controle saem na categoria esperada |
| CQ02 | Quais indicadores sustentam essa classificação? | Relatório técnico, 4.2 | Indicadores calculados por observação | Todo diagnóstico diferente de Ativo tem ao menos uma evidência ligada a um indicador |
| CQ03 | Quais fatores ou condições contribuíram para o diagnóstico? | Relatório técnico, 4.2 | Critérios atendidos e causas prováveis | Cada evidência aponta o critério que atendeu, com valor observado e limite |
| CQ04 | Quais alternativas de destinação são recomendadas para determinado contexto? | Relatório técnico, 4.2 | Diagnóstico, coleção, situação do mesmo SKU em outras lojas | Todo diagnóstico Lento ou obsoleto recebe ao menos uma recomendação |
| CQ05 | Quais regras de negócio justificam a recomendação produzida? | Relatório técnico, 4.2 | Identificador e versão da regra | Toda recomendação aponta a regra (id + versão) que a gerou |
| CQ06 | O diagnóstico de um produto muda entre lojas ou períodos? | Planejamento do PFP | Observações do mesmo SKU em lojas diferentes | Existe ao menos um SKU com categorias diferentes em lojas diferentes no dataset de exemplo |
| CQ07 | Quais informações são insuficientes para um diagnóstico confiável? | Planejamento do PFP | Campos obrigatórios por observação | Observações sem vendas registradas ou sem idade recebem Dados insuficientes, nunca Lento ou obsoleto |
| CQ08 | Qual é o custo de oportunidade do capital parado em cada estoque? | Planejamento do PFP (extensão em relação ao relatório) | Custo unitário, quantidade, idade, taxa de custo de capital | O valor calculado confere com a fórmula documentada; sem custo unitário, o valor fica ausente e o SKU sai do ranking financeiro |

## Categorias de diagnóstico

As quatro categorias seguem a Figura 1 do relatório técnico (classificação por idade do estoque e
relação entre demanda e estoque, NetSuite, 2024). A quinta categoria trata a hipótese de mundo aberto:
ausência de registro não é evidência de ausência de venda.

| Categoria | Idade do estoque | Cobertura (dias de venda que o estoque dura) |
| --- | --- | --- |
| Ativo | até o limite | até o limite |
| Excesso | até o limite | acima do limite |
| Envelhecido | acima do limite | até o limite |
| Lento ou obsoleto | acima do limite | acima do limite (ou sem venda no período) |
| Dados insuficientes | ausente | ausente |

Os limites ficam em `regras/parametros.yaml`. **Os valores iniciais são hipotéticos** e precisam ser
validados com especialistas antes de qualquer uso real.
