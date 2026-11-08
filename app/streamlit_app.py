"""Interface do FashionStockKG.

Execute com:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fashionstockkg import carga, motor  # noqa: E402
from fashionstockkg.conexao import conectar  # noqa: E402

st.set_page_config(page_title="FashionStockKG", layout="wide")

CATEGORIAS = ["Ativo", "Excesso", "Envelhecido", "LentoOuObsoleto", "DadosInsuficientes"]


@st.cache_resource
def driver():
    return conectar()


def consultar(cypher: str, **params) -> pd.DataFrame:
    with driver().session() as s:
        return pd.DataFrame(s.run(cypher, **params).data())


st.title("FashionStockKG")
st.caption("Diagnóstico e destinação de estoques obsoletos no varejo de moda, com regras explícitas e rastreáveis. "
           "Dados de exemplo fictícios; limites das regras ainda não validados com especialistas.")

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
    lojas = consultar("MATCH (l:LocalEstoque) RETURN l.nome AS nome ORDER BY nome")
    colecoes = consultar("MATCH (c:Colecao) RETURN c.nome AS nome ORDER BY nome")
    f_lojas = st.multiselect("Local", lojas["nome"].tolist() if not lojas.empty else [])
    f_colecoes = st.multiselect("Coleção", colecoes["nome"].tolist() if not colecoes.empty else [])
    f_categorias = st.multiselect("Diagnóstico", CATEGORIAS, default=["LentoOuObsoleto", "Excesso"])

aba_visao, aba_sku, aba_regras = st.tabs(["Visão geral", "Detalhe do SKU", "Regras e critérios"])

base = consultar("""
    MATCH (p:Produto)-[:POSSUI_OBSERVACAO]->(o:ObservacaoEstoque)-[:LOCALIZADA_EM]->(l:LocalEstoque)
    MATCH (p)-[:PERTENCE_A_COLECAO]->(c:Colecao)
    MATCH (o)-[:RECEBE_DIAGNOSTICO]->(d:Diagnostico)-[:CLASSIFICADO_COMO]->(cat:CategoriaDiagnostico)
    OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(ic:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'CustoOportunidade'})
    OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(ii:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'IdadeEstoque'})
    OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(iv:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'VendasPeriodo'})
    OPTIONAL MATCH (o)-[:POSSUI_INDICADOR]->(ib:Indicador)-[:DO_TIPO]->(:TipoIndicador {nome: 'CoberturaDias'})
    OPTIONAL MATCH (d)-[:RECOMENDA]->(:Recomendacao)-[:SUGERE_ACAO]->(a:AcaoDestinacao)
    RETURN p.sku AS SKU, p.descricao AS Produto, c.nome AS `Coleção`, l.nome AS Local,
           cat.nome AS `Diagnóstico`, o.quantidadeDisponivel AS Quantidade,
           ii.valor AS `Idade (dias)`, iv.valor AS `Vendas 90d`, ib.valor AS `Cobertura (dias)`,
           ic.valor AS `Custo de oportunidade (R$)`,
           collect(DISTINCT a.descricao) AS `Ações recomendadas`""")

filtro = base.copy()
if f_lojas:
    filtro = filtro[filtro["Local"].isin(f_lojas)]
if f_colecoes:
    filtro = filtro[filtro["Coleção"].isin(f_colecoes)]
if f_categorias:
    filtro = filtro[filtro["Diagnóstico"].isin(f_categorias)]

with aba_visao:
    c1, c2, c3 = st.columns(3)
    c1.metric("Estoques no filtro", f"{len(filtro):,}".replace(",", "."))
    c2.metric("Unidades", f"{int(filtro['Quantidade'].sum()):,}".replace(",", "."))
    c3.metric("Custo de oportunidade (R$)",
              f"{filtro['Custo de oportunidade (R$)'].sum():,.0f}".replace(",", "."))
    st.subheader("Custo de oportunidade por diagnóstico")
    resumo = (base.groupby("Diagnóstico")["Custo de oportunidade (R$)"].sum()
              .reindex(CATEGORIAS).fillna(0))
    st.bar_chart(resumo, horizontal=True)
    st.subheader("Estoques ordenados por custo de oportunidade")
    st.dataframe(filtro.sort_values("Custo de oportunidade (R$)", ascending=False, na_position="last"),
                 hide_index=True, use_container_width=True)
    sem_custo = filtro["Custo de oportunidade (R$)"].isna().sum()
    if sem_custo:
        st.info(f"{sem_custo} estoque(s) sem custo unitário ou sem idade: ficaram sem custo de oportunidade.")

with aba_sku:
    sku = st.text_input("SKU", value="CTRL-OBSOLETO")
    detalhe = consultar("""
        MATCH (p:Produto {sku: $sku})-[:POSSUI_OBSERVACAO]->(o)-[:LOCALIZADA_EM]->(l)
        MATCH (o)-[:RECEBE_DIAGNOSTICO]->(d)-[:CLASSIFICADO_COMO]->(cat)
        MATCH (d)-[:GERADO_POR_REGRA]->(r)
        RETURN l.nome AS local, cat.descricao AS diagnostico, r.id + ' v' + r.versao AS regra,
               [(d)-[:FUNDAMENTADO_EM]->(e)-[:ATENDE_CRITERIO]->(cr) | cr.id + ': ' + e.justificativa] AS evidencias,
               [(d)-[:RECOMENDA]->(rec)-[:SUGERE_ACAO]->(a) |
                  a.descricao + ' (' + [(rec)-[:GERADO_POR_REGRA]->(rr) | rr.id][0] + '): ' + rec.justificativa] AS recomendacoes
        ORDER BY local""", sku=sku)
    if detalhe.empty:
        st.warning("SKU não encontrado.")
    for _, linha in detalhe.iterrows():
        with st.container(border=True):
            st.markdown(f"**{linha['local']}**: {linha['diagnostico']} · regra {linha['regra']}")
            for e in linha["evidencias"]:
                st.markdown(f"- Evidência {e}")
            for r in linha["recomendacoes"]:
                st.markdown(f"- Recomendação: {r}")

with aba_regras:
    st.subheader("Regras de negócio")
    st.dataframe(consultar("""
        MATCH (r:RegraNegocio)-[:PERSPECTIVA_DE]->(a:AreaNegocio)
        RETURN r.id AS Regra, r.versao AS `Versão`, a.descricao AS `Área`, r.arquivo AS Arquivo,
               r.descricao AS `Descrição` ORDER BY Regra"""), hide_index=True, use_container_width=True)
    st.subheader("Critérios de diagnóstico")
    st.dataframe(consultar("""
        MATCH (c:CriterioDiagnostico)
        RETURN c.id AS `Critério`, c.descricao AS `Descrição`, c.operador AS Operador,
               c.limite AS Limite, c.versao AS `Versão` ORDER BY `Critério`"""),
                 hide_index=True, use_container_width=True)
