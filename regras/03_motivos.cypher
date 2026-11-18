// regra: R02 | versao: 0.2.0 | area: Planejamento
// descricao: Motivo marca descontinuada: a marca do produto está descontinuada na data de referência. Coexiste com qualquer situação.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'MarcaDescontinuada'})
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(:ProdutoCor)-[:VARIACAO_DE]->(:Produto)-[:PERTENCE_A_MARCA]->(m:Marca)
WHERE r.saldoRede > 0 AND m.descontinuadaDesde IS NOT NULL AND m.descontinuadaDesde <= r.dataReferencia
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-MarcaDescontinuada', justificativa: 'Marca ' + m.nome + ' descontinuada desde ' + toString(m.descontinuadaDesde)})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M01 marca descontinuada', justificativa: mo.justificativa})
RETURN count(mo) AS motivos;

// regra: R02 | versao: 0.2.0 | area: Operacoes
// descricao: Motivo produto com defeito: há saldo do produto-cor em filial de defeito. A quantidade afetada é registrada por filial.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'ProdutoComDefeito'})
MATCH (r:PosicaoRede)-[:CONSOLIDA]->(p:PosicaoEstoque)-[:TEM_CONDICAO]->(:CondicaoComercial {nome: 'ComDefeito'}),
      (p)-[:ESTA_EM]->(f:Filial)
WHERE r.saldoRede > 0 AND p.quantidade > 0
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-ProdutoComDefeito-' + f.codigo,
        justificativa: toString(p.quantidade) + ' peças com defeito em ' + f.nome + ', já no fluxo de qualidade'})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:NA_FILIAL]->(f)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M02 saldo em filial de defeito',
        valorObservado: p.quantidade, justificativa: mo.justificativa})
RETURN count(mo) AS motivos;

// regra: R02 | versao: 0.2.0 | area: Comercial
// descricao: Motivo produto cancelado: o estilo pediu para recolher o produto-cor da venda, em todas as filiais.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'ProdutoCancelado'})
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor {canceladoPeloEstilo: true})
WHERE r.saldoRede > 0
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-ProdutoCancelado', justificativa: 'Produto-cor ' + pc.codigo + ' cancelado pelo estilo'})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M03 cancelado pelo estilo', justificativa: mo.justificativa})
RETURN count(mo) AS motivos;

// regra: R02 | versao: 0.2.0 | area: Comercial
// descricao: Motivo oportunidade local: a rede tem giro, mas uma filial de venda aberta há mais de 12 meses está há mais de 180 dias sem venda válida do produto-cor. Filial nova, CD e filial de defeito não entram.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'OportunidadeLocal'})
MATCH (r:PosicaoRede)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
WHERE s.nome IN ['Ativo', 'AntigoComGiro']
MATCH (r)-[:REFERE_SE_A]->(pc:ProdutoCor), (r)-[:CONSOLIDA]->(p:PosicaoEstoque)-[:ESTA_EM]->(f:Filial)-[:DO_TIPO_FILIAL]->(:TipoFilial {nome: 'FilialVenda'})
WHERE p.quantidade > 0 AND f.dataFechamento IS NULL
  AND r.dataReferencia > f.dataAbertura + duration({months: $meses_filial_nova})
OPTIONAL MATCH (f)<-[:OCORREU_EM]-(v:Venda)-[:REFERE_SE_A]->(pc)
  WHERE v.tipoMovimento IN $tipos_venda_valida AND v.dataVenda <= r.dataReferencia
WITH regra, t, r, pc, p, f, max(v.dataVenda) AS ultimaLocal
WITH regra, t, r, p, f, ultimaLocal,
     duration.inDays(coalesce(ultimaLocal,
        CASE WHEN pc.dataLancamento > date($inicio_historico_vendas) THEN pc.dataLancamento ELSE date($inicio_historico_vendas) END),
        r.dataReferencia).days AS diasLocal
WHERE diasLocal > $dias_sem_venda
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-OportunidadeLocal-' + f.codigo,
        justificativa: toString(p.quantidade) + ' peças paradas em ' + f.nome + ' há ' + toString(diasLocal)
                       + ' dias, enquanto a rede vendeu em ' + toString(r.ultimaVendaValida)})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:NA_FILIAL]->(f)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M04 sem venda local com giro na rede',
        valorObservado: diasLocal, limite: $dias_sem_venda, justificativa: mo.justificativa})
RETURN count(mo) AS motivos;

// regra: R02 | versao: 0.2.0 | area: Operacoes
// descricao: Motivo bloqueio de envio: há bloqueio vigente do produto-cor para uma filial de destino. Quando a situação é sem giro, o bloqueio é registrado como causa provável da falta de venda.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'BloqueioDeEnvio'})
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(:ProdutoCor)-[:TEM_CLASSIFICACAO]->(c:ClassificacaoVigencia)-[:TEM_VALOR]->(:TipoRestricao {nome: 'BloqueioEnvio'}),
      (c)-[:RESTRINGE_DESTINO]->(f:Filial)
WHERE r.saldoRede > 0 AND c.validoDe <= r.dataReferencia AND (c.validoAte IS NULL OR c.validoAte >= r.dataReferencia)
MATCH (r)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-BloqueioDeEnvio-' + f.codigo,
        justificativa: 'Envio bloqueado para ' + f.nome + ' desde ' + toString(c.validoDe)
                       + CASE WHEN s.nome IN ['SemGiroEmAtencao', 'PotencialmenteObsoleto'] THEN ': causa provável da falta de venda' ELSE '' END})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:NA_FILIAL]->(f)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M05 bloqueio vigente', justificativa: mo.justificativa})
RETURN count(mo) AS motivos;

// regra: R02 | versao: 0.2.0 | area: Planejamento
// descricao: Motivo contínuo com sinal de obsolescência: produto-cor classificado como contínuo segue a mesma regra; se estiver sem giro, a classificação deve ser revista com a área de negócio.
MATCH (regra:RegraNegocio {id: 'R02'}), (t:TipoMotivo {nome: 'ContinuoComSinalObsolescencia'})
MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(:ProdutoCor)-[:TEM_CLASSIFICACAO]->(c:ClassificacaoVigencia)-[:TEM_VALOR]->(:TipoColecao {nome: 'TipoColecaoContinuo'})
WHERE c.validoDe <= r.dataReferencia AND (c.validoAte IS NULL OR c.validoAte >= r.dataReferencia)
MATCH (r)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
WHERE s.nome IN ['SemGiroEmAtencao', 'PotencialmenteObsoleto']
CREATE (r)-[:TEM_MOTIVO]->(mo:Motivo {id: r.id + '-ContinuoComSinalObsolescencia',
        justificativa: 'Produto classificado como contínuo, mas ' + toLower(s.descricao) + ' há ' + toString(r.diasSemVenda) + ' dias sem venda'})
CREATE (mo)-[:DO_TIPO_MOTIVO]->(t)
CREATE (mo)-[:GERADO_POR_REGRA]->(regra)
CREATE (mo)-[:SUSTENTADO_POR]->(:Evidencia {id: mo.id + '-E', criterio: 'M06 contínuo sem giro', justificativa: mo.justificativa})
RETURN count(mo) AS motivos;
