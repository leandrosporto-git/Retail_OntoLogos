"""Interface do Retail OntoLogos.

Execute com:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retail_ontologos import carga, motor  # noqa: E402
from retail_ontologos.conexao import conectar  # noqa: E402

st.set_page_config(page_title="Retail OntoLogos", layout="wide")

SITUACOES = ["Ativo", "AntigoComGiro", "SemGiroEmAtencao", "PotencialmenteObsoleto", "DiagnosticoPendente"]
ROTULOS = {"Ativo": "Ativo", "AntigoComGiro": "Antigo com giro", "SemGiroEmAtencao": "Sem giro em atenção",
           "PotencialmenteObsoleto": "Potencialmente obsoleto", "DiagnosticoPendente": "Diagnóstico pendente"}


@st.cache_resource
def driver():
    return conectar()


def consultar(cypher: str, **params) -> pd.DataFrame:
    with driver().session() as s:
        return pd.DataFrame(s.run(cypher, **params).data())


st.title("Retail OntoLogos")
st.caption("Diagnóstico e destinação de estoques obsoletos no varejo de moda, com regras explícitas e rastreáveis. "
           "Dados de exemplo fictícios.")

try:
    driver()
except Exception as erro:
    st.error(f"Não foi possível conectar ao Neo4j. Verifique se ele está rodando e o arquivo .env. Detalhe: {erro}")
    st.stop()

with st.sidebar:
    st.header("Dados")
    if st.button("Recarregar dados de exemplo e rodar as regras"):
        with st.spinner("Carregando..."):
            carga.carregar_tudo(carga.RAIZ / "dados" / "exemplo")
            motor.executar(verbose=False)
        st.success("Pronto.")
    st.header("Filtros")
    marcas = consultar("MATCH (:Produto)-[:PERTENCE_A_MARCA]->(m:Marca) RETURN DISTINCT m.nome AS nome ORDER BY nome")
    f_marcas = st.multiselect("Marca", marcas["nome"].tolist() if not marcas.empty else [])
    f_situacoes = st.multiselect("Situação", SITUACOES, default=["PotencialmenteObsoleto", "SemGiroEmAtencao"],
                                 format_func=ROTULOS.get)

aba_visao, aba_produto, aba_motivos, aba_regras = st.tabs(
    ["Visão geral", "Detalhe do produto-cor", "Motivos e recomendações", "Regras"])

base = consultar("""
    MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor)-[:VARIACAO_DE]->(p:Produto)-[:PERTENCE_A_MARCA]->(m:Marca)
    MATCH (r)-[:RECEBE_DIAGNOSTICO]->(:Diagnostico)-[:CLASSIFICADO_COMO]->(s:SituacaoGiroIdade)
    OPTIONAL MATCH (r)-[:NA_FASE]->(f:FaseColecao)
    RETURN pc.codigo AS `Produto-cor`, p.descricao AS Produto, m.nome AS Marca, p.subgrupo AS Subgrupo,
           s.nome AS situacao, f.descricao AS Fase, r.saldoRede AS Saldo, r.idadeMeses AS `Idade (meses)`,
           r.diasSemVenda AS `Dias sem venda`, r.valorACusto AS `Valor a custo (R$)`,
           r.custoOportunidade AS `Custo de oportunidade (R$)`,
           [(r)-[:TEM_MOTIVO]->(:Motivo)-[:DO_TIPO_MOTIVO]->(t) | t.descricao] AS Motivos""")
if base.empty:
    st.warning("O grafo está vazio. Use o botão na barra lateral para carregar os dados de exemplo.")
    st.stop()
base["Situação"] = base.pop("situacao").map(ROTULOS)

filtro = base.copy()
if f_marcas:
    filtro = filtro[filtro["Marca"].isin(f_marcas)]
if f_situacoes:
    filtro = filtro[filtro["Situação"].isin([ROTULOS[s] for s in f_situacoes])]

with aba_visao:
    c1, c2, c3 = st.columns(3)
    c1.metric("Produtos-cor no filtro", f"{len(filtro):,}".replace(",", "."))
    c2.metric("Peças", f"{int(filtro['Saldo'].sum()):,}".replace(",", "."))
    c3.metric("Custo de oportunidade (R$)", f"{filtro['Custo de oportunidade (R$)'].sum():,.0f}".replace(",", "."))
    st.subheader("Custo de oportunidade por situação")
    resumo = (base.groupby("Situação")["Custo de oportunidade (R$)"].sum()
              .reindex([ROTULOS[s] for s in SITUACOES]).fillna(0))
    st.bar_chart(resumo, horizontal=True)
    st.subheader("Produtos-cor ordenados por custo de oportunidade")
    st.dataframe(filtro.sort_values("Custo de oportunidade (R$)", ascending=False, na_position="last"),
                 hide_index=True, use_container_width=True)
    alertas = consultar("""
        MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc) WHERE r.alertaConsistencia IS NOT NULL
        RETURN pc.codigo AS `Produto-cor`, r.saldoRede AS Saldo, r.alertaConsistencia AS Alerta""")
    if not alertas.empty:
        st.info("Posições fora do diagnóstico por inconsistência de dados:")
        st.dataframe(alertas, hide_index=True)

with aba_produto:
    codigo = st.text_input("Produto-cor", value="CTRL-OBSOLETO")
    detalhe = consultar("""
        MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc:ProdutoCor {codigo: $codigo})
        MATCH (r)-[:RECEBE_DIAGNOSTICO]->(d)-[:CLASSIFICADO_COMO]->(s), (d)-[:GERADO_POR_REGRA]->(regra)
        RETURN s.descricao AS situacao, regra.id + ' v' + regra.versao AS regra,
               [(d)-[:SUSTENTADO_POR]->(e) | e.criterio + ': ' + e.justificativa] AS evidencias,
               [(r)-[:TEM_MOTIVO]->(m)-[:DO_TIPO_MOTIVO]->(t) | t.descricao + ': ' + m.justificativa] AS motivos,
               [(rec:Recomendacao)-[:CONSIDERA]->(x)<-[:TEM_MOTIVO|RECEBE_DIAGNOSTICO]-(r) |
                  '#' + toString(rec.prioridade) + ' ' + [(rec)-[:SUGERE_ACAO]->(a) | a.descricao][0] + ': ' + rec.justificativa] AS recomendacoes,
               [(r)-[:CONSOLIDA]->(p)-[:ESTA_EM]->(f) | f.nome + ': ' + toString(p.quantidade) + ' peças'] AS posicoes""",
                        codigo=codigo)
    if detalhe.empty:
        st.warning("Produto-cor sem diagnóstico (não encontrado, fora do escopo ou com saldo zero ou negativo).")
    for _, linha in detalhe.iterrows():
        with st.container(border=True):
            st.markdown(f"**{linha['situacao']}** · regra {linha['regra']}")
            st.markdown("Estoque na rede: " + "; ".join(linha["posicoes"]))
            for e in sorted(linha["evidencias"]):
                st.markdown(f"- Evidência {e}")
            for m in linha["motivos"]:
                st.markdown(f"- Motivo: {m}")
            for r in linha["recomendacoes"]:
                st.markdown(f"- Recomendação {r}")

with aba_motivos:
    st.dataframe(consultar("""
        MATCH (rec:Recomendacao)-[:SUGERE_ACAO]->(a:AcaoDestinacao), (rec)-[:CONSIDERA]->(x)
        MATCH (r:PosicaoRede)-[:REFERE_SE_A]->(pc) WHERE (r)-[:TEM_MOTIVO]->(x) OR (r)-[:RECEBE_DIAGNOSTICO]->(x)
        OPTIONAL MATCH (x)-[:DO_TIPO_MOTIVO]->(t:TipoMotivo)
        RETURN rec.prioridade AS Prioridade, pc.codigo AS `Produto-cor`,
               coalesce(t.descricao, 'Diagnóstico') AS `Considera`, a.descricao AS `Ação`,
               rec.percentualSugerido AS `%`, rec.justificativa AS Justificativa
        ORDER BY Prioridade"""), hide_index=True, use_container_width=True)

with aba_regras:
    st.dataframe(consultar("""
        MATCH (r:RegraNegocio)
        RETURN r.id AS Regra, r.versao AS `Versão`, r.areaResponsavel AS `Área`, r.arquivo AS Arquivo
        ORDER BY Regra"""), hide_index=True, use_container_width=True)
    st.markdown("Cada regra é um arquivo `.cypher` na pasta `regras/`, e os limites ficam em `regras/parametros.yaml`.")
