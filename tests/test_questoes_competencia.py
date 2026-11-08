"""Um teste por questão de competência (docs/questoes_competencia.md)."""
import pytest

from retail_ontologos.carga import ler_parametros
from retail_ontologos.gerar_dados import CASOS_CONTROLE


def test_cq01_toda_observacao_tem_um_unico_diagnostico(consultar):
    linhas = consultar("""
        MATCH (o:ObservacaoEstoque)
        OPTIONAL MATCH (o)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)
        WITH o, count(d) AS n WHERE n <> 1 RETURN o.id AS obs, n""")
    assert linhas == []


@pytest.mark.parametrize("sku,esperada", [(c[0], c[6]) for c in CASOS_CONTROLE])
def test_cq01_casos_de_controle(consultar, sku, esperada):
    [linha] = consultar("""
        MATCH (:Produto {sku: $sku})-[:POSSUI_OBSERVACAO]->()-[:RECEBE_DIAGNOSTICO]->()
              -[:CLASSIFICADO_COMO]->(c:CategoriaDiagnostico)
        RETURN c.nome AS categoria""", sku=sku)
    assert linha["categoria"] == esperada


def test_cq02_diagnosticos_nao_ativos_tem_evidencia_com_indicador(consultar):
    linhas = consultar("""
        MATCH (d:Diagnostico)-[:CLASSIFICADO_COMO]->(c:CategoriaDiagnostico)
        WHERE c.nome IN ['Excesso', 'Envelhecido', 'LentoOuObsoleto']
          AND NOT EXISTS { (d)-[:FUNDAMENTADO_EM]->(:Evidencia)-[:BASEADA_EM_INDICADOR]->(:Indicador) }
        RETURN d.id AS diagnostico""")
    assert linhas == []


def test_cq03_evidencias_apontam_criterio_e_valor(consultar):
    sem_criterio = consultar("""
        MATCH (e:Evidencia) WHERE NOT EXISTS { (e)-[:ATENDE_CRITERIO]->(:CriterioDiagnostico) }
        RETURN e.id AS evidencia""")
    assert sem_criterio == []
    limites = ler_parametros()["limites"]
    violacoes = consultar("""
        MATCH (e:Evidencia)-[:ATENDE_CRITERIO]->(:CriterioDiagnostico {id: 'C01'})
        WHERE e.valorObservado <= $limite RETURN e.id AS evidencia""",
                          limite=limites["idade_estoque_dias"])
    assert violacoes == []


def test_cq04_todo_obsoleto_recebe_recomendacao(consultar):
    linhas = consultar("""
        MATCH (d:Diagnostico)-[:CLASSIFICADO_COMO]->(:CategoriaDiagnostico {nome: 'LentoOuObsoleto'})
        WHERE NOT EXISTS { (d)-[:RECOMENDA]->(:Recomendacao)-[:SUGERE_ACAO]->(:AcaoDestinacao) }
        RETURN d.id AS diagnostico""")
    assert linhas == []


def test_cq05_toda_recomendacao_aponta_regra_versionada(consultar):
    linhas = consultar("""
        MATCH (r:Recomendacao)
        OPTIONAL MATCH (r)-[:GERADO_POR_REGRA]->(regra:RegraNegocio)-[:PERSPECTIVA_DE]->(:AreaNegocio)
        WITH r, regra WHERE regra IS NULL OR regra.versao IS NULL
        RETURN r.id AS recomendacao""")
    assert linhas == []


def test_cq06_diagnostico_varia_entre_lojas(consultar):
    [linha] = consultar("""
        MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->()-[:RECEBE_DIAGNOSTICO]->()-[:CLASSIFICADO_COMO]->(c)
        WITH p, count(DISTINCT c) AS categorias WHERE categorias > 1
        RETURN count(p) AS skus""")
    assert linha["skus"] > 0


def test_cq07_falta_de_registro_nunca_vira_obsoleto(consultar):
    linhas = consultar("""
        MATCH (o:ObservacaoEstoque)-[:RECEBE_DIAGNOSTICO]->()-[:CLASSIFICADO_COMO]->(c)
        WHERE NOT EXISTS { (o)-[:POSSUI_INDICADOR]->()-[:DO_TIPO]->(:TipoIndicador {nome: 'VendasPeriodo'}) }
          AND c.nome <> 'DadosInsuficientes'
        RETURN o.id AS obs""")
    assert linhas == []
    [linha] = consultar("""
        MATCH ()-[:CLASSIFICADO_COMO]->(:CategoriaDiagnostico {nome: 'DadosInsuficientes'})
        RETURN count(*) AS n""")
    assert linha["n"] > 0


def test_cq08_custo_de_oportunidade_confere_com_a_formula(consultar):
    taxa = ler_parametros()["financeiro"]["taxa_custo_capital_anual"]
    [linha] = consultar("""
        MATCH (p:Produto {sku: 'CTRL-OBSOLETO'})-[:POSSUI_OBSERVACAO]->(o)-[:POSSUI_INDICADOR]->(i)
              -[:DO_TIPO]->(:TipoIndicador {nome: 'CustoOportunidade'})
        RETURN i.valor AS valor""")
    assert linha["valor"] == pytest.approx(round(100.0 * 450 * taxa * 320 / 365, 2))
    sem_custo = consultar("""
        MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o)-[:POSSUI_INDICADOR]->()
              -[:DO_TIPO]->(:TipoIndicador {nome: 'CustoOportunidade'})
        WHERE p.custoUnitario IS NULL RETURN o.id AS obs""")
    assert sem_custo == []
