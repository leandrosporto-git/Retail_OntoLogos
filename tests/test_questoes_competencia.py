"""Um teste por questão de competência (docs/questoes_competencia.md).

Os casos de controle (gerar_dados.CASOS_CONTROLE) reproduzem os casos de validação
do documento de definições e os casos de limite acordados em 17/11/2026.
"""
import pytest

from retail_ontologos.carga import ler_parametros
from retail_ontologos.gerar_dados import CASOS_CONTROLE

PARAM = ler_parametros()


def _situacao(consultar, pc):
    return consultar("""
        MATCH (:ProdutoCor {codigo: $pc})<-[:REFERE_SE_A]-(r:PosicaoRede)
        OPTIONAL MATCH (r)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
        RETURN s.nome AS situacao""", pc=pc)


def _motivos(consultar, pc):
    return consultar("""
        MATCH (:ProdutoCor {codigo: $pc})<-[:REFERE_SE_A]-(:PosicaoRede)-[:TEM_MOTIVO]->(m:Motivo)-[:DO_TIPO_MOTIVO]->(t)
        OPTIONAL MATCH (m)-[:NA_FILIAL]->(f:Filial)
        OPTIONAL MATCH (rec:Recomendacao)-[:CONSIDERA]->(m)
        OPTIONAL MATCH (rec)-[:SUGERE_ACAO]->(a:AcaoDestinacao)
        RETURN t.nome AS motivo, f.codigo AS filial, a.nome AS acao, rec.percentualSugerido AS percentual,
               m.justificativa AS justificativa""", pc=pc)


# CQ01 -----------------------------------------------------------------------
def test_cq01_toda_posicao_com_saldo_tem_um_unico_diagnostico(consultar):
    assert consultar("""
        MATCH (r:PosicaoRede) WHERE r.saldoRede > 0
        OPTIONAL MATCH (r)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)
        WITH r, count(d) AS n WHERE n <> 1 RETURN r.id AS posicao, n""") == []
    assert consultar("""
        MATCH (r:PosicaoRede)-[:RECEBE_DIAGNOSTICO]->() WHERE r.saldoRede <= 0 RETURN r.id AS posicao""") == []


# CQ02 -----------------------------------------------------------------------
@pytest.mark.parametrize("pc,esperada", [(c[0], c[5]) for c in CASOS_CONTROLE if c[5]])
def test_cq02_casos_de_validacao(consultar, pc, esperada):
    assert _situacao(consultar, pc) == [{"situacao": esperada}]


# CQ03 -----------------------------------------------------------------------
def test_cq03_todo_diagnostico_tem_evidencias_e_regra_versionada(consultar):
    assert consultar("""
        MATCH (d:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
        WITH d, s, [(d)-[:SUSTENTADO_POR]->(e:Evidencia) | left(e.criterio, 3)] AS criterios
        WHERE NOT 'C01' IN criterios
           OR (s.nome = 'DiagnosticoPendente' AND NOT 'C04' IN criterios)
           OR (s.nome <> 'DiagnosticoPendente' AND NOT ('C02' IN criterios AND 'C03' IN criterios))
           OR NOT EXISTS { (d)-[:GERADO_POR_REGRA]->(r:RegraNegocio) WHERE r.versao = $versao }
        RETURN d.id AS diagnostico""", versao=PARAM["versao_regras"]) == []


# CQ04 -----------------------------------------------------------------------
def test_cq04_situacao_bate_com_os_valores_e_limites_estritos(consultar):
    lim = PARAM["limites"]
    assert consultar("""
        MATCH (r:PosicaoRede)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
        WHERE s.nome <> 'DiagnosticoPendente'
        MATCH (r)-[:REFERE_SE_A]->(pc:ProdutoCor)
        WITH r, s, r.diasSemVenda > $dias AS semGiro,
             r.dataReferencia > pc.dataLancamento + duration({months: $meses}) AS antigo
        WITH r, s, CASE WHEN semGiro AND antigo THEN 'PotencialmenteObsoleto' WHEN semGiro THEN 'SemGiroEmAtencao'
                        WHEN antigo THEN 'AntigoComGiro' ELSE 'Ativo' END AS esperada
        WHERE s.nome <> esperada RETURN r.id AS posicao, s.nome AS situacao, esperada""",
                     dias=lim["dias_sem_venda"], meses=lim["idade_meses"]) == []
    assert _situacao(consultar, "CTRL-LIMITE") == [{"situacao": "Ativo"}]


# CQ05 -----------------------------------------------------------------------
def test_cq05_motivos_coexistem_com_a_situacao(consultar):
    assert _situacao(consultar, "CTRL-DESCONT") == [{"situacao": "Ativo"}]
    [m] = _motivos(consultar, "CTRL-DESCONT")
    assert (m["motivo"], m["acao"], m["percentual"]) == ("MarcaDescontinuada", "Baixa", 100)
    [m] = _motivos(consultar, "CTRL-DEFEITO")
    assert (m["motivo"], m["filial"]) == ("ProdutoComDefeito", "F10")


# CQ06 -----------------------------------------------------------------------
def test_cq06_oportunidade_local_so_em_filial_de_venda_com_historico(consultar):
    [m] = _motivos(consultar, "CTRL-LOCAL")
    assert (m["motivo"], m["filial"], m["acao"]) == ("OportunidadeLocal", "F03", "Transferencia")
    [destino] = consultar("""
        MATCH (:ProdutoCor {codigo: 'CTRL-LOCAL'})<-[:REFERE_SE_A]-(:PosicaoRede)-[:TEM_MOTIVO]->(m)
              <-[:CONSIDERA]-(:Recomendacao)-[:DESTINO_SUGERIDO]->(f:Filial)
        RETURN f.codigo AS filial""")
    assert destino["filial"] == "F02"
    assert _motivos(consultar, "CTRL-LOJA-NOVA") == []  # loja aberta há menos de 12 meses
    assert consultar("""
        MATCH (m:Motivo)-[:DO_TIPO_MOTIVO]->(:TipoMotivo {nome: 'OportunidadeLocal'}), (m)-[:NA_FILIAL]->(f:Filial)
        WHERE NOT EXISTS { (f)-[:DO_TIPO_FILIAL]->(:TipoFilial {nome: 'FilialVenda'}) }
           OR f.dataAbertura + duration({months: $meses}) >= date($ref)
        RETURN m.id AS motivo""", meses=PARAM["limites"]["meses_filial_nova"], ref=PARAM["data_referencia"]) == []


# CQ07 -----------------------------------------------------------------------
def test_cq07_so_vendas_validas_do_escopo_contam(consultar):
    assert _situacao(consultar, "CTRL-CANCELADAS") == [{"situacao": "PotencialmenteObsoleto"}]
    assert _situacao(consultar, "CTRL-FORA-ESCOPO") == []      # saldo só em filial fora do escopo
    assert _situacao(consultar, "CTRL-NOME-ANTIGO") == [{"situacao": "AntigoComGiro"}]  # venda com nome antigo


# CQ08 -----------------------------------------------------------------------
def test_cq08_custo_de_oportunidade_e_prioridade(consultar):
    taxa = PARAM["financeiro"]["taxa_custo_capital_anual"]
    [linha] = consultar("""
        MATCH (:ProdutoCor {codigo: 'CTRL-OBSOLETO'})<-[:REFERE_SE_A]-(r:PosicaoRede)
        RETURN r.custoOportunidade AS custo""")
    assert linha["custo"] == pytest.approx(round(450 * 100.0 * taxa * 200 / 365, 2))
    prioridades = consultar("""
        MATCH (rec:Recomendacao)-[:CONSIDERA]->(x)
        MATCH (r:PosicaoRede) WHERE (r)-[:TEM_MOTIVO]->(x) OR (r)-[:RECEBE_DIAGNOSTICO]->(x)
        WITH rec, max(coalesce(r.custoOportunidade, 0)) AS custo
        RETURN rec.prioridade AS prioridade, custo ORDER BY prioridade""")
    assert [p["prioridade"] for p in prioridades] == list(range(1, len(prioridades) + 1))
    custos = [p["custo"] for p in prioridades]
    assert custos == sorted(custos, reverse=True)


# CQ09 -----------------------------------------------------------------------
def test_cq09_recomendacoes_sao_rastreaveis(consultar):
    assert consultar("""
        MATCH (rec:Recomendacao)
        WHERE NOT EXISTS { (rec)-[:CONSIDERA]->() }
           OR NOT EXISTS { (rec)-[:SUGERE_ACAO]->(:AcaoDestinacao) }
           OR NOT EXISTS { (rec)-[:GERADO_POR_REGRA]->(r:RegraNegocio) WHERE r.versao IS NOT NULL }
        RETURN rec.id AS recomendacao""") == []
    assert consultar("""
        MATCH (d:Diagnostico)-[:CLASSIFICADO_COMO]->(:SituacaoGiroIdade {nome: 'PotencialmenteObsoleto'})
        WHERE NOT EXISTS { (:Recomendacao)-[:CONSIDERA]->(d) } RETURN d.id AS diagnostico""") == []
    # Todo motivo tem recomendação, exceto defeito: as peças já estão no fluxo de qualidade.
    assert consultar("""
        MATCH (m:Motivo)-[:DO_TIPO_MOTIVO]->(t:TipoMotivo) WHERE t.nome <> 'ProdutoComDefeito'
          AND NOT EXISTS { (:Recomendacao)-[:CONSIDERA]->(m) } RETURN m.id AS motivo""") == []


# CQ10 -----------------------------------------------------------------------
def test_cq10_dado_inconsistente_ou_incompleto_nao_vira_obsoleto(consultar):
    [linha] = consultar("""
        MATCH (:ProdutoCor {codigo: 'CTRL-NEGATIVO'})<-[:REFERE_SE_A]-(r:PosicaoRede)
        RETURN r.alertaConsistencia AS alerta, EXISTS { (r)-[:RECEBE_DIAGNOSTICO]->() } AS tem_diagnostico""")
    assert linha == {"alerta": "Saldo negativo na rede", "tem_diagnostico": False}
    assert consultar("""
        MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor), (r)-[:RECEBE_DIAGNOSTICO]->()-[:CLASSIFICADO_COMO]->(s)
        WHERE pc.dataLancamento IS NULL AND s.nome <> 'DiagnosticoPendente' RETURN r.id AS posicao""") == []


# CQ11 -----------------------------------------------------------------------
@pytest.mark.parametrize("pc,motivo,acao", [
    ("CTRL-CANCELADO", "ProdutoCancelado", "RecolherEnviarFilialDefeito"),
    ("CTRL-BLOQUEIO", "BloqueioDeEnvio", "ManterNoCD"),
    ("CTRL-CONTINUO", "ContinuoComSinalObsolescencia", "RevisarClassificacao"),
])
def test_cq11_destinacao_por_motivo(consultar, pc, motivo, acao):
    [m] = _motivos(consultar, pc)
    assert (m["motivo"], m["acao"]) == (motivo, acao)


def test_cq11_bloqueio_explica_a_falta_de_venda(consultar):
    [m] = _motivos(consultar, "CTRL-BLOQUEIO")
    assert "causa provável" in m["justificativa"]
