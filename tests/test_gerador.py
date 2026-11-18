from retail_ontologos.gerar_dados import CASOS_CONTROLE, FILIAIS, gerar, meses_antes
from datetime import date


def test_mesma_semente_gera_os_mesmos_dados():
    assert gerar(30, 7) == gerar(30, 7)


def test_semente_diferente_gera_dados_diferentes():
    assert gerar(30, 7)["vendas"] != gerar(30, 8)["vendas"]


def test_meses_de_calendario_nao_assumem_30_dias():
    assert meses_antes(date(2026, 10, 31), 24) == date(2024, 10, 31)
    assert meses_antes(date(2026, 3, 31), 1) == date(2026, 2, 28)


def test_vendas_so_depois_da_abertura_da_filial():
    nomes = {}
    for f in FILIAIS:
        for n in [f[1], *f[2]]:
            nomes[n] = f[9]
    dados = gerar(60, 42)
    controle = {c[0] for c in CASOS_CONTROLE}
    atrasadas = [v for v in dados["vendas"] if v["produto_cor"] not in controle
                 and date.fromisoformat(v["data"]) < nomes[v["filial"]]]
    assert atrasadas == []


def test_dados_nao_citam_empresa_real():
    texto = str(gerar(30, 42)).lower()
    assert "off premium" not in texto and "ouvidor" not in texto
