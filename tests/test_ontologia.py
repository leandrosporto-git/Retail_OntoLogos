"""A ontologia é consistente e o grafo só usa o vocabulário declarado nela."""
import shutil

import pytest

from retail_ontologos.carga import nome_relacionamento
from retail_ontologos.ontologia import verificar_consistencia, vocabulario

ATRIBUTOS_TECNICOS = {"id"}  # identificadores internos do grafo
# Os testes olham o que está em uso no grafo, não o catálogo do banco (db.propertyKeys guarda
# chaves antigas mesmo depois que os nós são apagados).


@pytest.mark.skipif(shutil.which("java") is None, reason="o reasoner HermiT precisa de Java")
def test_ontologia_e_consistente():
    assert verificar_consistencia() == []


def test_rotulos_do_grafo_sao_classes_da_ontologia(consultar):
    classes = vocabulario()["classes"]
    rotulos = {r["rotulo"] for r in consultar("MATCH (n) UNWIND labels(n) AS rotulo RETURN DISTINCT rotulo")}
    assert rotulos - classes == set()


def test_relacionamentos_do_grafo_sao_propriedades_de_objeto(consultar):
    esperados = {nome_relacionamento(p) for p in vocabulario()["propriedades_objeto"]}
    tipos = {r["tipo"] for r in consultar(
        "MATCH ()-[r]->() RETURN DISTINCT type(r) AS tipo")}
    assert tipos - esperados == set()


def test_atributos_do_grafo_sao_propriedades_de_dados(consultar):
    permitidos = vocabulario()["propriedades_dados"] | ATRIBUTOS_TECNICOS
    chaves = {r["chave"] for r in consultar(
        "MATCH (n) UNWIND keys(n) AS chave RETURN DISTINCT chave UNION MATCH ()-[r]->() UNWIND keys(r) AS chave RETURN DISTINCT chave")}
    assert chaves - permitidos == set()
