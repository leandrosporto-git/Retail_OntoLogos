"""Leitura da ontologia OWL e verificação de consistência lógica.

A ontologia é a fonte de verdade do vocabulário. O grafo no Neo4j só pode usar
classes e propriedades declaradas aqui (ver tests/test_ontologia.py).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from rdflib import Graph, OWL, RDF

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_ONTOLOGIA = RAIZ / "ontologia" / "retail_ontologos.ttl"
NS = "https://example.org/retail-ontologos#"


def carregar_grafo(caminho: Path = ARQUIVO_ONTOLOGIA) -> Graph:
    g = Graph()
    g.parse(caminho, format="turtle")
    return g


def _nomes_locais(g: Graph, tipo) -> set[str]:
    return {str(s).removeprefix(NS) for s in g.subjects(RDF.type, tipo) if str(s).startswith(NS)}


def vocabulario(caminho: Path = ARQUIVO_ONTOLOGIA) -> dict[str, set[str]]:
    """Classes, propriedades de objeto e de dados declaradas na ontologia."""
    g = carregar_grafo(caminho)
    return {
        "classes": _nomes_locais(g, OWL.Class),
        "propriedades_objeto": _nomes_locais(g, OWL.ObjectProperty),
        "propriedades_dados": _nomes_locais(g, OWL.DatatypeProperty),
    }


def verificar_consistencia(caminho: Path = ARQUIVO_ONTOLOGIA) -> list[str]:
    """Roda o reasoner HermiT (via Owlready2, requer Java) e devolve as classes
    insatisfatíveis. Lança owlready2.OwlReadyInconsistentOntologyError se a
    ontologia for inconsistente."""
    import owlready2

    g = carregar_grafo(caminho)
    with tempfile.TemporaryDirectory() as tmp:
        arquivo_xml = Path(tmp) / "ontologia.owl"
        g.serialize(arquivo_xml, format="xml")
        mundo = owlready2.World()
        onto = mundo.get_ontology(arquivo_xml.as_uri()).load()
        with onto:
            owlready2.sync_reasoner_hermit(mundo, infer_property_values=False, debug=0)
        return [str(c) for c in mundo.inconsistent_classes()]


if __name__ == "__main__":
    voc = vocabulario()
    print({k: len(v) for k, v in voc.items()})
    problemas = verificar_consistencia()
    print("Ontologia consistente." if not problemas else f"Classes insatisfatíveis: {problemas}")
