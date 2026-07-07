# marimo: requirements=["duckdb", "plotly", "folium"]

import marimo

__generated_with = "0.23.3"
app = marimo.App(
    width="medium",
    app_title="Painel Transferências Municipais",
    css_file="custom.css",
)


@app.cell
async def _():
    import sys
    import os

    # Definimos a variável fora do if para garantir que ela sempre exista
    ambiente_preparado = False

    # Se estivermos rodando no navegador (WASM)
    if "pyodide" in sys.modules:
        import micropip  # type: ignore
        import pyodide.http  # type: ignore

        # Apenas plotly e folium precisam de micropip — são pacotes puros Python
        # não pré-compilados no Pyodide. branca e jinja2 são dependências
        # transitivas do folium e instalados automaticamente.
        await micropip.install(["plotly", "folium"])

        async def baixar_arquivo(url, destino):
            pasta = os.path.dirname(destino)
            if pasta:
                os.makedirs(pasta, exist_ok=True)

            resposta = await pyodide.http.pyfetch(url)
            # Trava de segurança: se o arquivo não for encontrado, ele avisa na hora!
            if not resposta.ok:
                raise Exception(f"Erro ao baixar {url}. Status: {resposta.status}")

            conteudo = await resposta.bytes()
            with open(destino, "wb") as f:
                f.write(conteudo)

        # URL base do seu GitHub Pages para forçar o download correto
        base_url = "https://r-giacomin.github.io/transferencias_municipais"

        await baixar_arquivo(f"{base_url}/transferencias_consolidada_final.parquet", "transferencias_consolidada_final.parquet")
        await baixar_arquivo(f"{base_url}/populacao.parquet", "populacao.parquet")
        await baixar_arquivo(f"{base_url}/assets/municipios_br_simpl.geojson", "assets/municipios_br_simpl.geojson")

    # Avisa que tudo terminou
    ambiente_preparado = True
    return (ambiente_preparado,)


@app.cell
def _(ambiente_preparado):
    _ = ambiente_preparado  # <-- ISSO AQUI impede o Marimo de apagar o argumento!

    import marimo as mo
    import pandas as pd
    import duckdb
    import plotly.express as px
    import json
    import numpy as np
    from scipy.stats import gaussian_kde
    import plotly.graph_objects as go
    import folium
    import branca

    # Conectar ao DuckDB
    con = duckdb.connect()
    
    # Criar a view ou tabela consolidada unindo transferências e população
    con.execute("""
        CREATE VIEW dados AS
        SELECT 
            t.ANO as Ano,
            t."TIPO TRANSFERÊNCIA" as tipo_transferencia,
            t.COD_IBGE as codigo_ibge,
            t.UF as sigla_uf,
            t.MUNICÍPIO as municipio,
            t."LINGUAGEM CIDADÃ" as linguagem_cidada,
            t."VALOR TRANSFERIDO" as valor_transferido,
            t.DESTINO as destino,
            t.REGIÃO as regiao,
            p.populacao as populacao
        FROM 'transferencias_consolidada_final.parquet' t
        LEFT JOIN 'populacao.parquet' p 
          ON t.ANO = p.ANO AND t.COD_IBGE = p.COD_IBGE
    """)
    
    # Carregar dados em df_full (para compatibilidade e exportação)
    df_full = con.execute("SELECT * FROM dados").df()
    
    # Obter listas únicas para os filtros
    lista_anos = sorted(df_full['Ano'].dropna().unique())
    lista_regioes = sorted(df_full['regiao'].dropna().unique())
    lista_ufs = sorted(df_full['sigla_uf'].dropna().unique())
    lista_tipos = sorted(df_full['tipo_transferencia'].dropna().unique())
    lista_linguagens = sorted(df_full['linguagem_cidada'].dropna().unique())
    
    map_regiao_uf = df_full.groupby('regiao')['sigla_uf'].unique().apply(list).to_dict()
    return (
        con,
        df_full,
        folium,
        gaussian_kde,
        go,
        json,
        lista_anos,
        lista_linguagens,
        lista_regioes,
        lista_tipos,
        lista_ufs,
        map_regiao_uf,
        mo,
        np,
        pd,
        px,
    )


@app.cell
def _():
    METODOLOGIA_HTML = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Relatório Metodológico - Base de Dados de Transferências Federais</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }
            h2 {
                color: #2c3e50;
                border-bottom: 2px solid #ecf0f1;
                padding-bottom: 5px;
                margin-top: 30px;
            }
            h3 {
                color: #34495e;
                margin-top: 20px;
            }
            ul {
                margin-bottom: 20px;
            }
            li {
                margin-bottom: 10px;
            }
            code {
                background-color: #f4f6f6;
                color: #c0392b;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.95em;
                font-weight: bold;
            }
            hr {
                border: 0;
                border-top: 1px solid #ecf0f1;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>

        <p>Este documento apresenta o relatório metodológico completo referente à estruturação do pipeline de dados para consolidação das finanças públicas federais repassadas aos entes subnacionais.</p>

        <hr>

        <h2>1. Objetivo</h2>
        <p>O objetivo principal deste projeto de engenharia de dados é identificar, quantificar e qualificar rigorosamente todas as transferências de recursos oriundas do Governo Federal com destino aos Estados, Municípios e aos cidadãos. A esteira visa construir uma base de dados unificada, padronizada e de alta granularidade, permitindo o rastreamento preciso dos fluxos financeiros e viabilizando análises de políticas públicas e distribuição orçamentária no território nacional.</p>

        <h2>2. Fontes dos Dados</h2>
        <p>A arquitetura de ingestão de dados foi dividida em três blocos temáticos principais, garantindo a captura das diferentes naturezas de repasses:</p>

        <h3>Bloco 1: Transferências Constitucionais e Legais</h3>
        <ul>
            <li><strong>Portal da Transparência (CGU):</strong> Arquivos detalhados de "Recursos Transferidos" (série histórica de 2014 a 2026).</li>
            <li><strong>Tesouro Transparente (STN):</strong> Dados extraídos via API (APEX) referentes às transferências diretas aos estados e municípios (ex: FPM, FPE, FUNDEB, Royalties, LC 176/2020).</li>
        </ul>

        <h3>Bloco 2: Transferências Discricionárias</h3>
        <ul>
            <li><strong>Plataforma Transferegov (antigo Siconv):</strong> Base central para extração de dados de convênios, contratos de repasse, termos de parceria e termos de fomento.</li>
        </ul>

        <h3>Bloco 3: Benefícios aos Cidadãos</h3>
        <ul>
            <li><strong>Ministério do Desenvolvimento e Assistência Social (MDS / SAGI):</strong> Dados de programas de transferência de renda (Bolsa Família, Auxílio Brasil, Auxílio Gás).</li>
            <li><strong>Previdência Social (INSS/MTP):</strong> Base de estatísticas municipais contemplando o BPC/LOAS (assistencial) e benefícios previdenciários padrão.</li>
            <li><strong>Portal da Transparência (CGU):</strong> Microdados agregados de programas sazonais e específicos (Garantia Safra, Seguro Defeso, PETI e Pé de Meia).</li>
        </ul>

        <h2>3. Padronização das Variáveis</h2>
        <p>Para garantir a interoperabilidade entre as dezenas de tabelas heterogêneas, as bases foram pivotadas e padronizadas para conter o seguinte dicionário de dados fundamental:</p>
        <ul>
            <li><code>ANO</code>: Identificador temporal da transferência (extraído da competência/mês de referência).</li>
            <li><code>TIPO TRANSFERÊNCIA</code>: Categoria macro do recurso (ex: Constitucional e Legal, Transferência Discricionária, Benefícios aos cidadãos).</li>
            <li><code>COD_IBGE</code>: Chave primária geográfica de 7 dígitos, essencial para o relacionamento com bases demográficas e territoriais.</li>
            <li><code>UF</code>: Sigla da Unidade da Federação.</li>
            <li><code>NOME MUNICÍPIO</code>: Nome do município padronizado conforme a Divisão Territorial Brasileira.</li>
            <li><code>LINGUAGEM CIDADÃ</code>: Taxonomia amigável e unificada do programa ou ação orçamentária (ex: "Pé de Meia", "FUNDEB - Origem estadual", "Erradicação do Trabalho Infantil - PETI").</li>
            <li><code>VALOR TRANSFERIDO</code>: Montante financeiro efetivamente repassado ou desembolsado no período (formato numérico float).</li>
            <li><code>DESTINO</code>: Indicador da esfera governamental ou social recebedora do recurso.</li>
            <li><code>DESCRICAO_EMENDA_SIAFI</code>: Identificação qualitativa de emendas parlamentares atreladas ao repasse, mapeadas a partir dos sistemas estruturantes.</li>
        </ul>

        <h2>4. Classificação da Variável ‘DESTINO’ (Estadual e Municipal)</h2>
        <p>Aplicada primariamente aos Blocos 1 e 2, a variável <code>DESTINO</code> resolve a ambiguidade de repasses feitos geograficamente dentro de um município, mas que pertencem à contabilidade do Estado (e vice-versa).</p>
        <ul>
            <li>A classificação é realizada por meio de uma matriz condicional estruturada (CASE WHEN no DuckDB/Pandas), que cruza as colunas originais de NOME MODALIDADE APLICAÇÃO DESPESA e TIPO FAVORECIDO.</li>
            <li>O algoritmo avalia cada registro para determinar se a entidade recebedora (Fundo, CNPJ privado, Consórcio, ou Administração Direta) caracteriza uma transferência efetivamente de destino 'Municipal' ou 'Estadual', garantindo precisão na alocação da despesa pública.</li>
        </ul>

        <h2>5. Detalhamento do Processo de Cada Notebook por Bloco</h2>

        <h3>Bloco 1: Transferências Constitucionais e Legais</h3>
        <ul>
            <li><strong>1.1 Recursos transferidos:</strong> Realiza a ingestão iterativa (mês a mês) dos ZIPs do Portal da Transparência (2014-2026). Agrupa os dados mensais, converte valores financeiros e utiliza DuckDB (UNION_BY_NAME) para empilhar toda a série histórica. Inicia o mapeamento SIAFI para IBGE.</li>
            <li><strong>1.2 Localizar município do CNPJ:</strong> Isola os CNPJs recebedores que não possuem identificação de município. Dispara consultas assíncronas em lote à API minhareceita.org para capturar a sede geográfica (Código IBGE) do favorecido.</li>
            <li><strong>1.3 Finalização:</strong> Módulo central de governança. Cruza os repasses sem município com a tabela de CNPJs geolocalizados. Aplica regras rígidas de exclusão (repasses ao exterior, organizações internacionais e ações residuais). Consome via API do Tesouro os valores exatos de FPM e Fundeb. De forma crucial, calcula os valores distribuídos pelos Estados aos Municípios (cota-parte) e injeta registros com sinal negativo (VALOR * -1) na rubrica Estadual correspondente, eliminando o risco de dupla contagem financeira.</li>
        </ul>

        <h3>Bloco 2: Transferências Discricionárias</h3>
        <ul>
            <li><strong>2.1 Transferências Discricionárias:</strong> Extrai os dados do Transferegov (Siconv) focando no recurso financeiro desembolsado. Durante o processamento, aplica-se uma tabela de correção específica (merge no Python) para remapear as ações orçamentárias atreladas a programas no conjunto de dados do Siconv, garantindo que os códigos específicos sejam associados corretamente aos nomes de desenvolvimento regional. Após a higienização financeira e espacial, os dados são compactados em Parquet.</li>
        </ul>

        <h3>Bloco 3: Benefícios aos Cidadãos</h3>
        <ul>
            <li><strong>Programas MDS:</strong> Código estruturado para contornar bloqueios (headers e polling) e extrair os dados do SAGI, harmonizando programas de diferentes governos (Bolsa Família/Auxílio Brasil) e isolando valores e quantidade de famílias.</li>
            <li><strong>Previdenciários e Assistenciais:</strong> Filtra as bases da Previdência Social, separando rigidamente o BPC/LOAS (benefício assistencial de natureza continuada) das rubricas de previdência contributiva (aposentadorias comuns).</li>
            <li><strong>Sazonais e Educacionais:</strong> (Garantia Safra, Seguro Defeso, PETI, Pé de Meia). Rotinas de extração otimizadas com leitura particionada (chunking) para evitar estouro de memória (Out of Memory). Convertem microdados em agregados mensais municipais. Aplicam a padronização De-Para (SIAFI para IBGE), tratam dados de devolução/estorno e preenchem competências vazias com zero.</li>
            <li><strong>3.1 Consolidação:</strong> Funciona como um hub. Realiza a concatenação matricial completa das tabelas produzidas no Bloco 3, preenche as lacunas (fillna(0)) geradas pela ausência de repasse de determinados programas em meses específicos, e salva o conjunto de dados da pessoa física no arquivo consolidado em formato Parquet.</li>
        </ul>

        <p>A etapa derradeira do projeto (Consolidação final das bases) empilha de forma harmonizada estes três blocos já higienizados, adiciona os denominadores de população municipal do IBGE para cálculos per capita, e habilita a auditoria visual dos resultados via interfaces gráficas interativas.</p>

    </body>
    </html>
    """
    return (METODOLOGIA_HTML,)


@app.cell
def _(mo):
    header = mo.Html("""
    <div class="gov-header">
        <div class="gov-title">
            <div>
                <h1>📊 Painel de Transferências Municipais</h1>
                <p>Mapeamento de Recursos da União para Entes Subnacionais e Cidadãos</p>
            </div>
        </div>
    </div>
    """)
    return (header,)


@app.cell
def _(lista_anos, lista_regioes, lista_tipos, lista_linguagens, mo):
    filtro_ano = mo.ui.slider(
        start=int(min(lista_anos)), stop=int(max(lista_anos)), step=1,
        value=int(max(lista_anos)), label="**Ano**", full_width=False, show_value=True)

    filtro_regiao = mo.ui.dropdown(
        options={"Todas": "Todas", **{r: r for r in lista_regioes}},
        value="Todas", label="**Região**"
    )
    
    filtro_destino = mo.ui.dropdown(
        options={"Apenas Municipal": "Municipal", "Municipal + Estadual (Todos)": "Todos"},
        value="Municipal + Estadual (Todos)", label="**Destino**"
    )
    
    filtro_tipo = mo.ui.multiselect(
        options={t: t for t in lista_tipos},
        value=lista_tipos, label="**Tipo de Transferência**"
    )
    
    filtro_linguagem = mo.ui.multiselect(
        options={l: l for l in lista_linguagens},
        value=lista_linguagens, label="**Linguagem Cidadã**"
    )
    
    filtro_metrica = mo.ui.dropdown(
        options={"Valor Transferido": "valor", "Transferência per capita": "per_capita"},
        value="Transferência per capita", label="**Métrica**"
    )
    filtro_inflacao = mo.ui.switch(value=False, label="**Valores em Reais de 2025**")
    return filtro_ano, filtro_regiao, filtro_destino, filtro_tipo, filtro_linguagem, filtro_metrica, filtro_inflacao


@app.cell
def _(filtro_regiao, lista_ufs, map_regiao_uf, mo):
    # Lógica de filtro hierárquico para UF
    _ufs_disponiveis = lista_ufs
    if filtro_regiao.value != "Todas":
        _ufs_disponiveis = sorted(map_regiao_uf.get(filtro_regiao.value, []))

    filtro_uf = mo.ui.dropdown(
        options={"Todas": "Todas", **{u: u for u in _ufs_disponiveis}},
        value="Todas", label="**UF**"
    )
    return (filtro_uf,)


@app.cell
def _(con, filtro_ano, filtro_regiao, filtro_uf, filtro_destino, filtro_tipo, filtro_linguagem, filtro_metrica, filtro_inflacao):
    where_parts = ["Ano = ?"]
    params_list = [str(filtro_ano.value)]
    
    if filtro_regiao.value != "Todas":
        where_parts.append("regiao = ?")
        params_list.append(filtro_regiao.value)
    if filtro_uf.value != "Todas":
        where_parts.append("sigla_uf = ?")
        params_list.append(filtro_uf.value)
    if filtro_destino.value == "Municipal":
        where_parts.append("destino = 'Municipal'")
    
    if len(filtro_tipo.value) > 0:
        _placeholders_tipo = ', '.join(['?'] * len(filtro_tipo.value))
        where_parts.append(f"tipo_transferencia IN ({_placeholders_tipo})")
        params_list.extend(filtro_tipo.value)
    else:
        where_parts.append("1=0")
        
    if len(filtro_linguagem.value) > 0:
        _placeholders_ling = ', '.join(['?'] * len(filtro_linguagem.value))
        where_parts.append(f"linguagem_cidada IN ({_placeholders_ling})")
        params_list.extend(filtro_linguagem.value)
    else:
        where_parts.append("1=0")

    where_clause = ' AND '.join(where_parts)
    
    sql_query = f"""
        SELECT 
            Ano,
            codigo_ibge,
            municipio,
            sigla_uf,
            regiao,
            MAX(populacao) as Populacao,
            SUM(valor_transferido) as Total_Transferido
        FROM dados 
        WHERE {where_clause}
        GROUP BY Ano, codigo_ibge, municipio, sigla_uf, regiao
    """
    df_filtered = con.execute(sql_query, params_list).df()
    
    fatores_inflacao = {
        2014: 1.8235, 2015: 1.6477, 2016: 1.5502, 2017: 1.5058,
        2018: 1.4514, 2019: 1.3914, 2020: 1.3312, 2021: 1.2095,
        2022: 1.1435, 2023: 1.0930, 2024: 1.0426, 2025: 1.0000
    }
    
    if filtro_inflacao.value:
        fator = fatores_inflacao.get(int(filtro_ano.value), 1.0)
        df_filtered['Total_Transferido'] = df_filtered['Total_Transferido'] * fator
    
    if filtro_metrica.value == 'per_capita':
        df_filtered['Metrica'] = (df_filtered['Total_Transferido'] / df_filtered['Populacao']).astype(float)
        nome_metrica = 'Transferência per capita (R$ 2025)' if filtro_inflacao.value else 'Transferência per capita (R$)'
    else:
        df_filtered['Metrica'] = df_filtered['Total_Transferido'].astype(float)
        nome_metrica = 'Valor Transferido (R$ 2025)' if filtro_inflacao.value else 'Valor Transferido (R$)'
        
    df_filtered = df_filtered.sort_values('Metrica', ascending=False)
    
    return df_filtered, nome_metrica


@app.cell
def _(df_filtered, mo, nome_metrica):
    n_mun = len(df_filtered)
    total_transferido = df_filtered['Total_Transferido'].sum() if n_mun > 0 else 0
    media_metrica = df_filtered['Metrica'].mean() if n_mun > 0 else 0
    pop_total = df_filtered['Populacao'].sum() if n_mun > 0 else 0

    def kpi(title, value, sub=""):
        return f'<div class="kpi-card"><h3>{title}</h3><div class="value">{value}</div><div class="sub">{sub}</div></div>'

    total_transferido_formatado = f"R$ {total_transferido / 1e9:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " bi"

    kpi_html = mo.Html(f"""<div class="kpi-row">
        {kpi("Municípios", f"{n_mun:,}".replace(",","."), "no filtro selecionado")}
        {kpi("Total Transferido", total_transferido_formatado, "Valor consolidado")}
        {kpi("Média da Métrica", f"R$ {media_metrica:,.2f}".replace(",","X").replace(".",",").replace("X","."), nome_metrica)}
        {kpi("Pop. Total", f"{pop_total:,.0f}".replace(",","."), "habitantes")}
    </div>""")
    return (kpi_html,)


@app.cell
def _(df_filtered, folium, json, mo, nome_metrica):
    # Carregar e processar o GeoJSON removendo o último dígito do codarea
    geojson_path = "./assets/municipios_br_simpl.geojson"

    # Carregar GeoJSON
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)

    # Processar cada feature: remover o último dígito do codarea
    for feature in geojson_data['features']:
        if 'codarea' in feature['properties']:
            codarea_original = feature['properties']['codarea']
            # Remover o último dígito (converter de 7 para 6 dígitos)
            codarea_6dig = codarea_original[:-1] if codarea_original else ""
            feature['properties']['codarea'] = codarea_6dig

    # Preparar dados
    map_data = df_filtered[['codigo_ibge', 'Metrica', 'municipio', 'sigla_uf']].copy()
    # Garantir 6 dígitos para o merge com GeoJSON e usar .str para segurança (trata NAs e PyArrow scalars)
    map_data['codigo_ibge'] = map_data['codigo_ibge'].astype(str).str.replace(r'\.0$', '', regex=True).str[:6].str.zfill(6)

    if map_data.empty:
        fig_map = mo.md("Sem dados para exibir no mapa.")
    else:
        # Calcular bins
        _min, _max = map_data['Metrica'].min(), map_data['Metrica'].max()
        if _min == _max:
            _min = _min * 0.9
            _max = _max * 1.1

        # Criar o mapa base com coordenadas corrigidas para o Brasil
        _m = folium.Map(
            location=[-14.2350, -51.9253],  # Centro geográfico do Brasil
            zoom_start=4.2,  # Zoom adequado para mostrar o país inteiro
            tiles="cartodbpositron",
            width='100%',  # Largura 100% do contêiner
            height='600px',  # Altura fixa
            control_scale=True  # Adiciona escala no mapa
        )

        # Ajustar os bounds máximo para garantir que todo o Brasil seja visível
        _m.fit_bounds([[-33.75, -73.98], [5.27, -34.79]])  # Bounding box do Brasil

        # Adicionar choropleth com o GeoJSON processado
        choropleth = folium.Choropleth(
            geo_data=geojson_data,
            data=map_data,
            columns=["codigo_ibge", "Metrica"],
            key_on="feature.properties.codarea",
            fill_color="PuBuGn",
            fill_opacity=0.9,
            line_opacity=0.01,
            legend_name=nome_metrica,
            bins=10,
            highlight=True,
            reset=True,
            smooth_factor=0.5,
            nan_fill_color="lightgray",
            nan_fill_opacity=0.3
        ).add_to(_m)

        # Criar dicionários para lookup rápido
        nome_dict = dict(zip(map_data['codigo_ibge'], map_data['municipio']))
        rpc_dict = dict(zip(map_data['codigo_ibge'], map_data['Metrica']))

        # Enriquecer o GeoJSON com nomes e valores formatados para o tooltip
        for feature in choropleth.geojson.data['features']:
            codarea = feature['properties'].get('codarea', '')
            if codarea in nome_dict:
                feature['properties']['nome_mun'] = nome_dict[codarea]
                valor = rpc_dict[codarea]
                feature['properties']['rpc_str'] = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                feature['properties']['nome_mun'] = 'Sem dado'
                feature['properties']['rpc_str'] = 'N/A'

        # Adicionar tooltip único com todas as informações
        folium.GeoJsonTooltip(
            fields=['nome_mun', 'codarea', 'rpc_str'],
            aliases=['Município: ', 'Código IBGE: ', 'RPC: '],
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px; border: 1px solid grey; border-radius: 5px;")
        ).add_to(choropleth.geojson)

        # JavaScript para garantir que o mapa ocupe todo o espaço
        fix_size_js = """
        <script>
        setTimeout(function() {
            var mapDiv = document.querySelector('.folium-map');
            if (mapDiv) {
                mapDiv.style.width = '100%';
                mapDiv.style.height = '600px';
                var mapObj = window[mapDiv.id];
                if (mapObj) {
                    mapObj.invalidateSize();
                    mapObj.setView([-14.2350, -51.9253], 4.2);
                }
            }
        }, 200);
        </script>
        """
        _m.get_root().html.add_child(folium.Element(fix_size_js))

        # Usar um contêiner HTML com CSS adequado (mesmo padrão do projeto de referência)
        fig_map = mo.Html(f'''
        <div style="width: 100%; height: 600px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
            {_m._repr_html_()}
        </div>
        ''')
    return (fig_map,)


@app.cell
def _(
    con,
    df_filtered,
    filtro_ano,
    filtro_regiao,
    filtro_uf,
    filtro_destino,
    filtro_tipo,
    filtro_linguagem,
    filtro_metrica,
    filtro_inflacao,
    nome_metrica,
    gaussian_kde,
    go,
    mo,
    np,
    pd,
    px,
):

    # Gráfico de Rank (Top 10 / Bot 10)
    top10 = df_filtered.nlargest(10, 'Metrica')
    bot10 = df_filtered.nsmallest(10, 'Metrica')
    rank_df = pd.concat([top10, bot10]).sort_values('Metrica', ascending=True).copy()
    rank_df['mun_uf'] = rank_df['municipio'] + ' - ' + rank_df['sigla_uf']

    fig_rank = px.bar(
        rank_df, y='mun_uf', x='Metrica', orientation='h',
        color='Metrica', color_continuous_scale='Teal',
        labels={'Metrica': nome_metrica, 'mun_uf': ''},
        title=f'Top 10 e Bottom 10 Municípios por Métrica em {filtro_ano.value}'
    )
    fig_rank.update_traces(textfont_size=10, textangle=0, cliponaxis=False)
    fig_rank.update_layout(
        template='plotly_white',
        height=500,
        margin=dict(l=0, r=50, t=50, b=0),
        showlegend=False,
        coloraxis_showscale=False,
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)'),
        yaxis=dict(categoryorder='total ascending')
    )

    # Função auxiliar para gerar curvas KDE com preenchimento (estilo Seaborn)
    def create_kde_plotly(df, x_col, hue_col=None, title="", color_map=None):
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly

        if hue_col and hue_col in df.columns:
            categories = sorted(df[hue_col].unique())
            for i, cat in enumerate(categories):
                subset = df[df[hue_col] == cat][x_col].dropna()
                if len(subset) < 3: continue

                kde = gaussian_kde(subset)
                x_range = np.linspace(df[x_col].min(), df[x_col].max(), 200)
                y_vals = kde(x_range)

                trace_color = color_map.get(cat, colors[i % len(colors)]) if color_map else colors[i % len(colors)]

                fig.add_trace(go.Scatter(
                    x=x_range, y=y_vals, mode='lines',
                    line=dict(width=2, color=trace_color),
                    fill='tozeroy', name=str(cat), opacity=0.4
                ))
        else:
            data = df[x_col].dropna()
            if len(data) > 2:
                kde = gaussian_kde(data)
                x_range = np.linspace(data.min(), data.max(), 200)
                y_vals = kde(x_range)
                fig.add_trace(go.Scatter(
                    x=x_range, y=y_vals, mode='lines',
                    line=dict(width=3, color='#1351B4'),
                    fill='tozeroy', name='Geral', opacity=0.5
                ))

        fig.update_layout(
            title=title, xaxis_title=nome_metrica, yaxis_title='Densidade',
            height=480, margin=dict(l=0, r=20, t=60, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
            template='plotly_white'
        )
        return fig

    # NOVO: Gráfico de Densidade Geral (KDE)
    fig_dist_total = create_kde_plotly(df_filtered, 'Metrica', title=f'Densidade Geral da Métrica dos Municípios em {filtro_ano.value}')

    # Consistência das categorias para os dois gráficos
    _group_col = 'sigla_uf' if (filtro_regiao.value != "Todas" or filtro_uf.value != "Todas") else 'regiao'
    _group_label = 'UF' if _group_col == 'sigla_uf' else 'Região'

    unique_cats = sorted(df_filtered[_group_col].dropna().unique())
    plotly_colors = px.colors.qualitative.Plotly
    shared_color_map = {cat: plotly_colors[i % len(plotly_colors)] for i, cat in enumerate(unique_cats)}

    # NOVO: Gráfico de Densidade com Hue (Região ou UF)
    fig_dist_hue = create_kde_plotly(df_filtered, 'Metrica', hue_col=_group_col, title=f'Densidade da Métrica dos Municípios por {_group_label} em {filtro_ano.value}', color_map=shared_color_map)

    # Gráfico de Trajetória Temporal Responsivo
    _where_ts = []
    _params_ts = []
    if filtro_regiao.value != "Todas":
        _where_ts.append("regiao = ?")
        _params_ts.append(filtro_regiao.value)
    if filtro_uf.value != "Todas":
        _where_ts.append("sigla_uf = ?")
        _params_ts.append(filtro_uf.value)
    if filtro_destino.value == "Municipal":
        _where_ts.append("destino = 'Municipal'")
    if len(filtro_tipo.value) > 0:
        _placeholders_tipo_ts = ', '.join(['?'] * len(filtro_tipo.value))
        _where_ts.append(f"tipo_transferencia IN ({_placeholders_tipo_ts})")
        _params_ts.extend(filtro_tipo.value)
    else:
        _where_ts.append("1=0")
    if len(filtro_linguagem.value) > 0:
        _placeholders_ling_ts = ', '.join(['?'] * len(filtro_linguagem.value))
        _where_ts.append(f"linguagem_cidada IN ({_placeholders_ling_ts})")
        _params_ts.extend(filtro_linguagem.value)
    else:
        _where_ts.append("1=0")

    _where_clause = f"WHERE {' AND '.join(_where_ts)}" if _where_ts else ""
    _metrica_expr = "SUM(valor_transferido)" if filtro_metrica.value == 'valor' else "SUM(valor_transferido)/SUM(populacao)"

    _ts_query = f"""
        SELECT Ano, {_group_col}, {_metrica_expr} as media_metrica 
        FROM (
            SELECT Ano, {_group_col}, codigo_ibge, MAX(populacao) as populacao, SUM(valor_transferido) as valor_transferido
            FROM dados 
            {_where_clause}
            GROUP BY Ano, {_group_col}, codigo_ibge
        )
        GROUP BY Ano, {_group_col} 
        ORDER BY Ano
    """
    ts_df = con.execute(_ts_query, _params_ts).df()
    ts_df['Ano'] = ts_df['Ano'].astype(int)

    if filtro_inflacao.value:
        fatores_inflacao = {
            2014: 1.8235, 2015: 1.6477, 2016: 1.5502, 2017: 1.5058,
            2018: 1.4514, 2019: 1.3914, 2020: 1.3312, 2021: 1.2095,
            2022: 1.1435, 2023: 1.0930, 2024: 1.0426, 2025: 1.0000
        }
        ts_df['fator'] = ts_df['Ano'].map(fatores_inflacao).fillna(1.0)
        ts_df['media_metrica'] = ts_df['media_metrica'] * ts_df['fator']

    _titulo_ts = (
        f'Trajetória Temporal do Valor Total Transferido por {_group_label}'
        if filtro_metrica.value == 'valor'
        else f'Trajetória Temporal da Transferência per capita por {_group_label}'
    )

    fig_ts = px.line(
        ts_df, x='Ano', y='media_metrica', color=_group_col,
        markers=True,
        color_discrete_map=shared_color_map,
        labels={'media_metrica': nome_metrica, 'Ano': 'Ano', _group_col: _group_label},
        title=_titulo_ts
    )
    fig_ts.add_vline(x=filtro_ano.value, line_dash="dot", line_color="#E52207", line_width=2,
                     annotation_text=f" {filtro_ano.value}", annotation_position="top left")
    fig_ts.update_layout(
        template='plotly_white',
        height=450,
        margin=dict(l=0, r=20, t=50, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)', dtick=1),
        yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)')
    )
    mo.output.replace(None)
    return fig_dist_hue, fig_dist_total, fig_rank, fig_ts


@app.cell
def _(df_filtered, mo, nome_metrica):
    cols = ['Ano', 'codigo_ibge', 'municipio', 'sigla_uf', 'regiao',
            'Populacao', 'Total_Transferido', 'Metrica']
    existing_cols = [_c for _c in cols if _c in df_filtered.columns]
    tdf = df_filtered[existing_cols].copy().sort_values('Metrica', ascending=False)

    # Formatação de colunas
    tdf['codigo_ibge'] = tdf['codigo_ibge'].astype(str).str.replace(r'\.0$', '', regex=True)
    tdf['Populacao'] = tdf['Populacao'].round(0).astype('Int64')
    tdf['Total_Transferido'] = tdf['Total_Transferido'].round(2)
    tdf['Metrica'] = tdf['Metrica'].round(2)

    tdf = tdf.rename(columns={
        'codigo_ibge': 'Cód. IBGE', 'municipio': 'Município', 'sigla_uf': 'UF',
        'regiao': 'Região', 'Populacao': 'Pop.',
        'Total_Transferido': 'Total Transferido (R$)',
        'Metrica': nome_metrica
    })
    data_table = mo.ui.table(tdf, selection=None, page_size=20, label="")
    mo.output.replace(None)
    return (data_table,)


@app.cell
def _(df_filtered, df_full, mo):
    # Configuração para padrão brasileiro: sep=';' e decimal=','
    download_csv_filtrado = mo.download(
        data=lambda: df_filtered.to_csv(sep=';', decimal=',', index=False).encode('utf-8-sig'),
        filename="rpc_municipal_filtrado.csv",
        label="⬇️ Baixar Dados Filtrados (CSV)"
    )

    download_csv_completo = mo.download(
        data=lambda: df_full.to_csv(sep=';', decimal=',', index=False).encode('utf-8-sig'),
        filename="rpc_municipal_completo.csv",
        label="⬇️ Baixar Tabela Completa (Série Histórica)"
    )
    return download_csv_completo, download_csv_filtrado


@app.cell
def _(METODOLOGIA_HTML, mo):
    metodologia_content = mo.Html(METODOLOGIA_HTML)
    return (metodologia_content,)


@app.cell
def _(
    data_table,
    download_csv_completo,
    download_csv_filtrado,
    fig_dist_hue,
    fig_dist_total,
    fig_map,
    fig_rank,
    fig_ts,
    filtro_ano,
    filtro_regiao,
    filtro_uf,
    filtro_destino,
    filtro_tipo,
    filtro_linguagem,
    filtro_metrica,
    filtro_inflacao,
    header,
    kpi_html,
    metodologia_content,
    mo,
):
    # Top bar (Header + Filtros) - Custom HTML para garantir responsividade total
    sticky_top = mo.Html(f'''
        <div class="main-header-sticky">
            {header._repr_html_()}
            <div class="responsive-filters" style="display: flex; gap: 10px; flex-wrap: wrap;">
                <div class="filter-item-ano">{filtro_ano._repr_html_()}</div>
                <div class="filter-item">{filtro_regiao._repr_html_()}</div>
                <div class="filter-item">{filtro_uf._repr_html_()}</div>
                <div class="filter-item">{filtro_destino._repr_html_()}</div>
                <div class="filter-item">{filtro_metrica._repr_html_()}</div>
                <div class="filter-item">{filtro_inflacao._repr_html_()}</div>
            </div>
            <div class="responsive-filters" style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                <div class="filter-item" style="flex:1">{filtro_tipo._repr_html_()}</div>
                <div class="filter-item" style="flex:1">{filtro_linguagem._repr_html_()}</div>
            </div>
        </div>
    ''')

    visao_tab = mo.vstack([
            mo.Html('<div class="section-title">Indicadores Resumo</div>'),
            kpi_html,
            mo.Html('<div class="section-title">Mapa Coroplético</div>'),
            fig_map,
            mo.Html('<div class="section-title">Análise Comparativa</div>'),
            mo.vstack([fig_rank, fig_dist_total]),
            mo.vstack([fig_dist_hue, fig_ts])
    ])

    explorador_tab = mo.vstack([
            mo.Html('<div class="section-title">Tabela Analítica</div>'),
            mo.Html('<p style="color:#666;font-size:13px;">Ordenado pela métrica selecionada (decrescente).</p>'),
            mo.hstack([download_csv_filtrado], justify="end"),
            data_table,
            mo.Html('<div class="section-title">Exportação de Dados Completos</div>'),
            mo.Html('<p style="color:#666;font-size:13px;">Baixar a tabela consolidada com todas as transferências e população.</p>'),
            mo.hstack([download_csv_completo], justify="start")
    ])

    tab_content = {
            "📊 Visao Geral": visao_tab,
            "🕵️ Explorador de Dados": explorador_tab,
            "📄 Metodologia": metodologia_content
    }

    layout = mo.vstack([
            sticky_top,
            mo.ui.tabs(tab_content)
    ])
    return (layout,)


@app.cell
def _(layout):
    layout
    return


if __name__ == "__main__":
    app.run()
