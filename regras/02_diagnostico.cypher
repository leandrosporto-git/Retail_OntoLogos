// regra: R01 | versao: 0.2.0 | area: Planejamento
// descricao: Classifica cada posição na rede com saldo positivo pelo fluxograma de giro e idade: dados insuficientes -> Diagnóstico pendente; senão cruza mais de 180 dias sem venda válida na rede com mais de 24 meses desde o lançamento (limites estritos, meses de calendário). Saldo zero ou negativo fica fora do universo.
MATCH (regra:RegraNegocio {id: 'R01'})
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor)
WHERE r.saldoRede > 0
WITH regra, r, pc,
     (pc.dataLancamento IS NULL OR date($inicio_historico_vendas) > r.dataReferencia - duration({days: $dias_sem_venda})) AS pendente
WITH regra, r, pc, pendente,
     (NOT pendente AND r.diasSemVenda > $dias_sem_venda) AS semGiro,
     (NOT pendente AND r.dataReferencia > pc.dataLancamento + duration({months: $idade_meses})) AS antigo
WITH regra, r, pc, pendente, semGiro, antigo,
     CASE WHEN pendente THEN 'DiagnosticoPendente'
          WHEN NOT semGiro AND NOT antigo THEN 'Ativo'
          WHEN NOT semGiro THEN 'AntigoComGiro'
          WHEN NOT antigo THEN 'SemGiroEmAtencao'
          ELSE 'PotencialmenteObsoleto' END AS situacao
MATCH (s:SituacaoGiroIdade {nome: situacao})
CREATE (r)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico {id: r.id + '-R01', dataAvaliacao: r.dataReferencia, versao: regra.versao})
CREATE (d)-[:CLASSIFICADO_COMO]->(s)
CREATE (d)-[:GERADO_POR_REGRA]->(regra)
CREATE (d)-[:SUSTENTADO_POR]->(:Evidencia {id: d.id + '-C01', criterio: 'C01 saldo consolidado positivo',
        valorObservado: r.saldoRede, limite: 0,
        justificativa: 'Saldo de ' + toString(r.saldoRede) + ' peças nas filiais do escopo em ' + toString(r.dataReferencia)})
FOREACH (_ IN CASE WHEN pendente THEN [1] ELSE [] END |
  CREATE (d)-[:SUSTENTADO_POR]->(:Evidencia {id: d.id + '-C04', criterio: 'C04 dados suficientes',
          justificativa: CASE WHEN pc.dataLancamento IS NULL THEN 'Sem data de lançamento confiável: completar evidências'
                              ELSE 'Janela de vendas não cobre os últimos ' + toString($dias_sem_venda) + ' dias' END}))
FOREACH (_ IN CASE WHEN pendente THEN [] ELSE [1] END |
  CREATE (d)-[:SUSTENTADO_POR]->(:Evidencia {id: d.id + '-C02', criterio: 'C02 dias sem venda válida na rede',
          valorObservado: r.diasSemVenda, limite: $dias_sem_venda,
          justificativa: CASE WHEN r.ultimaVendaValida IS NULL
                              THEN 'Nenhuma venda válida na rede na janela disponível: ' + toString(r.diasSemVenda) + ' dias'
                              ELSE 'Última venda válida na rede em ' + toString(r.ultimaVendaValida) + ': ' + toString(r.diasSemVenda) + ' dias' END
                         + CASE WHEN semGiro THEN ' (mais de ' ELSE ' (até ' END + toString($dias_sem_venda) + ' dias)'})
  CREATE (d)-[:SUSTENTADO_POR]->(:Evidencia {id: d.id + '-C03', criterio: 'C03 meses desde o lançamento',
          valorObservado: r.idadeMeses, limite: $idade_meses,
          justificativa: 'Lançado em ' + toString(pc.dataLancamento) + ' (' + coalesce(pc.origemDataLancamento, 'origem não informada') + '): '
                         + toString(r.idadeMeses) + ' meses' + CASE WHEN antigo THEN ' (mais de ' ELSE ' (até ' END + toString($idade_meses) + ' meses)'}))
RETURN situacao, count(*) AS posicoes ORDER BY situacao;
