from retail_ontologos.gerar_dados import gerar


def test_mesma_semente_gera_os_mesmos_dados():
    assert gerar(50, 7) == gerar(50, 7)


def test_semente_diferente_gera_dados_diferentes():
    assert gerar(50, 7)["observacoes"] != gerar(50, 8)["observacoes"]
