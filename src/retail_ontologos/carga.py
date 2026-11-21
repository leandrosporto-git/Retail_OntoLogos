"""Carga do grafo no Neo4j.

Mapeamento OWL -> grafo de propriedades (documentado em docs/mapeamento_owl_neo4j.md):
- classe OWL            -> rótulo de nó (ex.: :PosicaoEstoque)
- propriedade de objeto -> tipo de relacionamento em MAIÚSCULAS (refereSeA -> REFERE_SE_A)
- propriedade de dados  -> atributo do nó com o mesmo nome (dataLancamento)
- indivíduo enumerado   -> nó com o atributo nome (ex.: (:SituacaoGiroIdade {nome: 'Ativo'}))

Antes de carregar estoque e vendas, todo nome de filial (atual ou antigo) é
traduzido para o código estável da filial. Sem isso, uma venda registrada com um
nome antigo sumiria, e o produto poderia aparecer como sem giro.

Uso:
    python -m retail_ontologos.carga --dados dados/exemplo
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import yaml
from rdflib import RDF, RDFS, URIRef

from .conexao import conectar, RAIZ
from .ontologia import carregar_grafo, NS

# Listas de valores: classe enumerada -> rótulos extras do nó (superclasses).
ENUMERACOES = {
    "SituacaoGiroIdade": [], "CondicaoComercial": [], "FaseColecao": [], "Canal": [], "TipoFilial": [],
    "TipoMotivo": [], "AcaoDestinacao": [],
    "TipoColecao": ["ValorClassificacao"], "TipoRestricao": ["ValorClassificacao"],
}
CANAL = {"Fisico": "CanalFisico", "Digital": "CanalDigital", "Atacado": "CanalAtacado"}
TIPO_FILIAL = {"Venda": "FilialVenda", "Estoque": "FilialEstoque", "Defeito": "FilialDefeito"}


def nome_relacionamento(propriedade: str) -> str:
    """refereSeA -> REFERE_SE_A"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", propriedade).upper()


def ler_parametros() -> dict:
    with open(RAIZ / "regras" / "parametros.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ler_csv(pasta: Path, nome: str) -> list[dict]:
    arquivo = pasta / f"{nome}.csv"
    if not arquivo.exists():
        return []
    with open(arquivo, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _vazio_para_none(linhas: list[dict]) -> list[dict]:
    return [{k: (None if v == "" else v) for k, v in linha.items()} for linha in linhas]


def limpar(sessao) -> None:
    sessao.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS")


def criar_restricoes(sessao) -> None:
    for rotulo, chave in [("Marca", "codigo"), ("Colecao", "codigo"), ("Filial", "codigo"), ("Produto", "codigo"),
                          ("ProdutoCor", "codigo"), ("SKU", "codigo"), ("PosicaoEstoque", "id"),
                          ("PosicaoRede", "id"), ("Diagnostico", "id")]:
        sessao.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{rotulo}) REQUIRE n.{chave} IS UNIQUE")


def _iri(nome: str) -> URIRef:
    return URIRef(NS + nome)


def carregar_vocabulario(sessao) -> None:
    """Cria os indivíduos das listas de valores declarados na ontologia."""
    g = carregar_grafo()
    for classe, extras in ENUMERACOES.items():
        rotulos = ":".join([classe, *extras])
        for ind in g.subjects(RDF.type, _iri(classe)):
            nome = str(ind).removeprefix(NS)
            sessao.run(f"MERGE (n:{rotulos} {{nome: $nome}}) SET n.descricao = $rotulo",
                       nome=nome, rotulo=str(g.value(ind, RDFS.label) or nome))


def mapa_filiais(filiais: list[dict]) -> dict[str, str]:
    """Nome registrado (atual ou antigo) -> código estável da filial."""
    mapa = {}
    for f in filiais:
        for nome in [f["nome"], *filter(None, (f["nomes_anteriores"] or "").split("|"))]:
            if nome in mapa and mapa[nome] != f["codigo"]:
                raise ValueError(f"Nome de filial ambíguo: {nome}")
            mapa[nome] = f["codigo"]
    return mapa


def carregar_dados(sessao, pasta: Path) -> dict[str, int]:
    marcas = _vazio_para_none(_ler_csv(pasta, "marcas"))
    sessao.run("""
        UNWIND $linhas AS l
        CREATE (:Marca {codigo: l.codigo, nome: l.nome,
                        descontinuadaDesde: CASE WHEN l.descontinuada_desde IS NULL THEN null
                                                 ELSE date(l.descontinuada_desde) END})""", linhas=marcas)
    colecoes = _vazio_para_none(_ler_csv(pasta, "colecoes"))
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (m:Marca {codigo: l.marca})
        CREATE (c:Colecao {codigo: l.codigo, nome: l.nome, temporada: l.temporada, ano: toInteger(l.ano),
                           inicioColecao: date(l.inicio_colecao), inicioSale: date(l.inicio_sale),
                           inicioOff1: date(l.inicio_off1), inicioOff2: date(l.inicio_off2),
                           inicioOff3: date(l.inicio_off3)})
        CREATE (c)-[:COLECAO_DA_MARCA]->(m)""", linhas=colecoes)

    filiais = _vazio_para_none(_ler_csv(pasta, "filiais"))
    for f in filiais:
        f["canal_nome"], f["tipo_nome"] = CANAL[f["canal"]], TIPO_FILIAL[f["tipo"]]
        f["anteriores"] = (f["nomes_anteriores"] or "").split("|") if f["nomes_anteriores"] else []
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (m:Marca {codigo: l.fachada}), (c:Canal {nome: l.canal_nome}), (t:TipoFilial {nome: l.tipo_nome})
        CREATE (f:Filial {codigo: l.codigo, nome: l.nome, nomesAnteriores: l.anteriores, cidade: l.cidade,
                          estado: l.estado, regiao: l.regiao, dataAbertura: date(l.data_abertura),
                          dataFechamento: CASE WHEN l.data_fechamento IS NULL THEN null ELSE date(l.data_fechamento) END})
        CREATE (f)-[:OPERA_SOB_FACHADA]->(m)
        CREATE (f)-[:TEM_CANAL]->(c)
        CREATE (f)-[:DO_TIPO_FILIAL]->(t)""", linhas=filiais)

    produtos = _ler_csv(pasta, "produtos")
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (m:Marca {codigo: l.marca})
        CREATE (p:Produto {codigo: l.produto, descricao: l.descricao, negocio: l.negocio, linha: l.linha,
                           grupo: l.grupo, subgrupo: l.subgrupo})
        CREATE (p)-[:PERTENCE_A_MARCA]->(m)""", linhas=produtos)
    produtos_cor = _vazio_para_none(_ler_csv(pasta, "produtos_cor"))
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (p:Produto {codigo: l.produto})
        CREATE (pc:ProdutoCor {codigo: l.produto_cor, cor: l.cor,
                               dataLancamento: CASE WHEN l.data_lancamento IS NULL THEN null ELSE date(l.data_lancamento) END,
                               origemDataLancamento: l.origem_data, canceladoPeloEstilo: l.cancelado = 'True',
                               custoUnitario: toFloat(l.custo_unitario)})
        CREATE (pc)-[:VARIACAO_DE]->(p)
        WITH pc, l
        OPTIONAL MATCH (co:Colecao {codigo: l.colecao_original})
        OPTIONAL MATCH (ca:Colecao {codigo: l.colecao_atual})
        FOREACH (_ IN CASE WHEN co IS NULL THEN [] ELSE [1] END | CREATE (pc)-[:TEM_COLECAO_ORIGINAL]->(co))
        FOREACH (_ IN CASE WHEN ca IS NULL THEN [] ELSE [1] END | CREATE (pc)-[:TEM_COLECAO_ATUAL]->(ca))""",
                linhas=produtos_cor)
    skus = _ler_csv(pasta, "skus")
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (pc:ProdutoCor {codigo: l.produto_cor})
        CREATE (s:SKU {codigo: l.sku, tamanho: l.tamanho, grade: l.grade})
        CREATE (s)-[:TAMANHO_DE]->(pc)""", linhas=skus)
    classificacoes = _vazio_para_none(_ler_csv(pasta, "classificacoes"))
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (pc:ProdutoCor {codigo: l.produto_cor}), (v:ValorClassificacao {nome: l.valor})
        CREATE (pc)-[:TEM_CLASSIFICACAO]->(c:ClassificacaoVigencia {
                   validoDe: date(l.valido_de),
                   validoAte: CASE WHEN l.valido_ate IS NULL THEN null ELSE date(l.valido_ate) END})
        CREATE (c)-[:TEM_VALOR]->(v)
        WITH c, l WHERE l.filial IS NOT NULL
        MATCH (f:Filial {codigo: l.filial})
        CREATE (c)-[:RESTRINGE_DESTINO]->(f)""", linhas=classificacoes)

    mapa = mapa_filiais(filiais)
    sem_filial = 0
    estoque = []
    for e in _ler_csv(pasta, "estoque"):
        codigo = mapa.get(e["filial"])
        if codigo is None:
            sem_filial += 1
            continue
        estoque.append({**e, "codigo_filial": codigo, "id": f"{e['produto_cor']}@{codigo}@{e['data']}"})
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (pc:ProdutoCor {codigo: l.produto_cor}), (f:Filial {codigo: l.codigo_filial})
        MERGE (p:PosicaoEstoque {id: l.id})
          ON CREATE SET p.dataReferencia = date(l.data), p.quantidade = 0
        SET p.quantidade = p.quantidade + toInteger(l.quantidade)
        MERGE (p)-[:REFERE_SE_A]->(pc)
        MERGE (p)-[:ESTA_EM]->(f)""", linhas=estoque)
    vendas = []
    for v in _ler_csv(pasta, "vendas"):
        codigo = mapa.get(v["filial"])
        if codigo is None:
            sem_filial += 1
            continue
        vendas.append({**v, "codigo_filial": codigo})
    sessao.run("""
        UNWIND $linhas AS l
        CALL (l) {
          MATCH (pc:ProdutoCor {codigo: l.produto_cor}), (f:Filial {codigo: l.codigo_filial})
          CREATE (v:Venda {dataVenda: date(l.data), quantidade: toInteger(l.quantidade), tipoMovimento: l.tipo})
          CREATE (v)-[:REFERE_SE_A]->(pc)
          CREATE (v)-[:OCORREU_EM]->(f)
        } IN TRANSACTIONS OF 5000 ROWS""", linhas=vendas)
    return {"marcas": len(marcas), "colecoes": len(colecoes), "filiais": len(filiais), "produtos": len(produtos),
            "produtos_cor": len(produtos_cor), "skus": len(skus), "classificacoes": len(classificacoes),
            "posicoes_estoque": len(estoque), "vendas": len(vendas), "linhas_sem_filial": sem_filial}


def carregar_tudo(pasta: Path) -> dict[str, int]:
    with conectar() as driver:
        with driver.session() as sessao:
            limpar(sessao)
            criar_restricoes(sessao)
            carregar_vocabulario(sessao)
        with driver.session() as sessao:
            return carregar_dados(sessao, pasta)


def main() -> None:
    p = argparse.ArgumentParser(description="Carrega o grafo no Neo4j (apaga o conteúdo anterior).")
    p.add_argument("--dados", type=Path, default=RAIZ / "dados" / "exemplo")
    a = p.parse_args()
    print(carregar_tudo(a.dados))


if __name__ == "__main__":
    main()
