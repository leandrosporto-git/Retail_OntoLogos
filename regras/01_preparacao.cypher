// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Monta o escopo de rede a partir da fachada das filiais (filiais que operam sob a fachada da rede outlet).
MERGE (e:EscopoRede {codigo: $escopo_codigo})
SET e.nome = $escopo_nome
WITH e
MATCH (f:Filial)-[:OPERA_SOB_FACHADA]->(:Marca {codigo: $escopo_fachada})
MERGE (e)-[:INCLUI_FILIAL]->(f)
RETURN count(f) AS filiais_no_escopo;

// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Condição comercial da posição de estoque pelo tipo da filial: peça em filial de defeito é tratada como com defeito (hipótese simplificadora validada em 17/11/2026).
MATCH (p:PosicaoEstoque)-[:ESTA_EM]->(:Filial)-[:DO_TIPO_FILIAL]->(t:TipoFilial)
MATCH (c:CondicaoComercial {nome: CASE WHEN t.nome = 'FilialDefeito' THEN 'ComDefeito' ELSE 'SemDefeito' END})
MERGE (p)-[:TEM_CONDICAO]->(c)
RETURN c.nome AS condicao, count(p) AS posicoes ORDER BY condicao;

// regra: R00 | versao: 0.3.0 | area: Operacoes
// descricao: Alerta de consistência para saldo em filial já fechada (na prática, o estoque é baixado ou transferido antes do fechamento).
MATCH (p:PosicaoEstoque)-[:ESTA_EM]->(f:Filial)
WHERE f.dataFechamento IS NOT NULL AND f.dataFechamento <= p.dataReferencia AND p.quantidade <> 0
SET p.alertaConsistencia = 'Saldo em filial fechada em ' + toString(f.dataFechamento)
RETURN count(p) AS posicoes_com_alerta;

// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Consolida a posição na rede: soma das posições do produto-cor nas filiais do escopo, numa única data (não soma saldos de datas distintas).
MATCH (e:EscopoRede {codigo: $escopo_codigo})-[:INCLUI_FILIAL]->(:Filial)<-[:ESTA_EM]-(p:PosicaoEstoque)-[:REFERE_SE_A]->(pc:ProdutoCor)
WHERE p.dataReferencia = date($data_referencia)
WITH e, pc, collect(p) AS posicoes, sum(p.quantidade) AS saldo
CREATE (r:PosicaoRede {id: pc.codigo + '@' + e.codigo + '@' + $data_referencia, dataReferencia: date($data_referencia),
                       saldoRede: saldo,
                       valorACusto: CASE WHEN pc.custoUnitario IS NULL THEN null ELSE round(saldo * pc.custoUnitario, 2) END,
                       alertaConsistencia: CASE WHEN saldo < 0 THEN 'Saldo negativo na rede' END})
CREATE (r)-[:REFERE_SE_A]->(pc)
CREATE (r)-[:AVALIADA_NO_ESCOPO]->(e)
FOREACH (p IN posicoes | CREATE (r)-[:CONSOLIDA]->(p))
RETURN count(r) AS posicoes_na_rede, sum(CASE WHEN saldo > 0 THEN 1 ELSE 0 END) AS com_saldo_positivo;

// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Última venda válida na rede (a maior data entre as filiais do escopo, nunca a média), dias sem venda e idade em meses de calendário desde o lançamento. Sem venda na janela, os dias contam desde o lançamento ou do início do histórico.
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor), (r)-[:AVALIADA_NO_ESCOPO]->(e:EscopoRede)
OPTIONAL MATCH (e)-[:INCLUI_FILIAL]->(:Filial)<-[:OCORREU_EM]-(v:Venda)-[:REFERE_SE_A]->(pc)
  WHERE v.tipoMovimento IN $tipos_venda_valida AND v.dataVenda <= r.dataReferencia
WITH r, pc, max(v.dataVenda) AS ultima
WITH r, pc, ultima,
     CASE WHEN ultima IS NOT NULL THEN ultima
          WHEN pc.dataLancamento IS NULL THEN null
          WHEN pc.dataLancamento > date($inicio_historico_vendas) THEN pc.dataLancamento
          ELSE date($inicio_historico_vendas) END AS desde
SET r.ultimaVendaValida = ultima,
    r.diasSemVenda = CASE WHEN desde IS NULL THEN null ELSE duration.inDays(desde, r.dataReferencia).days END,
    r.idadeMeses = CASE WHEN pc.dataLancamento IS NULL THEN null ELSE duration.inMonths(pc.dataLancamento, r.dataReferencia).months END
RETURN count(r) AS posicoes_avaliadas, count(ultima) AS com_venda_valida;

// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Fase da coleção original na data de referência (ON, SALE, OFF 1, OFF 2, OFF 3).
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(:ProdutoCor)-[:TEM_COLECAO_ORIGINAL]->(c:Colecao)
WITH r, CASE WHEN r.dataReferencia >= c.inicioOff3 THEN 'FaseOFF3'
             WHEN r.dataReferencia >= c.inicioOff2 THEN 'FaseOFF2'
             WHEN r.dataReferencia >= c.inicioOff1 THEN 'FaseOFF1'
             WHEN r.dataReferencia >= c.inicioSale THEN 'FaseSALE'
             ELSE 'FaseON' END AS fase
MATCH (f:FaseColecao {nome: fase})
CREATE (r)-[:NA_FASE]->(f)
RETURN fase, count(r) AS posicoes ORDER BY fase;

// regra: R00 | versao: 0.3.0 | area: Planejamento
// descricao: Custo de oportunidade = valor a custo x taxa anual de custo de capital x dias sem venda / 365. Proposta original do projeto, usada para priorizar onde agir primeiro.
MATCH (r:PosicaoRede)
WHERE r.saldoRede > 0 AND r.valorACusto IS NOT NULL AND r.diasSemVenda IS NOT NULL
SET r.custoOportunidade = round(r.valorACusto * $taxa_custo_capital_anual * r.diasSemVenda / 365.0, 2)
RETURN count(r) AS posicoes_com_custo;
