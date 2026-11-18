# Mapeamento entre a ontologia OWL e o grafo no Neo4j

O Neo4j usa o modelo de grafo de propriedades, que não é uma linguagem de ontologias.
Por isso o projeto mantém dois artefatos: a ontologia em OWL (`ontologia/retail_ontologos.ttl`),
que é a fonte do vocabulário e é verificada por um reasoner, e o grafo operacional no Neo4j,
que guarda os dados e executa as regras. O mapeamento entre os dois é feito por código
Python próprio (`src/retail_ontologos/carga.py`), sem o plugin neosemantics, para evitar
dependência de versões específicas do Neo4j.

| Elemento OWL | Elemento no Neo4j | Exemplo |
| --- | --- | --- |
| Classe | Rótulo de nó | `:PosicaoRede` |
| Subclasse de enumeração | Rótulos adicionais | `:ValorClassificacao:TipoColecao` |
| Propriedade de objeto | Tipo de relacionamento em maiúsculas | `recebeDiagnostico` vira `RECEBE_DIAGNOSTICO` |
| Propriedade de dados | Atributo do nó, mesmo nome | `saldoRede` |
| Indivíduo de classe enumerada | Nó com atributo `nome` | `(:SituacaoGiroIdade {nome: 'PotencialmenteObsoleto'})` |
| Regra de negócio | Consulta Cypher versionada + nó `:RegraNegocio` | `regras/02_diagnostico.cypher`, regra R01 |

**Garantia de conformidade:** `tests/test_ontologia.py` falha se o grafo usar qualquer rótulo,
relacionamento ou atributo que não esteja declarado na ontologia (exceto o identificador
técnico `id`).

**Por que as regras não estão em OWL/SWRL:** o diagnóstico depende de ausência de registros
e de cálculos (dias sem venda, meses desde o lançamento, custo de oportunidade). OWL opera sob a hipótese de mundo aberto, em
que a falta de um registro de venda não permite concluir que não houve venda. As regras ficam
em Cypher, que avalia o grafo como mundo fechado, e o caso de dado ausente é tratado de forma
explícita pela situação Diagnóstico pendente.

**Datas:** na ontologia, as datas usam `xsd:dateTime`, porque o reasoner HermiT só aceita os tipos do
mapa de tipos de dados do OWL 2, que não inclui `xsd:date`.
No Neo4j, as datas são carregadas como `date` (sem hora), e meses são contados em meses de calendário.

**Nomes de filial:** o código da filial é a chave. O nome atual fica em `nome` e os anteriores em
`nomesAnteriores` (ideia de rótulo preferido e alternativos). Estoque e vendas registrados com um nome antigo
são traduzidos para o código antes da carga.

**Classificação com vigência:** tipo de coleção (contínuo, coleção etc.) e bloqueio de envio são nós
`:ClassificacaoVigencia` com `validoDe` e `validoAte`, para que a regra use o valor vigente na data de referência.
