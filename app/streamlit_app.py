"""Interface do Retail OntoLogos.

Execute com:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retail_ontologos import carga, motor  # noqa: E402
from retail_ontologos.conexao import conectar  # noqa: E402

st.set_page_config(page_title="Retail OntoLogos", layout="wide")

PARAM = carga.ler_parametros()
DIAS_DEMANDA = PARAM["limites"]["dias_sem_venda"]  # janela da demanda = janela da regra de giro
FAIXAS = ["0 a 12 meses", "12 a 24 meses", "24 a 36 meses", "36 a 48 meses", "48 a 60 meses", "Mais de 60 meses"]


def faixa_idade(meses) -> str:
    if pd.isna(meses):
        return "Sem data"
    return FAIXAS[min(int(meses) // 12, len(FAIXAS) - 1)]

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
           [(r)-[:TEM_MOTIVO]->(:Motivo)-[:DO_TIPO_MOTIVO]->(t) | t.descricao] AS Motivos,
           reduce(s = 0, q IN [(r)-[:AVALIADA_NO_ESCOPO]->(:EscopoRede)-[:INCLUI_FILIAL]->(:Filial)<-[:OCORREU_EM]-(v:Venda)-[:REFERE_SE_A]->(pc)
                               WHERE v.tipoMovimento IN $tipos AND v.dataVenda <= r.dataReferencia
                                 AND v.dataVenda > r.dataReferencia - duration({days: $dias}) | v.quantidade] | s + q) AS demanda,
           coalesce(pc.custoUnitario, 0) * reduce(s = 0, q IN [(r)-[:CONSOLIDA]->(p)-[:TEM_CONDICAO]->(:CondicaoComercial {nome: 'ComDefeito'})
                               | p.quantidade] | s + q) AS valorComDefeito""",
                 tipos=PARAM["venda_valida"]["tipos"], dias=DIAS_DEMANDA)
if base.empty:
    st.warning("O grafo está vazio. Use o botão na barra lateral para carregar os dados de exemplo.")
    st.stop()
base["Situação"] = base.pop("situacao").map(ROTULOS)
base["Faixa de idade"] = base["Idade (meses)"].map(faixa_idade)
base["Valor sem defeito (R$)"] = base["Valor a custo (R$)"].fillna(0) - base["valorComDefeito"]
base["Valor com defeito (R$)"] = base.pop("valorComDefeito")
base[f"Demanda {DIAS_DEMANDA} dias (peças)"] = base.pop("demanda")

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
    st.subheader("Demanda e valor do estoque por idade")
    st.caption(f"Peças vendidas nos últimos {DIAS_DEMANDA} dias (linha, eixo da esquerda) e valor do estoque a custo, "
               "com e sem defeito (barras, eixo da direita), por faixa de idade desde o lançamento. Mostra todas as "
               "situações, para comparar a carteira inteira; respeita só o filtro de marca.")
    ordem = FAIXAS + ["Sem data"]
    col_dem = f"Demanda {DIAS_DEMANDA} dias (peças)"
    carteira = base[base["Marca"].isin(f_marcas)] if f_marcas else base
    por_faixa = (carteira.groupby("Faixa de idade")[[col_dem, "Valor sem defeito (R$)", "Valor com defeito (R$)"]].sum()
                 .reindex(ordem).fillna(0).reset_index())
    tem_dado = (por_faixa[col_dem] > 0) | (por_faixa["Valor sem defeito (R$)"] + por_faixa["Valor com defeito (R$)"] > 0)
    por_faixa = por_faixa[tem_dado | por_faixa["Faixa de idade"].isin(FAIXAS)]
    valores = por_faixa.melt("Faixa de idade", ["Valor sem defeito (R$)", "Valor com defeito (R$)"],
                             var_name="Condição", value_name="Valor (R$)")
    valores["Condição"] = valores["Condição"].map({"Valor sem defeito (R$)": "Sem defeito",
                                                   "Valor com defeito (R$)": "Com defeito"})
    eixo_x = alt.X("Faixa de idade:N", sort=list(por_faixa["Faixa de idade"]), title="Idade do estoque",
                   axis=alt.Axis(labelAngle=0))
    barras = alt.Chart(valores).mark_bar(opacity=0.85).encode(
        x=eixo_x,
        y=alt.Y("Valor (R$):Q", title="Valor do estoque a custo (R$)", axis=alt.Axis(orient="right", format=",.0f")),
        color=alt.Color("Condição:N", scale=alt.Scale(domain=["Sem defeito", "Com defeito"], range=["#4C78A8", "#E45756"]),
                        legend=alt.Legend(title="Valor a custo", orient="top")),
        order=alt.Order("Condição:N", sort="descending"),
        tooltip=["Faixa de idade", "Condição", alt.Tooltip("Valor (R$):Q", format=",.0f")])
    linha = alt.Chart(por_faixa).mark_line(point=alt.OverlayMarkDef(size=70), color="#1B1B1B", strokeWidth=2.5).encode(
        x=eixo_x,
        y=alt.Y(f"{col_dem}:Q", title=f"Demanda: peças vendidas em {DIAS_DEMANDA} dias", axis=alt.Axis(orient="left", format=",.0f")),
        tooltip=["Faixa de idade", alt.Tooltip(f"{col_dem}:Q", format=",.0f")])
    st.altair_chart(alt.layer(barras, linha).resolve_scale(y="independent").properties(height=380),
                    use_container_width=True)
    st.subheader("Custo de oportunidade por situação")
    resumo = (base.groupby("Situação")["Custo de oportunidade (R$)"].sum()
              .reindex([ROTULOS[s] for s in SITUACOES]).fillna(0))
    st.bar_chart(resumo, horizontal=True)
    st.subheader("Produtos-cor ordenados por custo de oportunidade")
    st.dataframe(filtro.drop(columns=["Faixa de idade"]).sort_values("Custo de oportunidade (R$)", ascending=False, na_position="last"),
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
