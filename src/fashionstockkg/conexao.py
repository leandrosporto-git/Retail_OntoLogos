"""Conexão com o Neo4j, local (Docker) ou na nuvem (Neo4j Aura).

Configure por variáveis de ambiente ou por um arquivo .env na raiz:
    NEO4J_URI=bolt://localhost:7687        (Aura: neo4j+s://xxxx.databases.neo4j.io)
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=fashionstockkg
"""
from __future__ import annotations

import os
from pathlib import Path

from neo4j import GraphDatabase, Driver

RAIZ = Path(__file__).resolve().parents[2]


def _ler_env() -> None:
    arquivo = RAIZ / ".env"
    if arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.strip().startswith("#"):
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip())


def conectar() -> Driver:
    _ler_env()
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    usuario = os.environ.get("NEO4J_USER", "neo4j")
    senha = os.environ.get("NEO4J_PASSWORD", "fashionstockkg")
    driver = GraphDatabase.driver(uri, auth=(usuario, senha))
    driver.verify_connectivity()
    return driver
