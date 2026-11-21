// regra: R03 | versao: 0.3.0 | area: Comercial
// descricao: Marca descontinuada: recomendar baixa do percentual configurado (100%), condicionada ao cadastro oficial e ao fluxo de aprovação.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'Baixa'})
MATCH (mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'MarcaDescontinuada'})
CREATE (rec:Recomendacao {id: mo.id + '-R03', percentualSugerido: $percentual_baixa_marca_descontinuada,
        justificativa: 'Baixa de ' + toString($percentual_baixa_marca_descontinuada) + '%, condicionada ao cadastro oficial e à aprovação'})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Operacoes
// descricao: Produto cancelado pelo estilo: recolher ao CD e enviar à filial de defeito que vende, a única autorizada a vender esse tipo de produto.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'RecolherEnviarFilialDefeito'})
MATCH (mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'ProdutoCancelado'})
CREATE (rec:Recomendacao {id: mo.id + '-R03', percentualSugerido: 100,
        justificativa: 'Produto cancelado: recolher todo o saldo ao CD e enviar à filial de defeito que vende'})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Comercial
// descricao: Oportunidade local: transferir para filiais de venda do escopo que venderam o produto-cor nos últimos 180 dias e não têm bloqueio vigente.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'Transferencia'})
MATCH (r:PosicaoRede)-[:TEM_MOTIVO]->(mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'OportunidadeLocal'}),
      (mo)-[:NA_FILIAL]->(origem:Filial), (r)-[:REFERE_SE_A]->(pc:ProdutoCor), (r)-[:AVALIADA_NO_ESCOPO]->(e:EscopoRede)
OPTIONAL MATCH (e)-[:INCLUI_FILIAL]->(destino:Filial)<-[:OCORREU_EM]-(v:Venda)-[:REFERE_SE_A]->(pc)
  WHERE destino <> origem AND v.tipoMovimento IN $tipos_venda_valida
    AND v.dataVenda <= r.dataReferencia AND v.dataVenda >= r.dataReferencia - duration({days: $dias_sem_venda})
    AND EXISTS { (destino)-[:DO_TIPO_FILIAL]->(:TipoFilial {nome: 'FilialVenda'}) }
    AND NOT EXISTS { (pc)-[:TEM_CLASSIFICACAO]->(b:ClassificacaoVigencia)-[:RESTRINGE_DESTINO]->(destino)
                     WHERE b.validoDe <= r.dataReferencia AND (b.validoAte IS NULL OR b.validoAte >= r.dataReferencia) }
WITH regra, a, mo, origem, collect(DISTINCT destino) AS destinos
CREATE (rec:Recomendacao {id: mo.id + '-R03',
        justificativa: 'Transferir de ' + origem.nome + CASE WHEN size(destinos) = 0 THEN ' (sem destino com venda recente: avaliar exposição ou ação comercial)'
                       ELSE ' para filiais com venda recente: ' + reduce(s = '', d IN destinos | s + CASE WHEN s = '' THEN '' ELSE ', ' END + d.nome) END})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
FOREACH (d IN destinos | CREATE (rec)-[:DESTINO_SUGERIDO]->(d))
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Operacoes
// descricao: Bloqueio de envio: manter no CD enquanto o bloqueio estiver vigente (pode ser temporário ou de uma filial específica).
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'ManterNoCD'})
MATCH (mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'BloqueioDeEnvio'}), (mo)-[:NA_FILIAL]->(f:Filial)
CREATE (rec:Recomendacao {id: mo.id + '-R03', justificativa: 'Manter no CD enquanto vigorar o bloqueio de envio para ' + f.nome})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Planejamento
// descricao: Contínuo com sinal de obsolescência: levar à área de negócio a revisão da classificação de contínuo e a avaliação da descontinuação.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'RevisarClassificacao'})
MATCH (mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'ContinuoComSinalObsolescencia'})
CREATE (rec:Recomendacao {id: mo.id + '-R03', justificativa: 'Levar à área de negócio: revisar a classificação de contínuo e avaliar a descontinuação'})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Comercial
// descricao: Coleção com mais de 5 anos sem giro: produto sem valor comercial, recomendar baixa do percentual configurado, condicionada à aprovação (revisão de 20/11/2026).
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'Baixa'})
MATCH (mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'ColecaoMuitoAntiga'})
CREATE (rec:Recomendacao {id: mo.id + '-R03', percentualSugerido: $percentual_baixa_sem_valor_comercial,
        justificativa: 'Coleção com mais de 5 anos e sem giro: baixa de ' + toString($percentual_baixa_sem_valor_comercial) + '%, condicionada à aprovação'})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Operacoes
// descricao: Produto com defeito sem giro: as peças da filial de defeito não têm valor comercial; recomendar baixa do percentual configurado, condicionada à aprovação (revisão de 20/11/2026). Com giro, seguem o fluxo de qualidade sem recomendação.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'Baixa'})
MATCH (r:PosicaoRede)-[:TEM_MOTIVO]->(mo:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'ProdutoComDefeito'}),
      (r)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade),
      (mo)-[:NA_FILIAL]->(f:Filial)
WHERE s.nome IN ['SemGiroEmAtencao', 'PotencialmenteObsoleto']
CREATE (rec:Recomendacao {id: mo.id + '-R03', percentualSugerido: $percentual_baixa_sem_valor_comercial,
        justificativa: 'Peças com defeito em ' + f.nome + ' e produto sem giro: baixa de ' + toString($percentual_baixa_sem_valor_comercial) + '% dessas peças, condicionada à aprovação'})
CREATE (rec)-[:CONSIDERA]->(mo)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Comercial
// descricao: Potencialmente obsoleto: ação comercial (remarcar, promocionar, expor com sinalização) e avaliação de write-off, sem baixa automática (seção 8 das definições). Não se aplica quando já há recomendação de baixa por coleção com mais de 5 anos.
MATCH (regra:RegraNegocio {id: 'R03'}), (a:AcaoDestinacao {nome: 'AcaoComercial'})
MATCH (r:PosicaoRede)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)-[:CLASSIFICADO_COMO]->(:SituacaoGiroIdade {nome: 'PotencialmenteObsoleto'})
WHERE NOT EXISTS { (r)-[:TEM_MOTIVO]->(:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'ColecaoMuitoAntiga'}) }
CREATE (rec:Recomendacao {id: d.id + '-R03',
        justificativa: 'Potencialmente obsoleto: ação comercial (remarcar, promocionar) e avaliar write-off; sem baixa automática'})
CREATE (rec)-[:CONSIDERA]->(d)
CREATE (rec)-[:SUGERE_ACAO]->(a)
CREATE (rec)-[:GERADO_POR_REGRA]->(regra)
RETURN count(rec) AS recomendacoes;

// regra: R03 | versao: 0.3.0 | area: Planejamento
// descricao: Prioridade: ordena as recomendações pelo custo de oportunidade da posição na rede (1 = atuar primeiro). O excesso entra como qualificador quando a fórmula estiver definida.
MATCH (rec:Recomendacao)-[:CONSIDERA]->(x)
MATCH (r:PosicaoRede) WHERE (r)-[:TEM_MOTIVO]->(x) OR (r)-[:RECEBE_DIAGNOSTICO]->(x)
WITH rec, max(coalesce(r.custoOportunidade, 0)) AS custo
ORDER BY custo DESC, rec.id
WITH collect(rec) AS recs
UNWIND range(0, size(recs) - 1) AS i
WITH recs[i] AS rec, i
SET rec.prioridade = i + 1
RETURN count(rec) AS recomendacoes_priorizadas;
