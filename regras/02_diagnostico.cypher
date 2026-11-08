// regra: R01 | versao: 0.1.0 | area: Planejamento
// descricao: Classifica cada observação de estoque em uma das categorias (idade x cobertura) e registra as evidências e causas prováveis. Sem registro de vendas ou de idade, o diagnóstico é Dados insuficientes: ausência de registro não é tratada como ausência de venda.
MATCH (r:RegraNegocio {id: 'R01'})
MATCH (c1:CriterioDiagnostico {id: 'C01'}), (c2:CriterioDiagnostico {id: 'C02'}),
      (c3:CriterioDiagnostico {id: 'C03'}), (c4:CriterioDiagnostico {id: 'C04'})
MATCH (kCol:CausaProvavel {codigo: 'ColecaoEncerrada'}), (kDem:CausaProvavel {codigo: 'BaixaDemanda'}),
      (kIda:CausaProvavel {codigo: 'EstoqueEnvelhecido'})
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)
MATCH (p)-[:PERTENCE_A_COLECAO]->(col:Colecao)
OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(iIdade:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'IdadeEstoque'})
OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(iVend:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'VendasPeriodo'})
OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(iCob:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'CoberturaDias'})
WITH r, c1, c2, c3, c4, kCol, kDem, kIda, o, col, iIdade, iVend, iCob,
     (iIdade IS NULL OR iVend IS NULL) AS faltaDado
WITH r, c1, c2, c3, c4, kCol, kDem, kIda, o, col, iIdade, iVend, iCob, faltaDado,
     (NOT faltaDado AND iIdade.valor > $idade_estoque_dias) AS atendeC01,
     (NOT faltaDado AND (iVend.valor = 0 OR iCob.valor > $cobertura_dias)) AS atendeC02
WITH *, CASE
          WHEN faltaDado THEN 'DadosInsuficientes'
          WHEN atendeC01 AND atendeC02 THEN 'LentoOuObsoleto'
          WHEN atendeC01 THEN 'Envelhecido'
          WHEN atendeC02 THEN 'Excesso'
          ELSE 'Ativo'
        END AS categoria
MATCH (cat:CategoriaDiagnostico {nome: categoria})
CREATE (o)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico {id: o.id + '-R01', dataAvaliacao: datetime($data_avaliacao), versao: r.versao})
CREATE (d)-[:CLASSIFICADO_COMO]->(cat)
CREATE (d)-[:GERADO_POR_REGRA]->(r)
FOREACH (_ IN CASE WHEN atendeC01 THEN [1] ELSE [] END |
  CREATE (d)-[:FUNDAMENTADO_EM]->(e:Evidencia {id: d.id + '-C01', valorObservado: iIdade.valor,
          justificativa: 'Idade do estoque de ' + toString(iIdade.valor) + ' dias, acima do limite de ' + toString($idade_estoque_dias) + ' dias'})
  CREATE (e)-[:ATENDE_CRITERIO]->(c1)
  CREATE (e)-[:BASEADA_EM_INDICADOR]->(iIdade)
  CREATE (e)-[:INDICA_CAUSA]->(kIda))
FOREACH (_ IN CASE WHEN atendeC02 AND iVend.valor = 0 THEN [1] ELSE [] END |
  CREATE (d)-[:FUNDAMENTADO_EM]->(e:Evidencia {id: d.id + '-C02', valorObservado: 0,
          justificativa: 'Nenhuma venda registrada nos últimos 90 dias'})
  CREATE (e)-[:ATENDE_CRITERIO]->(c2)
  CREATE (e)-[:BASEADA_EM_INDICADOR]->(iVend)
  CREATE (e)-[:INDICA_CAUSA]->(kDem))
FOREACH (_ IN CASE WHEN atendeC02 AND iVend.valor > 0 THEN [1] ELSE [] END |
  CREATE (d)-[:FUNDAMENTADO_EM]->(e:Evidencia {id: d.id + '-C02', valorObservado: iCob.valor,
          justificativa: 'Cobertura de ' + toString(iCob.valor) + ' dias, acima do limite de ' + toString($cobertura_dias) + ' dias'})
  CREATE (e)-[:ATENDE_CRITERIO]->(c2)
  CREATE (e)-[:BASEADA_EM_INDICADOR]->(iCob)
  CREATE (e)-[:INDICA_CAUSA]->(kDem))
FOREACH (_ IN CASE WHEN col.encerrada AND categoria IN ['Excesso', 'Envelhecido', 'LentoOuObsoleto'] THEN [1] ELSE [] END |
  CREATE (d)-[:FUNDAMENTADO_EM]->(e:Evidencia {id: d.id + '-C03',
          justificativa: 'Produto da coleção ' + col.nome + ', já encerrada'})
  CREATE (e)-[:ATENDE_CRITERIO]->(c3)
  CREATE (e)-[:INDICA_CAUSA]->(kCol))
FOREACH (_ IN CASE WHEN faltaDado THEN [1] ELSE [] END |
  CREATE (d)-[:FUNDAMENTADO_EM]->(e:Evidencia {id: d.id + '-C04',
          justificativa: 'Sem registro de: ' + CASE WHEN iVend IS NULL AND iIdade IS NULL THEN 'vendas e idade do estoque'
                                                   WHEN iVend IS NULL THEN 'vendas no período'
                                                   ELSE 'idade do estoque' END})
  CREATE (e)-[:ATENDE_CRITERIO]->(c4))
RETURN categoria, count(*) AS observacoes ORDER BY categoria;
