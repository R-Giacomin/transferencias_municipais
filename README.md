### Metodologia de Processamento e Consolidação da Base de Dados de Transferências Federais

Este documento descreve o fluxo metodológico adotado para a construção de uma base de dados consolidada referente às transferências de recursos da União. O pipeline de dados foi desenvolvido em linguagem Python, estruturado em múltiplos módulos (notebooks) e engloba etapas de extração, limpeza, transformação, padronização e união de bases de diferentes órgãos governamentais.

#### 1. Fontes de Dados e Protocolos de Extração

A coleta de dados foi arquitetada de maneira modular para extrair informações de múltiplas fontes oficiais, lidando com diferentes granularidades temporais e estruturais:

* **Portal da Transparência (CGU):** Foram extraídas as tabelas de "Recursos Transferidos" e os dados específicos do programa "Garantia Safra". Para otimizar a extração de séries históricas densas (2014 a 2026), o sistema foi programado para baixar arquivos `.zip` mensais e processá-los sequencialmente.
* **Transferegov:** Utilizado para a captura das *Transferências Discricionárias* (convênios, contratos de repasse e termos de fomento).
* **Ministério do Desenvolvimento e Assistência Social, Família e Combate à Fome (MDS):** Os dados de benefícios aos cidadãos (como Bolsa Família, Auxílio Brasil e Auxílio Gás) foram extraídos do portal de aplicações do Ministério (SAGI). O script foi arquitetado para contornar bloqueios de raspagem (*scraping*), injetando cabeçalhos (*headers*) que simulam um navegador real e passando *cookies* de sessão. Além disso, o código conta com um mecanismo de espera ativa (*polling*) e tentativas (com aguardos de 60 segundos por até 20 tentativas) para lidar com arquivos que são gerados assincronamente pelo servidor do governo (código HTTP 202).
* **Previdência Social e INSS:** Base extraída do portal de "Estatísticas Municipais" da Previdência (Sintese/MTP), cobrindo dados do Benefício de Prestação Continuada (BPC/LOAS) e benefícios previdenciários padrão.
* **Instituto Brasileiro de Geografia e Estatística (IBGE):** Foi feito o download da Divisão Territorial Brasileira (DTB 2025) via FTP para a obtenção das tabelas de municípios, permitindo a padronização e mapeamento geográfico correto das transferências.

#### 2. Pré-processamento e Limpeza (Data Cleaning)

Devido à heterogeneidade dos sistemas governamentais, procedimentos rigorosos de limpeza foram aplicados logo na ingestão:

* **Gestão de Encodings:** O pipeline previu nativamente o tratamento de diferentes codificações de texto (frequentes em bases do governo), realizando tentativas de leitura em `utf-8` e, em caso de erro (*UnicodeDecodeError*), utilizando *fallback* para `latin1` (ISO-8859-1).
* **Otimização de Memória:** Em bases massivas como o *Garantia Safra*, foi aplicada uma técnica de restrição de leitura (*usecols*), carregando para a memória RAM estritamente as variáveis essenciais (ex: Mês Referência, UF, Código SIAFI, Nome Município e Valor Parcela).
* **Limpeza Geográfica (CNPJ para Município):** Transferências com ausência de indicação territorial direta passaram por um procedimento de cruzamento no notebook "Localizar município do CNPJ". A partir do CNPJ favorecido, buscou-se identificar a sede territorial do recebedor. Os casos onde a localização permaneceu falha (ex: "CNPJs sem município localizado") foram diagnosticados, quantificados e isolados do escopo principal para evitar distorções espaciais.
* **Validação Categórica:** Foi implementada uma etapa de validação com expressões regulares (*regex*). Um exemplo notório é a checagem na coluna `COD_IBGE`, onde linhas que contivessem caracteres não numéricos (`~str.contains(r'^\d+$')`) foram sinalizadas e excluídas ou enviadas para tratamento de exceção.

#### 3. Transformação, Padronização e Classificação

Para que bases de origens distintas dialogassem perfeitamente, variáveis chaves passaram por processos de padronização semântica:

* **Chaves de Relacionamento Geográfico:** Códigos de municípios do "SIAFI" foram alinhados aos "Códigos IBGE" de 7 e 6 dígitos, permitindo o relacionamento direto das tabelas financeiras com a base demográfica e territorial extraída da DTB do IBGE.
* **Taxonomia de Programas:** Foi aplicada uma normatização nas nomenclaturas de "Função", "Subfunção", "Ação" e "Linguagem Cidadã". Por exemplo, os benefícios assistenciais foram categorizados explicitamente com o rótulo "BPC/LOAS e outros de legislação específica", uniformizando nomes ao longo dos anos.
* **Formatos de Persistência Avançada:** Todos os dados processados na etapa bruta e intermediária (CSVs, Excels, APIs) foram imediatamente convertidos e salvos no formato **Apache Parquet**. Esta escolha garante compressão eficiente de dados, preservação rigorosa da tipagem das colunas e viabiliza interações de alta performance (OLAP) em etapas posteriores usando motores como *DuckDB* ou *Pandas*.

#### 4. Consolidações Intermediárias (Módulos Temáticos)

O agrupamento dos dados foi dividido em três grandes módulos antes de se unirem na base mestra:

1. **Transferências Constitucionais e Legais:** Contendo os repasses diretos e obrigatórios da União aos entes (FPM, FPE, Royalties, etc.).
2. **Transferências Discricionárias:** Consolidação dos recursos atrelados à plataforma Transferegov (convênios e contratos condicionados a projetos específicos).
3. **Benefícios aos Cidadãos:** Um fluxo complexo de concatenação de 11 bases distintas (incluindo *Bolsa Família, Auxílio Brasil, Auxílio Gás, Gás do Povo*, entre outros), integradas em uma tabela única (`transferencias_aos_cidadaos.parquet`), harmonizando o número de famílias atendidas e os valores monetários repassados.

#### 5. Consolidação Final e Visualização

A última etapa da esteira corresponde à **"Consolidação Final das Bases"**.

* Neste processo, os três grandes eixos (Constitucionais, Discricionárias e Benefícios aos Cidadãos) foram fundidos matricialmente (*merged/joined*) tendo as variáveis temporais (Mês/Ano) e espaciais (Código IBGE/SIAFI) como chaves primárias.
* A base unificada recebeu o enriquecimento dos dados de **População Municipal**, permitindo, além da análise do volume bruto financeiro, o cálculo per capita dos recursos.
* **Análise Exploratória e Validação:** Para permitir a visualização, análise dos resultados e facilitar insights rápidos, foi implementado um aplicaticativo, disponível nesse repositório pelo link (https://r-giacomin.github.io/transferencias_municipais/)
