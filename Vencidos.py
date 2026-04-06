import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os

st.set_page_config(page_title="Gestor de Equipos Vencidos", layout="wide")

st.title("Reporte y Mapa de Equipos Vencidos")
st.markdown("Sube tu archivo Excel para ver el listado y la ubicación en el mapa de los equipos **VENCIDOS** (excluyendo los No Operativos).")

# --- ARCHIVOS ESTÁTICOS ---
# Cambia estos nombres si tus archivos se llaman diferente
RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# 1. Componente para subir el archivo de datos (el que cambia en cada uso)
uploaded_file = st.file_uploader("Sube el archivo Excel (Ej. BCS ESD IDS.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        with st.spinner("Procesando datos y generando mapa..."):
            
            # --- PROCESAMIENTO DE DATOS ---
            df_piso = pd.read_excel(uploaded_file, sheet_name="PISO", header=4)
            df_piso['Hoja Origen'] = 'PISO'
            
            df_mob = pd.read_excel(uploaded_file, sheet_name="MOBILIARIO", header=4)
            df_mob['Hoja Origen'] = 'MOBILIARIO'
            
            df_total = pd.concat([df_piso, df_mob], ignore_index=True)
            
            # Limpieza de estatus para evitar errores tipográficos
            df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
            
            if 'Estatus operativo' in df_total.columns:
                df_total['Estatus operativo'] = df_total['Estatus operativo'].astype(str).str.strip().str.upper()
            else:
                # Si no existe la columna, creamos una vacía para que no falle el filtro
                df_total['Estatus operativo'] = 'OPERATIVO'

            # FILTRO: Vencidos Y que NO sean "No Operativo"
            vencidos = df_total[
                (df_total['Estatus de verificación'] == 'VENCIDO') & 
                (df_total['Estatus operativo'] != 'NO OPERATIVO')
            ]
            
            if not vencidos.empty:
                st.error(f"🚨 Se encontraron {len(vencidos)} equipos VENCIDOS en operación.")
                
                # Agrupar por línea para contar cuántos vencidos hay en cada una
                conteo_lineas = vencidos.groupby('Línea').size().reset_index(name='Cantidad Vencidos')
                
                # --- GENERACIÓN DEL MAPA ---
                st.markdown("### Mapa de Ubicaciones")
                
                if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                    # Cargar imagen y coordenadas
                    img = Image.open(RUTA_MAPA)
                    width, height = img.size
                    df_coords = pd.read_csv(RUTA_COORDENADAS)
                    
                    # Unir el conteo de vencidos con sus coordenadas (X, Y)
                    mapa_data = pd.merge(conteo_lineas, df_coords, on='Línea', how='inner')
                    
                    if not mapa_data.empty:
                        # Crear gráfico sobre la imagen
                        fig = px.scatter(
                            mapa_data, 
                            x="X", y="Y", 
                            size="Cantidad Vencidos", 
                            color="Cantidad Vencidos",
                            hover_name="Línea",
                            text="Cantidad Vencidos",
                            color_continuous_scale="Reds"
                        )
                        
                        # Estilizar los círculos (texto al centro, tamaño, etc.)
                        fig.update_traces(
                            textposition='middle center', 
                            textfont=dict(color='white', size=14, weight='bold'),
                            marker=dict(opacity=0.85, line=dict(width=2, color='DarkSlateGrey'))
                        )
                        
                        # Colocar la imagen de fondo y ajustar ejes
                        fig.update_layout(
                            images=[dict(
                                source=img,
                                xref="x", yref="y",
                                x=0, y=0,
                                sizex=width, sizey=height,
                                sizing="stretch", # Se mantiene stretch, pero los ejes ya están bloqueados
                                opacity=1,
                                layer="below"
                            )],
                            # Configuración del eje X
                            xaxis=dict(
                                showgrid=False, zeroline=False, 
                                range=[0, width], visible=False
                            ),
                            # Configuración del eje Y (Aquí está la magia para la proporción real)
                            yaxis=dict(
                                showgrid=False, zeroline=False, 
                                range=[height, 0], visible=False,
                                scaleanchor="x", # Ancla la escala al eje X
                                scaleratio=1     # Fuerza la proporción 1:1
                            ),
                            margin=dict(l=0, r=0, t=0, b=0),
                            coloraxis_showscale=False
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No se encontraron coincidencias entre las líneas vencidas y el archivo de coordenadas.")
                else:
                    st.info(f"📌 Para ver el mapa, asegúrate de colocar '{RUTA_MAPA}' y '{RUTA_COORDENADAS}' en la misma carpeta que este script.")
                
                # --- TABLA DE DATOS ---
                st.markdown("### Detalles de Equipos")
                columnas_mostrar = ['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación', 'Estatus operativo', 'Hoja Origen']
                columnas_mostrar = [col for col in columnas_mostrar if col in vencidos.columns]
                
                df_mostrar = vencidos[columnas_mostrar]
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                
            else:
                st.success("✅ ¡Felicidades! No hay equipos operativos con estatus 'VENCIDO'.")
                
    except Exception as e:
        st.error(f"Ocurrió un error inesperado al procesar los datos: {e}")