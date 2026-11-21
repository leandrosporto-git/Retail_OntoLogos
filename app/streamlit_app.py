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
JANELAS = {"Últimos 180 dias": 180, "Últimos 12 meses": 365}  # janela da demanda no gráfico
CORES = {"Sem defeito": "#1F5F7A", "Com defeito": "#E8743B"}

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
    f_condicao = st.radio("Condição do produto", ["Todos", "Sem defeito", "Com defeito"], horizontal=True,
                          help="Com defeito: o produto-cor tem peças numa filial de defeito.")
    f_janela = st.selectbox("Demanda (eixo vertical do gráfico)", list(JANELAS), index=1,
                            help="Peças vendidas (vendas válidas nas filiais do escopo) na janela escolhida. Com 180 dias, todo produto sem giro fica em zero, porque é essa a regra; 12 meses mostra quanto ele vendia antes de parar.")

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
           reduce(s = 0, q IN [(r)-[:CONSOLIDA]->(p)-[:TEM_CONDICAO]->(:CondicaoComercial {nome: 'ComDefeito'})
                               | p.quantidade] | s + q) AS pecasComDefeito""",
                 tipos=PARAM["venda_valida"]["tipos"], dias=JANELAS[f_janela])
if base.empty:
    st.warning("O grafo está vazio. Use o botão na barra lateral para carregar os dados de exemplo.")
    st.stop()
base["Situação"] = base.pop("situacao").map(ROTULOS)
col_dem = f"Peças vendidas ({f_janela.lower()})"
base[col_dem] = base.pop("demanda")
base["Condição"] = base.pop("pecasComDefeito").gt(0).map({True: "Com defeito", False: "Sem defeito"})

filtro = base.copy()
if f_marcas:
    filtro = filtro[filtro["Marca"].isin(f_marcas)]
if f_condicao != "Todos":
    filtro = filtro[filtro["Condição"] == f_condicao]

if "cluster" not in st.session_state:
    st.session_state.cluster = None


def escolher(situacao):
    st.session_state.cluster = None if st.session_state.cluster == situacao else situacao


with aba_visao:
    st.caption("Clique num card para ver só os produtos-cor daquela situação no gráfico e na tabela; clique de novo "
               "para voltar a todos.")
    cards = st.columns(len(SITUACOES))
    for coluna, nome in zip(cards, SITUACOES):
        rotulo = ROTULOS[nome]
        grupo = filtro[filtro["Situação"] == rotulo]
        selecionado = st.session_state.cluster == rotulo
        with coluna.container(border=True):
            st.markdown(f"**{rotulo}**")
            st.metric("Custo de oportunidade", f"R$ {grupo['Custo de oportunidade (R$)'].sum():,.0f}".replace(",", "."))
            st.caption(f"{len(grupo)} produtos-cor · {int(grupo['Saldo'].sum()):,} peças".replace(",", "."))
            st.button("Mostrando" if selecionado else "Ver no gráfico", key=f"card_{nome}", on_click=escolher,
                      args=(rotulo,), type="primary" if selecionado else "secondary", use_container_width=True)
    visao = filtro if st.session_state.cluster is None else filtro[filtro["Situação"] == st.session_state.cluster]

    st.subheader("Demanda × idade do estoque" + (f": {st.session_state.cluster}" if st.session_state.cluster else ""))
    pontos = visao.dropna(subset=["Idade (meses)"])
    sem_data = len(visao) - len(pontos)
    limite_x = max(6, int(pontos["Idade (meses)"].max() // 6 + 1) * 6) if not pontos.empty else 6
    eixo_x = alt.X("Idade (meses):Q", title="Idade do estoque (meses desde o lançamento)",
                   scale=alt.Scale(domain=[0, limite_x]),
                   axis=alt.Axis(values=list(range(0, limite_x + 1, 6)), grid=True))
    dispersao = alt.Chart(pontos).mark_circle(size=90, opacity=0.8, stroke="white", strokeWidth=0.5).encode(
        x=eixo_x,
        y=alt.Y(field=col_dem, type="quantitative", title=f"Demanda: {col_dem.lower()}",
              scale=alt.Scale(domainMin=0, domainMax=max(10, int(pontos[col_dem].max()) if not pontos.empty else 10)),
              axis=alt.Axis(format=",.0f")),
        color=alt.Color("Condição:N", scale=alt.Scale(domain=list(CORES), range=list(CORES.values())),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=["Produto-cor", "Produto", "Marca", "Situação", "Condição", "Idade (meses)", col_dem, "Saldo",
                 alt.Tooltip("Custo de oportunidade (R$):Q", format=",.0f")])
    limite = PARAM["limites"]["idade_meses"]
    regra = alt.Chart(pd.DataFrame({"x": [limite]})).mark_rule(strokeDash=[6, 4], color="#888").encode(x="x:Q")
    texto = alt.Chart(pd.DataFrame({"x": [limite], "t": [f"{limite} meses"]})).mark_text(
        align="left", dx=4, dy=-6, color="#666", baseline="top").encode(x="x:Q", y=alt.value(0), text="t:N")
    st.altair_chart(alt.layer(regra, texto, dispersao).properties(height=420), use_container_width=True)
    nota = f"Cada ponto é um produto-cor. A linha tracejada marca o limite de idade da regra ({limite} meses)."
    if sem_data:
        nota += f" {sem_data} produto(s)-cor sem data de lançamento não aparecem no gráfico (diagnóstico pendente)."
    st.caption(nota)

    st.subheader("Produtos-cor ordenados por custo de oportunidade")
    st.dataframe(visao.sort_values("Custo de oportunidade (R$)", ascending=False, na_position="last"),
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
