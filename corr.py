import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text
import sqlalchemy
import joblib
import unicodedata 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Comercialización de Unidades", layout="wide", initial_sidebar_state="expanded")

# --- PALETA DE COLORES CORPORATIVA ---
COLOR_VINO = "#5C1212"
COLOR_VINO_LIGHT = "#912828"
COLOR_GRIS_OSCURO = "#333333"
COLOR_GRIS_CLARO = "#CCCCCC"
PALETA_CORPORATIVA = [COLOR_VINO, "#7A1818", "#993333", "#4D4D4D", "#808080", "#B3B3B3"]

# --- CSS PERSONALIZADO ---
st.markdown(f"""
<style>
@import url('https://fonts.com/css2?family=Roboto:wght@300;400;700&display=swap');
:root {{
    --primary-color: {COLOR_VINO};
    --secondary-color: {COLOR_VINO_LIGHT};
    --sidebar-bg-color: #212529;
    --app-bg-color: #f4f4f9;
    --white: #ffffff;
}}
body {{ font-family: 'Roboto', sans-serif; background-color: var(--app-bg-color); }}

/* Banner Styling */
.title-banner {{ 
    background-color: var(--primary-color); 
    color: var(--white); 
    font-size: 2.2em; 
    font-weight: bold; 
    padding: 20px; 
    text-align: center; 
    border-radius: 0 0 15px 15px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    margin-bottom: 25px; 
}}

/* Sidebar Styling */
[data-testid="stSidebar"] {{ background-color: var(--sidebar-bg-color); border-right: 3px solid var(--primary-color); }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label {{ color: var(--white); }}
[data-testid="stSidebar"] .stSelectbox > div, [data-testid="stSidebar"] .stMultiSelect > div, [data-testid="stSidebar"] .stTextInput > div {{ background-color: #343a3a; color: var(--white); }}

/* Metrics */
[data-testid="stMetricValue"] {{ font-size: 1.6rem !important; color: var(--primary-color); font-weight: bold; }}

/* Expander Styling */
.streamlit-expanderHeader {{
    font-weight: bold;
    color: {COLOR_VINO};
    background-color: #e9ecef;
    border-radius: 5px;
}}

/* Table Styling Profesional */
table {{ border-collapse: collapse; width: 100%; border-radius: 5px; overflow: hidden; font-family: 'Roboto', sans-serif; font-size: 0.9em; }}
th {{ background-color: #4a4a4a; color: white; padding: 10px; text-align: center; font-weight: bold; border: 1px solid #ddd; }}
td {{ border: 1px solid #ccc; padding: 8px; text-align: center; background-color: white; color: #333; }}
tr:nth-child(even) td {{ background-color: #f8f9fa; }}
tr:hover td {{ background-color: #e2e6ea; }}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
if "cliente_autenticado" not in st.session_state:
    st.session_state.cliente_autenticado = None

def normalize_text(s):
    if s is None: return ""
    s = str(s).lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# --- CARGA DE RECURSOS ---
@st.cache_resource
def cargar_recursos():
    try:
        opciones_filtros = joblib.load('opciones_filtros.joblib')
    except FileNotFoundError:
        opciones_filtros = {'clientes': [], 'clas_venta': [], 'condiciones': [], 'clas_modelo': [], 'origen_marca': [], 'combustibles': []}

    if "postgres" not in st.secrets or "db_url" not in st.secrets["postgres"]:
        DATABASE_URL = "sqlite:///:memory:" 
    else:
        DATABASE_URL = st.secrets["postgres"]["db_url"].replace("postgresql://", "postgresql+psycopg2://")
    
    engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
    return engine, opciones_filtros

engine, opciones_filtros = cargar_recursos()

@st.cache_data(ttl="1h")
def obtener_datos(_engine, query, params=None):
    with _engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn, params=params)
        if 'FECHA_DE_PAGO' in df.columns:
            df['FECHA_DE_PAGO'] = pd.to_datetime(df['FECHA_DE_PAGO'], errors='coerce')
        return df

# --- INTERFAZ PRINCIPAL ---
st.markdown('<div class="title-banner">Comercialización de Unidades</div>', unsafe_allow_html=True)

# --- SIDEBAR & SEGURIDAD ---
st.sidebar.image("https://tse1.mm.bing.net/th/id/OIP.dZs9yNpJVa2kZjoE9rx54gAAAA?cb=12&rs=1&pid=ImgDetMain&o=7&rm=3", width=200)

# 1. Cliente Auth
grupo_sel = st.sidebar.selectbox("Cliente", ["TODOS"] + opciones_filtros['clientes'])
acceso_permitido = False
if grupo_sel == "TODOS":
    st.session_state.cliente_autenticado = None
    acceso_permitido = True
else:
    if st.session_state.get("cliente_autenticado") == grupo_sel:
        st.sidebar.success(f"Autenticado: {grupo_sel}")
        acceso_permitido = True
    else:
        pwd = st.sidebar.text_input("Código de acceso:", type="password")
        if st.sidebar.button("Verificar"):
            codes = {normalize_text(k): v for k, v in st.secrets.get("client_codes", {}).items()}
            if codes.get(normalize_text(grupo_sel)) == pwd:
                st.session_state.cliente_autenticado = grupo_sel
                acceso_permitido = True
                st.rerun()
            else:
                st.sidebar.error("Código incorrecto")

if not acceso_permitido:
    st.warning("Por favor ingrese el código de cliente en la barra lateral.")
    st.stop()

st.sidebar.divider()
st.sidebar.header("Filtros Globales")

# 2. Filtros solicitados
meses_dict = {0: "Todos", 1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
mes_sel = st.sidebar.selectbox("Mes de Subasta", list(meses_dict.values()))
mes_num = [k for k, v in meses_dict.items() if v == mes_sel][0]

condicion_sel = st.sidebar.selectbox("Condición de Venta", ["TODOS"] + opciones_filtros.get('condiciones', []))
combustible_sel = st.sidebar.selectbox("Combustible", ["TODOS"] + opciones_filtros.get('combustibles', []))
origen_marca_sel = st.sidebar.selectbox("Marca China", ["TODOS"] + opciones_filtros.get('origen_marca', []))

segmento_sel = st.sidebar.selectbox("Segmento", ["TODOS", "Salvamentos", "Seminuevos"])

# --- QUERY PRINCIPAL ---
base_query = """
SELECT 
    "CLIENTE", "SEGMENTO", "FECHA_DE_PAGO", "CANTIDAD_OFERTADA", "PRECIO_RESERVA", 
    "COSTO_CLIENTE", "PRECIO_DE_MERCADO", "DIAS_HABILES_VENTA", "NUMERO_DE_OFERTAS", 
    "RECUPERACION_PRECIO", "RECUPERACION_VALOR", "MARCA", "MODELO", 
    "CLASIFICACION_VENTA", "CONDICION_DE_VENTA", "CLASIFICACION_MODELO", 
    "ORIGEN_MARCA", "COMBUSTIBLE"
FROM ventas_historicas 
WHERE 1=1
"""
params = {}

if grupo_sel != "TODOS":
    base_query += ' AND "CLIENTE" = :cliente'
    params['cliente'] = grupo_sel
if condicion_sel != "TODOS":
    base_query += ' AND "CONDICION_DE_VENTA" = :cond'
    params['cond'] = condicion_sel
if combustible_sel != "TODOS":
    base_query += ' AND "COMBUSTIBLE" = :comb'
    params['comb'] = combustible_sel
if origen_marca_sel != "TODOS":
    base_query += ' AND "ORIGEN_MARCA" = :orig'
    params['orig'] = origen_marca_sel
if segmento_sel != "TODOS":
    base_query += ' AND "SEGMENTO" ILIKE :seg'
    params['seg'] = segmento_sel
if mes_num != 0:
    base_query += ' AND EXTRACT(MONTH FROM "FECHA_DE_PAGO") = :mes'
    params['mes'] = mes_num

# Carga de datos
try:
    df_main = obtener_datos(engine, base_query, params)
    
    numeric_cols = ['COSTO_CLIENTE', 'CANTIDAD_OFERTADA', 'PRECIO_DE_MERCADO', 'DIAS_HABILES_VENTA', 'RECUPERACION_PRECIO', 'RECUPERACION_VALOR']
    for col in numeric_cols:
        df_main[col] = pd.to_numeric(df_main[col], errors='coerce').fillna(0)
    
    df_main['AÑO'] = df_main['FECHA_DE_PAGO'].dt.year
    df_main['MES_NUM'] = df_main['FECHA_DE_PAGO'].dt.month

    # Estandarizar Clasificación Modelo
    def clean_tipo(t):
        t = str(t).upper()
        if 'MOTO' in t: return 'MOTOS'
        if any(x in t for x in ['AUTO', 'SEDAN', 'SUV', 'PICKUP', 'VAN', 'CAMIONETA']): return 'AUTOS'
        if any(x in t for x in ['EP', 'PESADO', 'CAMION', 'TRACTO', 'MAQUINARIA']): return 'EP'
        return 'OTROS'
    
    df_main['TIPO_UNIDAD'] = df_main['CLASIFICACION_MODELO'].apply(clean_tipo)

    if df_main.empty:
        st.warning("No se encontraron datos con los filtros seleccionados.")
        st.stop()
        
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# --- DEFINICIÓN DE PESTAÑAS ---
tab1, tab2 = st.tabs(["📊 Comercializadas Anual", "🏗️ Estrategia de Corralones"])

# ==============================================================================
# TAB 1: COMERCIALIZADAS ANUAL (MEJORADO)
# ==============================================================================
with tab1:
    st.subheader("Resumen Anual de Comercialización")
    
    tipos_disponibles = ["TODOS"] + sorted(df_main['CLASIFICACION_MODELO'].dropna().unique().tolist())
    tipo_unidad_sel = st.selectbox("Filtrar por Tipo de Unidad:", tipos_disponibles)
    
    df_anual = df_main.copy()
    if tipo_unidad_sel != "TODOS":
        df_anual = df_anual[df_anual['CLASIFICACION_MODELO'] == tipo_unidad_sel]

    if df_anual.empty:
        st.info("Sin datos para este tipo de unidad.")
    else:
        # --- TABLA DE RESUMEN ---
        grouped = df_anual.groupby('AÑO')
        resumen_data = []
        for year, group in grouped:
            resumen_data.append({
                'AÑO': year,
                'Unidades': len(group),
                'Monto de Ventas': group['CANTIDAD_OFERTADA'].sum(),
                'Precio Medio Venta': group['CANTIDAD_OFERTADA'].mean(),
                'Costo Cliente': group['COSTO_CLIENTE'].sum(),
                'Costo Promedio': group['COSTO_CLIENTE'].mean(),
                'Precio de Mercado': group['PRECIO_DE_MERCADO'].sum(),
                'Precio Medio Mercado': group['PRECIO_DE_MERCADO'].mean(),
                '% REC VS CC': group['RECUPERACION_PRECIO'].mean(),
                '% REC VS EBC': group['RECUPERACION_VALOR'].mean()
            })
            
        df_display = pd.DataFrame(resumen_data).sort_values('AÑO', ascending=False).set_index('AÑO')
        
        # Calcular Totales
        total_row = {
            'Unidades': df_display['Unidades'].sum(),
            'Monto de Ventas': df_display['Monto de Ventas'].sum(),
            'Precio Medio Venta': df_anual['CANTIDAD_OFERTADA'].mean(),
            'Costo Cliente': df_display['Costo Cliente'].sum(),
            'Costo Promedio': df_anual['COSTO_CLIENTE'].mean(),
            'Precio de Mercado': df_display['Precio de Mercado'].sum(),
            'Precio Medio Mercado': df_anual['PRECIO_DE_MERCADO'].mean(),
            '% REC VS CC': df_anual['RECUPERACION_PRECIO'].mean(),
            '% REC VS EBC': df_anual['RECUPERACION_VALOR'].mean()
        }
        
        # Render Tabla HTML
        html = '<table style="width:100%; font-size:13px; margin-bottom: 20px;">'
        cols = ['Unidades', 'Monto de Ventas', 'Precio Medio Venta', 'Costo Cliente', 'Costo Promedio', 
                'Precio de Mercado', 'Precio Medio Mercado', '% REC VS CC', '% REC VS EBC']
        html += '<tr style="background-color:#4a4a4a; color:white;"><th>AÑO</th>'
        for c in cols: html += f'<th>{c.upper()}</th>'
        html += '</tr>'
        for year, row in df_display.iterrows():
            html += '<tr>'
            html += f'<td style="font-weight:bold;">{year}</td>'
            for col in cols:
                val = row[col]
                if col == 'Unidades': fmt = f"{val:,.0f}"
                elif '%' in col: fmt = f"{val:.1f}%"
                else: fmt = f"$ {val:,.0f}"
                html += f'<td>{fmt}</td>'
            html += '</tr>'
        html += '<tr style="font-weight:bold; background-color:#e0e0e0;"><td>TOTAL</td>'
        for col in cols:
            val = total_row[col]
            if col == 'Unidades': fmt = f"{val:,.0f}"
            elif '%' in col: fmt = f"{val:.1f}%"
            else: fmt = f"$ {val:,.0f}"
            html += f'<td>{fmt}</td>'
        html += '</tr></table>'
        st.markdown(html, unsafe_allow_html=True)

        # --- SECCIÓN ANALYTICS AVANZADO ---
        st.markdown("#### 📊 Análisis de Tendencias y Desempeño")
        
        c1, c2 = st.columns(2)
        with c1:
            # 1. Vol vs Precio
            fig_mix = make_subplots(specs=[[{"secondary_y": True}]])
            fig_mix.add_trace(go.Bar(x=df_display.index, y=df_display['Unidades'], name='Unidades', marker_color=COLOR_VINO), secondary_y=False)
            fig_mix.add_trace(go.Scatter(x=df_display.index, y=df_display['Precio Medio Venta'], name='Precio Medio ($)', mode='lines+markers', line=dict(color='black', width=3)), secondary_y=True)
            fig_mix.update_layout(title="<b>Volumen vs Precio Medio</b>", template="plotly_white", legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_mix, use_container_width=True, key="anual_mix")
            
            # 2. Top Marcas
            df_brands = df_anual.groupby('MARCA')['CANTIDAD_OFERTADA'].sum().reset_index().sort_values('CANTIDAD_OFERTADA', ascending=False).head(10)
            fig_brands = px.bar(df_brands, x='CANTIDAD_OFERTADA', y='MARCA', orientation='h', 
                                title="<b>Top 10 Marcas por Monto de Venta</b>",
                                color_discrete_sequence=[COLOR_VINO])
            fig_brands.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_brands, use_container_width=True, key="anual_brands")

        with c2:
            # 3. Heatmap Estacionalidad
            pivot_mes = df_anual.pivot_table(index='AÑO', columns='MES_NUM', values='CANTIDAD_OFERTADA', aggfunc='count').fillna(0)
            # Mapear numeros a nombres meses
            mes_map = {1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'}
            pivot_mes.columns = [mes_map.get(c,c) for c in pivot_mes.columns]
            
            fig_heat = px.imshow(pivot_mes, text_auto=True, color_continuous_scale='Reds', title="<b>Estacionalidad (Unidades Vendidas)</b>")
            fig_heat.update_layout(xaxis_title="Mes", yaxis_title="Año")
            st.plotly_chart(fig_heat, use_container_width=True, key="anual_heat")

            # 4. Scatter Precio vs Recuperación
            # Muestrear si hay muchos datos para no saturar
            df_sample = df_anual if len(df_anual) < 2000 else df_anual.sample(2000)
            fig_scat = px.scatter(df_sample, x='PRECIO_DE_MERCADO', y='RECUPERACION_PRECIO', color='TIPO_UNIDAD',
                                  title="<b>Dispersión: Valor Mercado vs % Recuperación</b>",
                                  labels={'PRECIO_DE_MERCADO': 'Valor Mercado ($)', 'RECUPERACION_PRECIO': '% Recup.'},
                                  color_discrete_sequence=PALETA_CORPORATIVA)
            fig_scat.update_layout(xaxis_type="log") # Log scale ayuda a ver mejor precios dispares
            st.plotly_chart(fig_scat, use_container_width=True, key="anual_scat")


# ==============================================================================
# TAB 2: ESTRATEGIA DE CORRALONES (DISEÑO FORMAL & EXPANDERS)
# ==============================================================================
with tab2:
    st.subheader("Análisis de Antigüedad de Inventario")

    # --- LÓGICA DE DATOS ---
    def asignar_rango(dias):
        if dias < 90: return '<90'
        elif dias <= 180: return '90 - 180'
        elif dias <= 270: return '180 - 270'
        elif dias <= 360: return '270 - 360'
        elif dias <= 720: return '360 - 720'
        else: return '>720'
    
    order_rangos = ['<90', '90 - 180', '180 - 270', '270 - 360', '360 - 720', '>720']
    
    df_corralon = df_main.copy()
    df_corralon['Rango_Dias'] = df_corralon['DIAS_HABILES_VENTA'].apply(asignar_rango)
    
    # Datasets
    data_sin_chatarra = df_corralon[df_corralon['COSTO_CLIENTE'] >= 102]
    data_solo_chatarra = df_corralon[df_corralon['COSTO_CLIENTE'] < 102]
    data_general = df_corralon
    
    datasets_info = {
        "Sin Chatarra": data_sin_chatarra,
        "Solo Chatarra": data_solo_chatarra,
        "Base General": data_general
    }

    # ==========================================
    # SECCIÓN 1: MATRIZ EJECUTIVA Y KPIS
    # ==========================================
    st.markdown("### 📋 Resumen Ejecutivo y Matrices")
    
    # Contenedor gris claro para diferenciar la zona de datos
    with st.container():
        st.markdown('<div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border:1px solid #ddd;">', unsafe_allow_html=True)
        
        # Tabs para las tablas
        tab_sin, tab_con, tab_gen = st.tabs(["🔹 Sin Chatarra", "🔸 Solo Chatarra", "🌐 Base General"])
        
        def render_kpi_table(df_in, key_suffix):
            if df_in.empty:
                st.warning("Sin datos disponibles.")
                return

            # KPIs Superiores
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Unidades", f"{len(df_in):,.0f}")
            k2.metric("Promedio Días", f"{df_in['DIAS_HABILES_VENTA'].mean():.0f}")
            k3.metric("Costo Inv. Total", f"${df_in['COSTO_CLIENTE'].sum()/1e6:.1f}M")
            k4.metric("Precio Reserva Prom", f"${df_in['PRECIO_RESERVA'].mean():,.0f}")
            
            st.divider()
            
            # Pivot Matrix
            pivot = pd.crosstab(df_in['Rango_Dias'], df_in['TIPO_UNIDAD'])
            pivot = pivot.reindex(order_rangos).fillna(0)
            pivot['TOTAL'] = pivot.sum(axis=1)
            pivot.loc['Total General'] = pivot.sum()
            
            # % Total Global
            total_global = pivot.loc['Total General', 'TOTAL']
            pivot['% Part.'] = (pivot['TOTAL'] / total_global * 100).fillna(0)

            # Render Table
            try:
                # Estilo formal con gradiente rojo
                st.dataframe(
                    pivot.style
                    .background_gradient(cmap="Reds", axis=0, subset=pivot.columns[:-1])
                    .format("{:,.0f}", subset=pivot.columns[:-1])
                    .format("{:.1f}%", subset=['% Part.']),
                    width="stretch" # Ocupa todo el ancho
                )
            except:
                st.dataframe(pivot, width="stretch")
        
        with tab_sin: render_kpi_table(data_sin_chatarra, "sin")
        with tab_con: render_kpi_table(data_solo_chatarra, "con")
        with tab_gen: render_kpi_table(data_general, "gen")

        st.markdown('</div>', unsafe_allow_html=True)

    st.write("") # Espacio
    
    # ==========================================
    # SECCIÓN 2: ANÁLISIS VISUAL (DESPLEGABLES)
    # ==========================================
    st.markdown("### 📈 Análisis Gráfico Detallado")
    st.caption("Haga clic en las secciones para desplegar los gráficos correspondientes.")

    def render_graficos_expander(titulo_expander, df_data, unique_key):
        with st.expander(f"{titulo_expander}", expanded=False):
            if df_data.empty:
                st.warning("No hay datos para graficar.")
                return
            
            g1, g2 = st.columns(2)
            
            with g1:
                # 1. Antiguedad Temporal
                df_agg = df_data.groupby(['AÑO', 'Rango_Dias']).size().reset_index(name='Unidades')
                fig_bar = px.bar(df_agg, x='AÑO', y='Unidades', color='Rango_Dias', 
                            title="Evolución de Antigüedad por Año",
                            category_orders={"Rango_Dias": order_rangos},
                            color_discrete_sequence=px.colors.sequential.Reds_r) # Color Vino/Rojo
                fig_bar.update_layout(template="plotly_white", height=350)
                st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{unique_key}")
                
                # 3. Box Plot Dias Venta
                fig_box = px.box(df_data, x='TIPO_UNIDAD', y='DIAS_HABILES_VENTA', 
                                 title="Distribución Días Venta (Detectar Atípicos)",
                                 color_discrete_sequence=[COLOR_VINO])
                fig_box.update_layout(template="plotly_white", height=350)
                st.plotly_chart(fig_box, use_container_width=True, key=f"box_{unique_key}")

            with g2:
                # 2. Treemap Marcas Retrasadas
                df_retraso = df_data[df_data['DIAS_HABILES_VENTA'] > 180]
                if not df_retraso.empty:
                    # Agrupar marcas pequeñas
                    top_m = df_retraso['MARCA'].value_counts().head(8).index
                    df_retraso.loc[~df_retraso['MARCA'].isin(top_m), 'MARCA'] = 'OTROS'
                    
                    fig_tree = px.treemap(df_retraso, path=['TIPO_UNIDAD', 'MARCA'], 
                                          title="Concentración de Inventario > 180 Días",
                                          color_discrete_sequence=PALETA_CORPORATIVA)
                    fig_tree.update_layout(height=350)
                    st.plotly_chart(fig_tree, use_container_width=True, key=f"tree_{unique_key}")
                else:
                    st.info("Excelente: No hay unidades con más de 180 días.")

                # 4. Sunburst Jerarquía
                fig_sun = px.sunburst(df_data, path=['TIPO_UNIDAD', 'Rango_Dias'], 
                                      title="Composición: Tipo > Rango",
                                      color_discrete_sequence=PALETA_CORPORATIVA)
                fig_sun.update_layout(height=350)
                st.plotly_chart(fig_sun, use_container_width=True, key=f"sun_{unique_key}")

    # Renderizar los 3 expanders
    render_graficos_expander("📊 1. ANÁLISIS: SIN CHATARRA (Unidades de valor)", data_sin_chatarra, "sch")
    render_graficos_expander("📊 2. ANÁLISIS: SOLO CHATARRA (Unidades bajo costo)", data_solo_chatarra, "ch")
    render_graficos_expander("📊 3. ANÁLISIS: GENERAL (Visión Global)", data_general, "gen")
