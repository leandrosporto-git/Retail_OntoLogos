"""Motor de regras: executa os arquivos .cypher da pasta regras/, em ordem.

Cada consulta começa com um cabeçalho que identifica a regra:
    // regra: R01 | versao: 0.1.0 | area: Planejamento
    // descricao: ...
O motor cria um nó :RegraNegocio para cada regra, ligado à área de negócio, de modo
que todo diagnóstico e toda recomendação apontem a regra (e a versão) que os gerou.

Uso:
    python -m fashionstockkg.motor
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .carga import ler_parametros
from .conexao import conectar, RAIZ

PASTA_REGRAS = RAIZ / "regras"
CABECALHO = re.compile(r"//\s*regra:\s*(\w+)\s*\|\s*versao:\s*([\w.]+)\s*\|\s*area:\s*(\w+)\s*\n//\s*descricao:\s*(.+)")


@dataclass
class Consulta:
    regra: str
    versao: str
    area: str
    descricao: str
    arquivo: str
    cypher: str


def ler_consultas(pasta: Path = PASTA_REGRAS) -> list[Consulta]:
    consultas = []
    for arquivo in sorted(pasta.glob("*.cypher")):
        for bloco in arquivo.read_text(encoding="utf-8").split(";\n"):
            bloco = bloco.strip()
            if not bloco:
                continue
            m = CABECALHO.search(bloco)
            if not m:
                raise ValueError(f"Consulta sem cabeçalho de regra em {arquivo.name}:\n{bloco[:200]}")
            consultas.append(Consulta(*m.groups(), arquivo=arquivo.name, cypher=bloco.rstrip(";")))
    return consultas


def limpar_resultados(sessao) -> None:
    """Apaga resultados de execuções anteriores, mantendo os dados de entrada."""
    sessao.run("MATCH (n) WHERE n:Diagnostico OR n:Evidencia OR n:Recomendacao OR n:RegraNegocio DETACH DELETE n")
    sessao.run("""MATCH (i:Indicador)-[:DO_TIPO]->(t:TipoIndicador)
                  WHERE t.nome IN ['CoberturaDias', 'SellThrough', 'CustoOportunidade']
                  DETACH DELETE i""")


def executar(data_avaliacao: date | None = None, verbose: bool = True) -> list[dict]:
    parametros = ler_parametros()
    args = {
        **parametros["limites"],
        **parametros["financeiro"],
        "data_avaliacao": (data_avaliacao or date(2026, 10, 31)).isoformat(),
    }
    consultas = ler_consultas()
    resultados = []
    with conectar() as driver, driver.session() as sessao:
        limpar_resultados(sessao)
        for c in {c.regra: c for c in consultas}.values():
            sessao.run("""
                MERGE (r:RegraNegocio {id: $id})
                SET r.versao = $versao, r.descricao = $descricao, r.arquivo = $arquivo
                WITH r MATCH (a:AreaNegocio {nome: $area})
                MERGE (r)-[:PERSPECTIVA_DE]->(a)""",
                       id=c.regra, versao=c.versao, descricao=c.descricao, arquivo=c.arquivo, area=c.area)
        for c in consultas:
            linhas = sessao.run(c.cypher, **args).data()
            resultados.append({"regra": c.regra, "arquivo": c.arquivo, "resultado": linhas})
            if verbose:
                print(f"{c.regra} ({c.arquivo}): {linhas}")
    return resultados


if __name__ == "__main__":
    executar()
