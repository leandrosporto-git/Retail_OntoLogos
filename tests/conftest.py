import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from retail_ontologos import carga, motor  # noqa: E402
from retail_ontologos.conexao import conectar  # noqa: E402
from retail_ontologos.gerar_dados import gerar, salvar  # noqa: E402


@pytest.fixture(scope="session")
def driver(tmp_path_factory):
    """Carrega o dataset de exemplo (semente 42) e roda as regras uma vez por sessão."""
    try:
        d = conectar()
    except Exception as erro:  # Neo4j fora do ar
        pytest.skip(f"Neo4j indisponível: {erro}")
    pasta = tmp_path_factory.mktemp("dados")
    salvar(gerar(300, 42), pasta)
    carga.carregar_tudo(pasta)
    motor.executar(verbose=False)
    yield d
    d.close()


@pytest.fixture
def consultar(driver):
    def _consultar(cypher, **params):
        with driver.session() as s:
            return s.run(cypher, **params).data()
    return _consultar
