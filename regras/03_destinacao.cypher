// regra: R02 | versao: 0.1.0 | area: Operacoes
// descricao: Recomenda transferência entre lojas quando o estoque está em Excesso ou Lento ou obsoleto em uma loja e o mesmo SKU tem boa saída (Ativo ou Envelhecido) em outra loja.
MATCH (r:RegraNegocio {id: 'R02'}), (acao:AcaoDestinacao {nome: 'TransferenciaEntreLojas'})
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)-[:CLASSIFICADO_COMO]->(cat:CategoriaDiagnostico)
WHERE cat.nome IN ['Excesso', 'LentoOuObsoleto']
MATCH (p)-[:POSSUI_OBSERVACAO]->(o2:ObservacaoEstoque)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(cat2:CategoriaDiagnostico)
WHERE o2 <> o AND cat2.nome IN ['Ativo', 'Envelhecido']
MATCH (o2)-[:LOCALIZADA_EM]->(destino:Loja)
WITH r, acao, d, collect(DISTINCT destino.nome) AS destinos
CREATE (d)-[:RECOMENDA]->(rec:Recomendacao {id: d.id + '-R02',
        justificativa: 'O mesmo SKU tem boa saída em: ' + reduce(s = '', x IN destinos | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x)})
CREATE (rec)-[:SUGERE_ACAO]->(acao)
CREATE (rec)-[:GERADO_POR_REGRA]->(r)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.1.0 | area: Comercial
// descricao: Recomenda remarcação para estoque em Excesso e para estoque Lento ou obsoleto de coleção ainda vigente.
MATCH (r:RegraNegocio {id: 'R03'}), (acao:AcaoDestinacao {nome: 'Remarcacao'})
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)-[:CLASSIFICADO_COMO]->(cat:CategoriaDiagnostico)
MATCH (p)-[:PERTENCE_A_COLECAO]->(col:Colecao)
WHERE cat.nome = 'Excesso' OR (cat.nome = 'LentoOuObsoleto' AND NOT col.encerrada)
CREATE (d)-[:RECOMENDA]->(rec:Recomendacao {id: d.id + '-R03',
        justificativa: 'Estoque ' + toLower(cat.descricao) + ' em coleção ' + CASE WHEN col.encerrada THEN 'encerrada' ELSE 'vigente' END + ': reduzir preço para acelerar a venda'})
CREATE (rec)-[:SUGERE_ACAO]->(acao)
CREATE (rec)-[:GERADO_POR_REGRA]->(r)
RETURN count(rec) AS recomendacoes;

// regra: R04 | versao: 0.1.0 | area: Comercial
// descricao: Recomenda liquidação (por exemplo, no canal outlet) para estoque Lento ou obsoleto de coleção encerrada.
MATCH (r:RegraNegocio {id: 'R04'}), (acao:AcaoDestinacao {nome: 'Liquidacao'})
MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)-[:CLASSIFICADO_COMO]->(:CategoriaDiagnostico {nome: 'LentoOuObsoleto'})
MATCH (p)-[:PERTENCE_A_COLECAO]->(col:Colecao {encerrada: true})
CREATE (d)-[:RECOMENDA]->(rec:Recomendacao {id: d.id + '-R04',
        justificativa: 'Estoque lento ou obsoleto da coleção ' + col.nome + ', já encerrada: liquidar'})
CREATE (rec)-[:SUGERE_ACAO]->(acao)
CREATE (rec)-[:GERADO_POR_REGRA]->(r)
RETURN count(rec) AS recomendacoes;
