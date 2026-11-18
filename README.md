# Retail OntoLogos

Protótipo de apoio à decisão para **diagnóstico e destinação de estoques obsoletos no varejo de moda**,
fundamentado em uma ontologia de domínio (OWL) e implementado com Neo4j.

Projeto Final de Programação (INF2102, PUC-Rio), de Leandro Porto, com orientação do Prof. Sérgio Lifschitz.
Continua o relatório técnico *Ontologia para diagnóstico e destinação de estoques obsoletos no Varejo de Moda*
(Monografias em Ciência da Computação nº 06/2026, DI/PUC-Rio).

> **Estado:** versão 0.2.0 (ontologia V_Zero), prova de conceito em desenvolvimento. Os dados de exemplo são
> fictícios (marcas e filiais inventadas). Os limites das regras (24 meses e 180 dias) seguem o documento de
> definições validado em 17/11/2026; a definição de venda válida e a fórmula de excesso ainda estão em aberto.

## O que o programa faz

1. Lê uma ontologia OWL (`ontologia/retail_ontologos.ttl`) com o vocabulário do domínio: marca, coleção, produto,
   produto-cor, SKU, filial, escopo de rede, classificação com vigência, posição de estoque, posição na rede,
   venda, diagnóstico, evidência, motivo, recomendação e regra de negócio.
2. Carrega no Neo4j marcas, coleções, filiais (com nomes anteriores), produtos, classificações, estoque e vendas (CSV).
3. Executa regras de negócio explícitas e versionadas, escritas em Cypher:
   - **R00 preparação:** consolida o saldo de cada produto-cor nas filiais do escopo, calcula dias sem venda válida
     na rede, meses desde o lançamento e custo de oportunidade, e marca dados inconsistentes (saldo negativo);
   - **R01 diagnóstico:** classifica cada produto-cor com saldo positivo como **Ativo, Antigo com giro, Sem giro em
     atenção, Potencialmente obsoleto** ou **Diagnóstico pendente** (mais de 180 dias sem venda × mais de 24 meses
     desde o lançamento, limites estritos), com as evidências de cada critério;
   - **R02 motivos:** registra motivos que coexistem com a situação (marca descontinuada, produto com defeito,
     produto cancelado, oportunidade local, bloqueio de envio, contínuo com sinal de obsolescência);
   - **R03 recomendação:** sugere a destinação de cada motivo e de cada potencialmente obsoleto (transferência,
     ação comercial, baixa, recolher e enviar à filial de defeito, manter no CD, revisar classificação) e ordena
     as recomendações pelo custo de oportunidade.
4. Mostra tudo numa interface web (Streamlit), incluindo, para cada diagnóstico, as evidências, a regra e a versão.

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
| `regras/` | Regras em Cypher (`01_preparacao` a `04_recomendacao`) e `parametros.yaml` com data de referência, escopo, limites e taxa de custo de capital |
| `dados/exemplo/` | Dataset sintético (120 produtos, semente 42, mais 17 casos de controle `CTRL-*`) no formato de marcas, coleções, filiais, produtos, produtos_cor, skus, classificacoes, estoque e vendas |
| `src/retail_ontologos/` | Gerador de dados, carga, motor de regras, leitura da ontologia |
| `app/` | Interface Streamlit |
| `tests/` | Testes automatizados |
| `docs/` | Questões de competência e mapeamento OWL → Neo4j |

## Como mudar uma regra

1. Ajuste os limites em `regras/parametros.yaml` ou a consulta no arquivo `.cypher` correspondente.
2. Suba `versao_regras` em `parametros.yaml` e a versão no cabeçalho da regra (`// regra: R01 | versao: 0.2.0 | ...`).
3. Rode `python -m retail_ontologos.motor` e `python -m pytest`.

## Licença

Código sob licença MIT. Ontologia sob CC BY 4.0. Ver `LICENSE`.
