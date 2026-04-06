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
                df_total['Estatus operativo'] = 'OPERATIVO'

            # FILTRO: Vencidos Y que NO sean "No Operativo"
            vencidos = df_total[
                (df_total['Estatus de verificación'] == 'VENCIDO') & 
                (df_total['Estatus operativo'] != 'NO OPERATIVO')
            ]
            
            if not vencidos.empty:
                st.error(f"🚨 Se encontraron {len(vencidos)} equipos VENCIDOS en operación.")
                
                # --- LÓGICA DE AGRUPACIÓN (DESGLOSE PISO/MOBILIARIO) ---
                conteo_tipos = vencidos.groupby(['Línea', 'Hoja Origen']).size().unstack(fill_value=0).reset_index()
                
                if 'PISO' not in conteo_tipos.columns: conteo_tipos['PISO'] = 0
                if 'MOBILIARIO' not in conteo_tipos.columns: conteo_tipos['MOBILIARIO'] = 0
                
                conteo_tipos.rename(columns={'PISO': 'Equipos (Piso)', 'MOBILIARIO': 'Mobiliario'}, inplace=True)
                conteo_tipos['Total Vencidos'] = conteo_tipos['Equipos (Piso)'] + conteo_tipos['Mobiliario']
                
                # --- NUEVO FORMATO DE TEXTO (MULTILÍNEA) ---
                # Usamos <br> para forzar el salto de línea entre P y M
                conteo_tipos['Etiqueta'] = "P: " + conteo_tipos['Equipos (Piso)'].astype(str) + "<br>M: " + conteo_tipos['Mobiliario'].astype(str)
                
                # --- GENERACIÓN DEL MAPA ---
                st.markdown("### Mapa de Ubicaciones")
                
                if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                    img = Image.open(RUTA_MAPA)
                    width, height = img.size
                    df_coords = pd.read_csv(RUTA_COORDENADAS)
                    
                    mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
                    
                    if not mapa_data.empty:
                        fig = px.scatter(
                            mapa_data, 
                            x="X", y="Y", 
                            color="Total Vencidos",
                            text="Etiqueta",
                            hover_name="Línea",
                            hover_data={
                                "X": False, 
                                "Y": False, 
                                "Etiqueta": False, 
                                "Total Vencidos": True,
                                "Equipos (Piso)": True,
                                "Mobiliario": True
                            },
                            color_continuous_scale="Reds"
                        )
                        
                        # --- NUEVO FORMATO DE MARCADOR (CUADRADO) ---
                        fig.update_traces(
                            textposition='middle center', 
                            textfont=dict(color='white', size=9, weight='bold'),
                            marker=dict(
                                symbol='square', # Esto cambia la forma a un cuadrado
                                size=40,         # Tamaño del cuadrado
                                opacity=0.9, 
                                line=dict(width=2, color='DarkSlateGrey')
                            )
                        )
                        
                        fig.update_layout(
                            images=[dict(
                                source=img, xref="x", yref="y", x=0, y=0,
                                sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below"
                            )],
                            xaxis=dict(showgrid=False, zeroline=False, range=[0, width], visible=False),
                            yaxis=dict(
                                showgrid=False, zeroline=False, range=[height, 0], visible=False,
                                scaleanchor="x", scaleratio=1
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
