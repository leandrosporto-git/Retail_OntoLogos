# Retail OntoLogos

Protótipo de apoio à decisão para **diagnóstico e destinação de estoques obsoletos no varejo de moda**,
fundamentado em uma ontologia de domínio (OWL) e implementado com Neo4j.

Projeto Final de Programação (INF2102, PUC-Rio), de Leandro Porto, com orientação do Prof. Sérgio Lifschitz.
Continua o relatório técnico *Ontologia para diagnóstico e destinação de estoques obsoletos no Varejo de Moda*
(Monografias em Ciência da Computação nº 06/2026, DI/PUC-Rio).

> **Estado:** versão 0.1.0, prova de conceito em desenvolvimento. Os dados de exemplo são fictícios e os limites
> das regras são hipotéticos, ainda não validados com especialistas.

## O que o programa faz

1. Lê uma ontologia OWL que define o vocabulário do domínio: produto, coleção, local, observação de estoque,
   indicador, critério, evidência, diagnóstico, causa provável, recomendação, regra e área de negócio.
2. Carrega no Neo4j dados de produtos, coleções, locais e estoques (CSV).
3. Executa regras de negócio explícitas e versionadas, escritas em Cypher, que:
   - calculam indicadores (cobertura, sell-through, custo de oportunidade);
   - classificam cada estoque, em cada loja e data, como **Ativo, Excesso, Envelhecido, Lento ou obsoleto** ou
     **Dados insuficientes**;
   - registram as evidências e causas prováveis de cada diagnóstico;
   - recomendam ações de destinação (transferência entre lojas, remarcação, liquidação).
4. Mostra tudo numa interface web (Streamlit), incluindo, para cada diagnóstico, a regra e a versão que o produziram.

## Como rodar

### Opção A: tudo com Docker (recomendado)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

Abra a interface em http://localhost:8501. O navegador do Neo4j fica em http://localhost:7474
(usuário `neo4j`, senha `retail_ontologos`).

### Opção B: Python local + Neo4j Aura (sem instalar banco de dados)

1. Crie uma instância gratuita em [Neo4j Aura](https://neo4j.com/cloud/aura-free/) e guarde a URI e a senha.
2. Copie `.env.example` para `.env` e preencha a URI (`neo4j+s://...`) e a senha.
3. Com Python 3.11 ou mais recente:

```bash
pip install -r requirements.txt
export PYTHONPATH=src                       # no Windows (PowerShell): $env:PYTHONPATH="src"
python -m retail_ontologos.gerar_dados        # gera dados/exemplo/*.csv (opcional: já vêm no repositório)
python -m retail_ontologos.carga              # carrega o grafo (apaga o conteúdo anterior)
python -m retail_ontologos.motor              # roda as regras
streamlit run app/streamlit_app.py
```

### Testes

```bash
python -m pytest
```

Cada questão de competência da ontologia é um teste automatizado (`tests/test_questoes_competencia.py`).
Também há testes de consistência lógica da ontologia com o reasoner HermiT (requer Java) e de conformidade
entre o grafo e a ontologia. Sem Neo4j disponível, os testes que dependem do banco são pulados.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `ontologia/` | Ontologia OWL em Turtle (abre no [Protégé](https://protege.stanford.edu/)) |
| `regras/` | Regras em Cypher, uma consulta por regra, e `parametros.yaml` com limites e taxa de custo de capital |
| `dados/exemplo/` | Dataset sintético (semente 42) |
| `src/retail_ontologos/` | Gerador de dados, carga, motor de regras, leitura da ontologia |
| `app/` | Interface Streamlit |
| `tests/` | Testes automatizados |
| `docs/` | Questões de competência e mapeamento OWL → Neo4j |

## Como mudar uma regra

1. Ajuste os limites em `regras/parametros.yaml` ou a consulta no arquivo `.cypher` correspondente.
2. Suba a versão no cabeçalho da regra (`// regra: R01 | versao: 0.2.0 | ...`).
3. Rode `python -m retail_ontologos.motor` e `python -m pytest`.

## Licença

Código sob licença MIT. Ontologia sob CC BY 4.0. Ver `LICENSE`.
