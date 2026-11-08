"""Gerador de dados sintéticos de estoque para o varejo de moda.

Os dados são fictícios e reprodutíveis (mesma semente, mesmos dados). Servem para
demonstrar e testar o software sem expor dados reais de nenhuma empresa.

Uso:
    python -m retail_ontologos.gerar_dados --produtos 300 --semente 42 --saida dados/exemplo
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date
from pathlib import Path

DATA_REFERENCIA = date(2026, 10, 31)

COLECOES = [
    # codigo, nome, temporada, ano, encerrada, idade média do estoque em dias
    ("VER25", "Verão 2025", "Verão", 2025, True, 300),
    ("INV25", "Inverno 2025", "Inverno", 2025, True, 210),
    ("ALV26", "Alto Verão 2026", "Alto Verão", 2026, True, 150),
    ("RES26", "Resort 2026", "Resort", 2026, False, 90),
    ("PRI26", "Primavera 2026", "Primavera", 2026, False, 45),
]

LOCAIS = [
    # codigo, nome, tipo, regiao
    ("L01", "Loja Rio de Janeiro", "Loja", "Sudeste"),
    ("L02", "Loja São Paulo", "Loja", "Sudeste"),
    ("L03", "Loja Belo Horizonte", "Loja", "Sudeste"),
    ("L04", "Loja Porto Alegre", "Loja", "Sul"),
    ("L05", "Loja Curitiba", "Loja", "Sul"),
    ("L06", "Loja Recife", "Loja", "Nordeste"),
    ("L07", "Loja Salvador", "Loja", "Nordeste"),
    ("L08", "Loja Brasília", "Loja", "Centro-Oeste"),
    ("CD1", "Centro de Distribuição", "CentroDistribuicao", "Sudeste"),
]

CATEGORIAS = ["Vestido", "Blusa", "Calça", "Saia", "Camisa", "Jaqueta", "Short", "Macacão"]
ESTAMPAS = ["Floral", "Liso", "Listrado", "Xadrez", "Poá", "Tie-dye", "Animal print"]

# Casos de controle: valores escolhidos para cair em cada categoria com os
# parâmetros padrão (idade 180 dias, cobertura 90 dias). Usados nos testes.
CASOS_CONTROLE = [
    # sku, colecao, local, quantidade, idade_dias, vendas_90d, categoria esperada
    ("CTRL-ATIVO", "PRI26", "L01", 40, 30, 60, "Ativo"),
    ("CTRL-EXCESSO", "RES26", "L02", 300, 60, 30, "Excesso"),
    ("CTRL-ENVELHECIDO", "INV25", "L06", 20, 240, 45, "Envelhecido"),
    ("CTRL-OBSOLETO", "VER25", "L04", 450, 320, 5, "LentoOuObsoleto"),
    ("CTRL-SEMVENDA", "VER25", "L05", 80, 300, 0, "LentoOuObsoleto"),
    ("CTRL-SEMDADO", "RES26", "L03", 50, 100, None, "DadosInsuficientes"),
]


def gerar(n_produtos: int = 300, semente: int = 42) -> dict[str, list[dict]]:
    rnd = random.Random(semente)
    colecoes = [
        {"codigo": c, "nome": n, "temporada": t, "ano": a, "encerrada": e}
        for c, n, t, a, e, _ in COLECOES
    ]
    idade_media = {c[0]: c[5] for c in COLECOES}
    locais = [{"codigo": c, "nome": n, "tipo": t, "regiao": r} for c, n, t, r in LOCAIS]

    produtos, observacoes = [], []
    for i in range(1, n_produtos + 1):
        col = rnd.choice(COLECOES)[0]
        cat = rnd.choice(CATEGORIAS)
        custo = round(rnd.uniform(25, 180), 2)
        sem_custo = rnd.random() < 0.03  # parte dos produtos sem custo (CQ08)
        produtos.append({
            "sku": f"SKU{i:05d}",
            "descricao": f"{cat} {rnd.choice(ESTAMPAS)}",
            "categoria": cat,
            "colecao": col,
            "custo_unitario": "" if sem_custo else custo,
            "preco_venda": round(custo * rnd.uniform(2.0, 3.2), 2),
        })
        # Popularidade do produto e variação regional: o mesmo SKU pode ir bem em
        # uma loja e mal em outra (CQ06).
        popularidade = rnd.lognormvariate(0, 0.9)
        for loc in rnd.sample(LOCAIS, rnd.randint(2, 5)):
            fator_local = rnd.lognormvariate(0, 0.7)
            quantidade = rnd.randint(5, 400)
            idade = max(1, int(rnd.gauss(idade_media[col], 40)))
            vendas = int(quantidade * 1.1 * popularidade * fator_local * (120 / (idade + 60)))
            if rnd.random() < 0.04:
                vendas = None  # registro de vendas ausente (CQ07)
            if rnd.random() < 0.02:
                idade = None
            observacoes.append({
                "sku": f"SKU{i:05d}",
                "local": loc[0],
                "data": DATA_REFERENCIA.isoformat(),
                "quantidade": quantidade,
                "idade_dias": "" if idade is None else idade,
                "vendas_90d": "" if vendas is None else vendas,
            })

    for sku, col, loc, qtd, idade, vendas, _ in CASOS_CONTROLE:
        produtos.append({
            "sku": sku, "descricao": f"Caso de controle {sku}", "categoria": "Controle",
            "colecao": col, "custo_unitario": 100.0, "preco_venda": 250.0,
        })
        observacoes.append({
            "sku": sku, "local": loc, "data": DATA_REFERENCIA.isoformat(), "quantidade": qtd,
            "idade_dias": idade, "vendas_90d": "" if vendas is None else vendas,
        })

    return {"colecoes": colecoes, "locais": locais, "produtos": produtos, "observacoes": observacoes}


def salvar(dados: dict[str, list[dict]], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, linhas in dados.items():
        with open(pasta / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--produtos", type=int, default=300)
    p.add_argument("--semente", type=int, default=42)
    p.add_argument("--saida", type=Path, default=Path("dados/exemplo"))
    a = p.parse_args()
    dados = gerar(a.produtos, a.semente)
    salvar(dados, a.saida)
    print(f"{len(dados['produtos'])} produtos e {len(dados['observacoes'])} observações em {a.saida}")


if __name__ == "__main__":
    main()
