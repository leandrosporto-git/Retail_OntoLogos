// regra: R00 | versao: 0.1.0 | area: Planejamento
// descricao: Calcula indicadores derivados (cobertura, sell-through, custo de oportunidade) a partir dos indicadores medidos. Indicador ausente não é criado (mundo aberto).
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:POSSUI_INDICADOR]->(v:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'VendasPeriodo'})
WITH p, o, v
CALL (o, v) {
  WITH o, v WHERE v.valor > 0
  MATCH (t:TipoIndicador {nome: 'CoberturaDias'})
  CREATE (o)-[:POSSUI_INDICADOR]->(c:Indicador {id: o.id + '-CoberturaDias', valor: round(o.quantidadeDisponivel / (v.valor / 90.0), 1), unidade: 'dias'})-[:DO_TIPO]->(t)
}
CALL (o, v) {
  MATCH (t:TipoIndicador {nome: 'SellThrough'})
  CREATE (o)-[:POSSUI_INDICADOR]->(s:Indicador {id: o.id + '-SellThrough', valor: round(toFloat(v.valor) / (v.valor + o.quantidadeDisponivel), 3), unidade: 'proporção'})-[:DO_TIPO]->(t)
}
RETURN count(*) AS observacoes_com_vendas;

// regra: R00 | versao: 0.1.0 | area: Planejamento
// descricao: Custo de oportunidade = custo unitário x quantidade x taxa anual de custo de capital x idade/365. Proposta original do projeto.
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:POSSUI_INDICADOR]->(i:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'IdadeEstoque'})
WHERE p.custoUnitario IS NOT NULL
MATCH (t:TipoIndicador {nome: 'CustoOportunidade'})
CREATE (o)-[:POSSUI_INDICADOR]->(:Indicador {id: o.id + '-CustoOportunidade', valor: round(p.custoUnitario * o.quantidadeDisponivel * $taxa_custo_capital_anual * i.valor / 365.0, 2), unidade: 'R$'})-[:DO_TIPO]->(t)
RETURN count(*) AS observacoes_com_custo;
