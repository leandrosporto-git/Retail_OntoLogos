"""Carga do grafo no Neo4j.

Mapeamento OWL -> grafo de propriedades (documentado em docs/mapeamento_owl_neo4j.md):
- classe OWL            -> rótulo de nó (ex.: :ObservacaoEstoque)
- propriedade de objeto -> tipo de relacionamento em MAIÚSCULAS (possuiObservacao -> POSSUI_OBSERVACAO)
- propriedade de dados  -> atributo do nó com o mesmo nome (quantidadeDisponivel)
- indivíduo enumerado   -> nó com o atributo nome (ex.: (:CategoriaDiagnostico {nome: 'Ativo'}))

Uso:
    python -m fashionstockkg.carga --dados dados/exemplo
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

ENUMERACOES = ["TipoIndicador", "CategoriaDiagnostico", "AcaoDestinacao", "AreaNegocio"]
UNIDADES = {"IdadeEstoque": "dias", "VendasPeriodo": "unidades"}


def nome_relacionamento(propriedade: str) -> str:
    """possuiObservacao -> POSSUI_OBSERVACAO"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", propriedade).upper()


def ler_parametros() -> dict:
    with open(RAIZ / "regras" / "parametros.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ler_csv(pasta: Path, nome: str) -> list[dict]:
    with open(pasta / f"{nome}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(valor: str):
    return None if valor in ("", None) else float(valor)


def limpar(sessao) -> None:
    sessao.run("MATCH (n) DETACH DELETE n")


def criar_restricoes(sessao) -> None:
    for rotulo, chave in [("Produto", "sku"), ("Colecao", "codigo"), ("LocalEstoque", "codigo"),
                          ("ObservacaoEstoque", "id"), ("Indicador", "id"), ("Diagnostico", "id")]:
        sessao.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{rotulo}) REQUIRE n.{chave} IS UNIQUE")


def carregar_vocabulario(sessao, parametros: dict) -> None:
    """Cria os indivíduos enumerados da ontologia, os critérios e as causas prováveis."""
    g = carregar_grafo()
    for classe in ENUMERACOES:
        for ind in g.subjects(RDF.type, _iri(classe)):
            nome = str(ind).removeprefix(NS)
            rotulo = str(g.value(ind, RDFS.label) or nome)
            sessao.run(f"MERGE (n:{classe} {{nome: $nome}}) SET n.descricao = $rotulo",
                       nome=nome, rotulo=rotulo)
    limites = parametros["limites"]
    for c in parametros["criterios"]:
        sessao.run(
            "MERGE (c:CriterioDiagnostico {id: $id}) "
            "SET c.descricao = $descricao, c.operador = $operador, c.limite = $limite, c.versao = $versao",
            id=c["id"], descricao=c["descricao"], operador=c["operador"],
            limite=limites.get(c["limite_param"]) if c["limite_param"] else None,
            versao=parametros["versao_regras"])
    for k in parametros["causas_provaveis"]:
        sessao.run("MERGE (k:CausaProvavel {codigo: $codigo}) SET k.nome = $nome", **k)


def _iri(classe: str) -> URIRef:
    return URIRef(NS + classe)


def carregar_dados(sessao, pasta: Path) -> dict[str, int]:
    colecoes = _ler_csv(pasta, "colecoes")
    sessao.run("""
        UNWIND $linhas AS l
        CREATE (:Colecao {codigo: l.codigo, nome: l.nome, temporada: l.temporada,
                          ano: toInteger(l.ano), encerrada: l.encerrada = 'True'})""", linhas=colecoes)
    locais = _ler_csv(pasta, "locais")
    for tipo in ("Loja", "CentroDistribuicao"):
        sessao.run(f"""
            UNWIND $linhas AS l
            CREATE (:LocalEstoque:{tipo} {{codigo: l.codigo, nome: l.nome, regiao: l.regiao}})""",
                   linhas=[l for l in locais if l["tipo"] == tipo])
    produtos = _ler_csv(pasta, "produtos")
    for p in produtos:
        p["custo_unitario"] = _num(p["custo_unitario"])
        p["preco_venda"] = _num(p["preco_venda"])
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (c:Colecao {codigo: l.colecao})
        CREATE (p:Produto {sku: l.sku, descricao: l.descricao, categoriaProduto: l.categoria,
                           custoUnitario: l.custo_unitario, precoVenda: l.preco_venda})
        CREATE (p)-[:PERTENCE_A_COLECAO]->(c)""", linhas=produtos)
    observacoes = _ler_csv(pasta, "observacoes")
    for o in observacoes:
        o["id"] = f"{o['sku']}@{o['local']}@{o['data']}"
        o["idade_dias"] = _num(o["idade_dias"])
        o["vendas_90d"] = _num(o["vendas_90d"])
    sessao.run("""
        UNWIND $linhas AS l
        MATCH (p:Produto {sku: l.sku}), (loc:LocalEstoque {codigo: l.local})
        CREATE (o:ObservacaoEstoque {id: l.id, dataObservacao: datetime(l.data),
                                     quantidadeDisponivel: toInteger(l.quantidade)})
        CREATE (p)-[:POSSUI_OBSERVACAO]->(o)
        CREATE (o)-[:LOCALIZADA_EM]->(loc)""", linhas=observacoes)
    # Indicadores medidos. Valor ausente no CSV = indicador não criado (mundo aberto).
    for tipo, campo in [("IdadeEstoque", "idade_dias"), ("VendasPeriodo", "vendas_90d")]:
        sessao.run("""
            UNWIND $linhas AS l
            WITH l WHERE l[$campo] IS NOT NULL
            MATCH (o:ObservacaoEstoque {id: l.id}), (t:TipoIndicador {nome: $tipo})
            CREATE (o)-[:POSSUI_INDICADOR]->(i:Indicador {id: l.id + '-' + $tipo, valor: toInteger(l[$campo]), unidade: $unidade})
            CREATE (i)-[:DO_TIPO]->(t)""", linhas=observacoes, campo=campo, tipo=tipo, unidade=UNIDADES[tipo])
    return {"colecoes": len(colecoes), "locais": len(locais), "produtos": len(produtos),
            "observacoes": len(observacoes)}


def carregar_tudo(pasta: Path) -> dict[str, int]:
    parametros = ler_parametros()
    with conectar() as driver, driver.session() as sessao:
        limpar(sessao)
        criar_restricoes(sessao)
        carregar_vocabulario(sessao, parametros)
        return carregar_dados(sessao, pasta)


def main() -> None:
    p = argparse.ArgumentParser(description="Carrega o grafo no Neo4j (apaga o conteúdo anterior).")
    p.add_argument("--dados", type=Path, default=RAIZ / "dados" / "exemplo")
    a = p.parse_args()
    print(carregar_tudo(a.dados))


if __name__ == "__main__":
    main()
