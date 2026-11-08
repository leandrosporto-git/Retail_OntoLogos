"""A ontologia é consistente e o grafo só usa o vocabulário declarado nela."""
import shutil

import pytest

from fashionstockkg.carga import nome_relacionamento
from fashionstockkg.ontologia import verificar_consistencia, vocabulario

ATRIBUTOS_TECNICOS = {"id"}  # identificadores internos do grafo


@pytest.mark.skipif(shutil.which("java") is None, reason="o reasoner HermiT precisa de Java")
def test_ontologia_e_consistente():
    assert verificar_consistencia() == []


def test_rotulos_do_grafo_sao_classes_da_ontologia(consultar):
    classes = vocabulario()["classes"]
    rotulos = {r["rotulo"] for r in consultar("CALL db.labels() YIELD label RETURN label AS rotulo")}
    assert rotulos - classes == set()


def test_relacionamentos_do_grafo_sao_propriedades_de_objeto(consultar):
    esperados = {nome_relacionamento(p) for p in vocabulario()["propriedades_objeto"]}
    tipos = {r["tipo"] for r in consultar(
        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS tipo")}
    assert tipos - esperados == set()


def test_atributos_do_grafo_sao_propriedades_de_dados(consultar):
    permitidos = vocabulario()["propriedades_dados"] | ATRIBUTOS_TECNICOS
    chaves = {r["chave"] for r in consultar(
        "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS chave")}
    assert chaves - permitidos == set()
