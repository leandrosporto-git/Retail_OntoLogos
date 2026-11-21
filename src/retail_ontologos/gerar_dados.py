"""Gerador de dados sintéticos no formato de uma rede de outlets de moda.

Tudo é fictício e reprodutível (mesma semente, mesmos dados): marcas, filiais,
produtos, estoques e vendas. Nenhum dado real de empresa entra no repositório.

O gerador produz uma foto de estoque na data de referência e o histórico de
vendas (com cancelamentos e devoluções) desde o início da janela de vendas.
A idade, a última venda e o diagnóstico são calculados pelo motor de regras,
e não entregues prontos no CSV.

Uso:
    python -m retail_ontologos.gerar_dados --produtos 120 --semente 42 --saida dados/exemplo
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA_REFERENCIA = date(2026, 10, 31)
INICIO_HISTORICO_VENDAS = date(2024, 1, 1)
FACHADA_REDE = "OUT"  # marca da fachada das filiais da rede outlet (escopo avaliado)


def meses_antes(d: date, meses: int) -> date:
    """Mesma data, n meses de calendário antes (sem assumir 30 dias por mês)."""
    ano, mes = divmod(d.year * 12 + d.month - 1 - meses, 12)
    dia = min(d.day, [31, 29 if ano % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes])
    return date(ano, mes + 1, dia)


MARCAS = [
    # codigo, nome, descontinuada_desde
    ("OUT", "Rede Outlet", None),
    ("AUR", "Aurora", None),
    ("BRS", "Brisa", None),
    ("COR", "Coral", None),
    ("DUN", "Duna", None),
    ("ESM", "Esmeralda", date(2025, 6, 30)),
]
MARCAS_PRODUTO = ["AUR", "BRS", "COR", "DUN", "ESM"]

FILIAIS = [
    # codigo, nome atual, nomes anteriores, fachada, canal, tipo, cidade, estado, regiao, abertura, fechamento
    ("F01", "OUTLET RIO CM", ["RIO OUTLET", "OUTLET RIO SB"], "OUT", "Fisico", "Venda", "Rio de Janeiro", "RJ", "Sudeste", date(2019, 3, 1), None),
    ("F02", "OUTLET SP CM", ["SP OUTLET"], "OUT", "Fisico", "Venda", "São Paulo", "SP", "Sudeste", date(2018, 8, 15), None),
    ("F03", "OUTLET BH CM", ["BH OUTLET", "OUTLET BH SB"], "OUT", "Fisico", "Venda", "Belo Horizonte", "MG", "Sudeste", date(2020, 5, 10), None),
    ("F04", "OUTLET CURITIBA CM", [], "OUT", "Fisico", "Venda", "Curitiba", "PR", "Sul", date(2021, 2, 1), None),
    ("F05", "OUTLET RECIFE CM", [], "OUT", "Fisico", "Venda", "Recife", "PE", "Nordeste", date(2022, 9, 1), None),
    ("F06", "OUTLET BRASILIA CM", ["BRASILIA OUTLET"], "OUT", "Fisico", "Venda", "Brasília", "DF", "Centro-Oeste", date(2019, 11, 20), None),
    ("F07", "OUTLET FLORIPA CM", [], "OUT", "Fisico", "Venda", "Florianópolis", "SC", "Sul", date(2026, 5, 2), None),  # loja nova
    ("F08", "OUTLET ECOM CM", [], "OUT", "Digital", "Venda", "São Paulo", "SP", "Sudeste", date(2020, 1, 1), None),
    ("F09", "CD OUTLET CM", ["CDS OUTLET LOJAS"], "OUT", "Fisico", "Estoque", "Rio de Janeiro", "RJ", "Sudeste", date(2018, 1, 1), None),
    ("F10", "QUALIDADE OUTLET CM", [], "OUT", "Fisico", "Defeito", "Rio de Janeiro", "RJ", "Sudeste", date(2018, 1, 1), None),
    ("F11", "PONTA DE ESTOQUE CM", [], "OUT", "Fisico", "Defeito", "Rio de Janeiro", "RJ", "Sudeste", date(2018, 1, 1), None),
    ("F12", "OUTLET SALVADOR CM", [], "OUT", "Fisico", "Venda", "Salvador", "BA", "Nordeste", date(2017, 4, 1), date(2025, 12, 31)),  # fechada
    # Filiais fora do escopo da rede outlet: lojas e CD das marcas
    ("M01", "AURORA IPANEMA CM", [], "AUR", "Fisico", "Venda", "Rio de Janeiro", "RJ", "Sudeste", date(2015, 1, 1), None),
    ("M02", "BRISA OSCAR FREIRE CM", [], "BRS", "Fisico", "Venda", "São Paulo", "SP", "Sudeste", date(2016, 6, 1), None),
    ("M03", "CD MARCAS CM", [], "AUR", "Atacado", "Estoque", "Rio de Janeiro", "RJ", "Sudeste", date(2014, 1, 1), None),
]
NOME_ATUAL = {f[0]: f[1] for f in FILIAIS}
LOJAS_REDE = [f[0] for f in FILIAIS if f[3] == FACHADA_REDE and f[5] == "Venda" and f[10] is None]
LOJAS_MARCA = ["M01", "M02", "M03"]
FILIAL_QUALIDADE, FILIAL_PONTA, FILIAL_CD, LOJA_NOVA = "F10", "F11", "F09", "F07"

HIERARQUIA = [
    # negocio, linha, grupo, subgrupo
    ("Feminino", "Jeans", "Bottom", "Calça"),
    ("Feminino", "Jeans", "Bottom", "Saia"),
    ("Feminino", "Malha", "Top", "Blusa"),
    ("Feminino", "Tecido plano", "Top", "Camisa"),
    ("Feminino", "Tecido plano", "Vestido e inteiros", "Vestido"),
    ("Feminino", "Tecido plano", "Vestido e inteiros", "Macacão"),
    ("Feminino", "Alfaiataria", "Overtop", "Blazer"),
    ("Feminino", "Praia", "Praia fitness e lingerie", "Biquíni"),
    ("Masculino", "Malha", "Top", "Camiseta"),
    ("Casa", "Cama", "Casa cama e banho", "Jogo de cama"),
]
CORES = ["Preto", "Off-white", "Azul médio", "Verde oliva", "Terracota", "Estampado"]
GRADE = ("Grade PP-GG", ["PP", "P", "M", "G", "GG"])
TEMPORADAS = [("VER", "Verão", 6), ("INV", "Inverno", 1)]  # mês de início da coleção


def _colecoes() -> list[dict]:
    linhas = []
    for marca in MARCAS_PRODUTO:
        for ano in range(2020, 2028):
            for sigla, nome, mes in TEMPORADAS:
                inicio = date(ano - 1 if sigla == "VER" else ano, mes, 1)
                linhas.append({
                    "codigo": f"{marca}-{sigla}{ano % 100:02d}", "marca": marca,
                    "nome": f"{nome} {ano}", "temporada": nome, "ano": ano,
                    "inicio_colecao": inicio.isoformat(),
                    "inicio_sale": (inicio + timedelta(days=182)).isoformat(),
                    "inicio_off1": meses_antes(inicio, -12).isoformat(),
                    "inicio_off2": meses_antes(inicio, -18).isoformat(),
                    "inicio_off3": meses_antes(inicio, -24).isoformat(),
                })
    return linhas


def _colecao_do_lancamento(marca: str, lancamento: date, colecoes: list[dict]) -> str:
    candidatas = [c for c in colecoes if c["marca"] == marca and c["inicio_colecao"] <= lancamento.isoformat()]
    return max(candidatas, key=lambda c: c["inicio_colecao"])["codigo"]


# Casos de controle: valores escolhidos para cair em cada situação com os parâmetros
# padrão (24 meses, 180 dias, limites estritos). Datas relativas à data de referência.
R = DATA_REFERENCIA
CASOS_CONTROLE = [
    # (produto_cor, marca, idade_meses, [(filial, quantidade)], [(filial, dias_atras, tipo)], situacao_esperada, extras)
    ("CTRL-ATIVO", "AUR", 12, [("F01", 40)], [("F01", 10, "venda")], "Ativo", {}),
    ("CTRL-ANTIGO-GIRO", "AUR", 30, [("F02", 25)], [("F03", 10, "venda")], "AntigoComGiro", {}),
    ("CTRL-OBSOLETO", "BRS", 30, [("F01", 300), ("F09", 150)], [("F01", 200, "venda")], "PotencialmenteObsoleto", {}),
    ("CTRL-ATENCAO", "BRS", 20, [("F02", 80)], [("F02", 200, "venda")], "SemGiroEmAtencao", {}),
    ("CTRL-PENDENTE", "COR", None, [("F03", 50)], [("F03", 30, "venda")], "DiagnosticoPendente", {}),
    ("CTRL-LIMITE", "COR", 24, [("F04", 30)], [("F04", 180, "venda")], "Ativo", {}),
    ("CTRL-LOCAL", "DUN", 12, [("F03", 60), ("F02", 10)], [("F03", 200, "venda"), ("F02", 10, "venda")], "Ativo",
     {"motivo_local": "F03"}),
    ("CTRL-LOJA-NOVA", "DUN", 30, [(LOJA_NOVA, 40), ("F02", 10)], [("F02", 10, "venda")], "AntigoComGiro", {}),
    ("CTRL-DESCONT", "ESM", 12, [("F02", 70)], [("F02", 15, "venda")], "Ativo", {}),
    ("CTRL-NEGATIVO", "AUR", 12, [("F01", -5)], [("F01", 20, "venda")], None, {}),
    ("CTRL-CANCELADAS", "BRS", 30, [("F04", 90)],
     [("F04", 300, "venda"), ("F04", 60, "cancelamento"), ("F04", 20, "devolucao")], "PotencialmenteObsoleto", {}),
    ("CTRL-CONTINUO", "COR", 30, [("F06", 120)], [("F06", 200, "venda")], "PotencialmenteObsoleto", {"continuo": True}),
    ("CTRL-CANCELADO", "DUN", 6, [("F01", 35)], [("F01", 5, "venda")], "Ativo", {"cancelado": True}),
    ("CTRL-BLOQUEIO", "AUR", 20, [(FILIAL_CD, 200)], [("F01", 250, "venda")], "SemGiroEmAtencao", {"bloqueio": "F02"}),
    ("CTRL-DEFEITO", "BRS", 12, [(FILIAL_QUALIDADE, 12), ("F02", 40)], [("F02", 8, "venda")], "Ativo", {}),
    ("CTRL-MUITO-ANTIGO", "DUN", 70, [("F04", 50)], [("F04", 250, "venda")], "PotencialmenteObsoleto", {}),
    ("CTRL-DEFEITO-SEM-GIRO", "COR", 30, [(FILIAL_QUALIDADE, 20)], [("F02", 220, "venda")], "PotencialmenteObsoleto", {}),
    ("CTRL-NOME-ANTIGO", "COR", 30, [("F03", 25)], [("OUTLET BH SB", 12, "venda")], "AntigoComGiro", {}),
    ("CTRL-FORA-ESCOPO", "AUR", 30, [("M01", 60)], [("M01", 5, "venda")], None, {}),
]


def _nome_registrado(rnd: random.Random, codigo: str) -> str:
    """Nome com que a filial aparece numa linha de estoque ou venda: às vezes um nome antigo."""
    f = next(f for f in FILIAIS if f[0] == codigo)
    nomes = [f[1]] + f[2]
    return nomes[0] if rnd.random() < 0.7 else rnd.choice(nomes)


def gerar(n_produtos: int = 120, semente: int = 42) -> dict[str, list[dict]]:
    rnd = random.Random(semente)
    colecoes = _colecoes()
    marcas = [{"codigo": c, "nome": n, "descontinuada_desde": d.isoformat() if d else ""} for c, n, d in MARCAS]
    filiais = [{
        "codigo": c, "nome": n, "nomes_anteriores": "|".join(ant), "fachada": fach, "canal": canal, "tipo": tipo,
        "cidade": cid, "estado": uf, "regiao": reg, "data_abertura": ab.isoformat(),
        "data_fechamento": fe.isoformat() if fe else "",
    } for c, n, ant, fach, canal, tipo, cid, uf, reg, ab, fe in FILIAIS]

    produtos, produtos_cor, skus, classificacoes, estoque, vendas = [], [], [], [], [], []

    def novo_produto_cor(codigo_pc, produto, marca, cor, lancamento, origem, cancelado, custo):
        col = _colecao_do_lancamento(marca, lancamento, colecoes) if lancamento else ""
        produtos_cor.append({
            "produto_cor": codigo_pc, "produto": produto, "cor": cor, "colecao_original": col,
            "colecao_atual": col, "data_lancamento": lancamento.isoformat() if lancamento else "",
            "origem_data": origem, "cancelado": cancelado, "custo_unitario": custo,
        })
        for tam in GRADE[1]:
            skus.append({"sku": f"{codigo_pc}-{tam}", "produto_cor": codigo_pc, "tamanho": tam, "grade": GRADE[0]})

    for i in range(1, n_produtos + 1):
        marca = rnd.choice(MARCAS_PRODUTO)
        neg, lin, gru, sub = rnd.choice(HIERARQUIA)
        produto = f"P{i:05d}"
        produtos.append({"produto": produto, "marca": marca, "descricao": f"{sub} {rnd.choice(['Básica', 'Estampada', 'Linho', 'Malha', 'Jeans'])}",
                         "negocio": neg, "linha": lin, "grupo": gru, "subgrupo": sub})
        lancamento_base = R - timedelta(days=rnd.randint(30, 1950))
        for cor in rnd.sample(CORES, rnd.randint(1, 3)):
            pc = f"{produto}-{cor[:3].upper()}"
            lancamento = lancamento_base + timedelta(days=rnd.randint(0, 60))
            sem_data = rnd.random() < 0.04
            novo_produto_cor(pc, produto, marca, cor, None if sem_data else min(lancamento, R),
                             "" if sem_data else rnd.choice(["coleção original", "primeira entrada"]),
                             rnd.random() < 0.02, round(rnd.uniform(25, 180), 2))
            if rnd.random() < 0.08:
                classificacoes.append({"produto_cor": pc, "tipo": "TipoColecao", "valor": "TipoColecaoContinuo",
                                       "filial": "", "valido_de": lancamento.isoformat(), "valido_ate": ""})
            # Popularidade: parte dos produtos vende bem, parte para de vender.
            popularidade = rnd.lognormvariate(-0.3, 1.0)
            parou_ha = rnd.choice([0, 0, 0, 60, 150, 250, 400])  # dias desde que parou de vender
            locais = rnd.sample(LOJAS_REDE, rnd.randint(2, 4))
            if rnd.random() < 0.3:
                locais.append(FILIAL_CD)
            if rnd.random() < 0.05:
                locais.append(FILIAL_QUALIDADE)
            if rnd.random() < 0.15:
                locais.append(rnd.choice(LOJAS_MARCA))
            inicio_vendas = max(lancamento, INICIO_HISTORICO_VENDAS)
            for filial in locais:
                estoque.append({"data": R.isoformat(), "filial": _nome_registrado(rnd, filial),
                                "produto_cor": pc, "quantidade": rnd.randint(3, 250)})
                if filial in (FILIAL_CD, FILIAL_QUALIDADE):
                    continue
                abertura = next(f[9] for f in FILIAIS if f[0] == filial)
                inicio_local = max(inicio_vendas, abertura)
                fim_vendas = R - timedelta(days=parou_ha)
                dias = (fim_vendas - inicio_local).days
                if dias <= 0:
                    continue
                for _ in range(min(40, int(dias / 30 * popularidade * rnd.uniform(0.3, 1.5)))):
                    d = inicio_local + timedelta(days=rnd.randint(0, dias))
                    tipo = rnd.choices(["venda", "cancelamento", "devolucao"], [0.9, 0.05, 0.05])[0]
                    vendas.append({"data": d.isoformat(), "filial": _nome_registrado(rnd, filial),
                                   "produto_cor": pc, "quantidade": rnd.randint(1, 3), "tipo": tipo})

    for pc, marca, idade, posicoes, movs, _, extras in CASOS_CONTROLE:
        produto = f"PROD-{pc}"
        produtos.append({"produto": produto, "marca": marca, "descricao": f"Caso de controle {pc}",
                         "negocio": "Feminino", "linha": "Controle", "grupo": "Controle", "subgrupo": "Controle"})
        lancamento = meses_antes(R, idade) if idade is not None else None
        novo_produto_cor(pc, produto, marca, "Controle", lancamento,
                         "coleção original" if lancamento else "", extras.get("cancelado", False), 100.0)
        if extras.get("continuo"):
            classificacoes.append({"produto_cor": pc, "tipo": "TipoColecao", "valor": "TipoColecaoContinuo",
                                   "filial": "", "valido_de": lancamento.isoformat(), "valido_ate": ""})
        if extras.get("bloqueio"):
            classificacoes.append({"produto_cor": pc, "tipo": "Restricao", "valor": "BloqueioEnvio",
                                   "filial": extras["bloqueio"], "valido_de": (R - timedelta(days=300)).isoformat(),
                                   "valido_ate": ""})
        for filial, qtd in posicoes:
            estoque.append({"data": R.isoformat(), "filial": NOME_ATUAL[filial],
                            "produto_cor": pc, "quantidade": qtd})
        for filial, dias_atras, tipo in movs:
            nome = NOME_ATUAL.get(filial, filial)  # código -> nome atual; um nome antigo fica como está
            vendas.append({"data": (R - timedelta(days=dias_atras)).isoformat(), "filial": nome,
                           "produto_cor": pc, "quantidade": 1, "tipo": tipo})

    vendas.sort(key=lambda v: (v["data"], v["produto_cor"], v["filial"]))
    return {"marcas": marcas, "colecoes": colecoes, "filiais": filiais, "produtos": produtos,
            "produtos_cor": produtos_cor, "skus": skus, "classificacoes": classificacoes,
            "estoque": estoque, "vendas": vendas}


def salvar(dados: dict[str, list[dict]], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.csv"):
        antigo.unlink()
    for nome, linhas in dados.items():
        with open(pasta / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--produtos", type=int, default=120)
    p.add_argument("--semente", type=int, default=42)
    p.add_argument("--saida", type=Path, default=Path("dados/exemplo"))
    a = p.parse_args()
    dados = gerar(a.produtos, a.semente)
    salvar(dados, a.saida)
    print({nome: len(linhas) for nome, linhas in dados.items()}, "em", a.saida)


if __name__ == "__main__":
    main()
