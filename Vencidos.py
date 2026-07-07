import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import base64
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import streamlit.components.v1 as components
import fitz  # PyMuPDF
import re
import io
import pytesseract
from supabase import create_client, Client
import time
from werkzeug.security import generate_password_hash, check_password_hash
import plotly.graph_objects as go

if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Mapa" # O la vista principal que uses por defecto

if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None

if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

if "rol_usuario" not in st.session_state:
    st.session_state.rol_usuario = None

# Agrega aquí cualquier otra llave que uses (ej. val_form_key)
if "val_form_key" not in st.session_state:
    st.session_state.val_form_key = 0

# Configuración de página
st.set_page_config(page_title="Control ESD BCS-AIS", layout="wide")

# ==========================================
# DICCIONARIOS GLOBALES DE REFERENCIA
# ==========================================
INFO_ELEMENTOS_ESD = {
    "Pulsera antiestática": {"limite": "RS < 3.5x10^7 ohms", "ref_num": 3.5e7, "tipo_material": "Banda elástica / Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Calzado": {"limite": "RS < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Suela disipativa / Talón", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Piso ESD": {"limite": "RTG < 1.0x10^9 ohms / Walking Test < 100V", "ref_num": 1.0e9, "tipo_material": "Epóxico / Vinílico ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53 / ANSI/ESD 97.2", "frecuencia": "Semestralmente"},
    "Superficie de trabajo": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tapete disipativo / Mesa", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Anualmente"},
    "Monitor Continuo": {"limite": "RTG < 2 ohms", "ref_num": 2.0, "tipo_material": "Equipo Electrónico", "magnitud": "Resistencia", "metodo": "Anexo A.1", "frecuencia": "Trimestralmente"},
    "Ionizador": {"limite": "Descarga: <10s, Bal: +-35V", "ref_num": 10.0, "tipo_material": "Ventilador / Barra", "magnitud": "Tiempo", "metodo": "ANSI/ESD SP3.3-2016", "frecuencia": "Trimestralmente"},
    "Bolsa disipativa": {"limite": "RS < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Plástico disipativo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Semestralmente"},
    "Cautín / Estación de soldar": {"limite": "RTG < 10 ohms", "ref_num": 10.0, "tipo_material": "Metal / Punta", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Caja Disipativa": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Plástico / Cartón", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Anualmente"},
    "Caja conductiva": {"limite": "RS < 1.0x10^4 ohms", "ref_num": 1.0e4, "tipo_material": "Plástico conductivo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Anualmente"},
    "Charola conductiva": {"limite": "RS < 1.0x10^4 ohms", "ref_num": 1.0e4, "tipo_material": "Plástico conductivo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Charola Disipativa": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Plástico disipativo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Magazine": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Metal / Plástico", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Bata": {"limite": "RPP < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Gorra": {"limite": "RPP < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Rack": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM4.1", "frecuencia": "Anualmente"},
    "Carrito": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM4.1", "frecuencia": "Anualmente"},
    "Silla ESD": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tela / Vinil ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Guantes Nitrilo": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Nitrilo", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Guantes Tela": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Tapete de piso": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Caucho / Vinil ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Aislantes - EPA (General)": {"limite": ">30 cm de ESDS", "ref_num": 2000.0, "tipo_material": "Material Aislante", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Aislantes - Conductores Aislados": {"limite": "< 35 Volts", "ref_num": 35.0, "tipo_material": "Conductor Aislado", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Aislantes - Contacto directo": {"limite": "<= 125 Volts/in", "ref_num": 125.0, "tipo_material": "Material Aislante", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Bolsas blindadas": {"limite": "Visual", "ref_num": 0.0, "tipo_material": "Plástico metalizado", "magnitud": "Otro", "metodo": "Inspección visual", "frecuencia": "Trimestralmente"}
}

MAPA_UNIDADES = {
    "Resistencia": "Ohms",
    "Voltaje": "Volts",
    "Tiempo": "Segundos",
    "Longitud": "cm",
    "Otro": "N/A"
}

def parsear_resistencia(valor_str):
    """Convierte texto libre a float soportando notación científica y comas."""
    if not valor_str or str(valor_str).strip() == "":
        return None
    try:
        # Limpiamos espacios y cambiamos la coma por punto (por si usan teclado en español)
        val_limpio = str(valor_str).strip().replace(',', '.')
        return float(val_limpio)
    except ValueError:
        return "ERROR"

def ejecutar_automigracion_lineas():
    """Extrae líneas únicas de todas las tablas y las inserta en catalogo_lineas."""
    lineas_encontradas = set()

    # 1. Extraer de Validación General
    try:
        resp_val = supabase.table("validacion_esd").select("ubicacion").execute()
        if resp_val.data:
            for reg in resp_val.data:
                linea = str(reg.get("ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e: pass

    # 2. Extraer de Event Meter
    try:
        resp_em = supabase.table("event_meter").select("linea_ubicacion").execute()
        if resp_em.data:
            for reg in resp_em.data:
                linea = str(reg.get("linea_ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e: pass

    # --- NUEVO: 3. Extraer de Inventario ESD (Mobiliario, Ionizadores, etc.) ---
    try:
        resp_inv = supabase.table("inventario_esd").select("linea_ubicacion").execute()
        if resp_inv.data:
            for reg in resp_inv.data:
                linea = str(reg.get("linea_ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e: pass

    # --- NUEVO: 4. Extraer de Maquinaria ---
    try:
        resp_maq = supabase.table("mediciones_maquinaria").select("linea_ubicacion").execute()
        if resp_maq.data:
            for reg in resp_maq.data:
                linea = str(reg.get("linea_ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e: pass

    # 5. Insertar registros en la tabla catálogo maestro (Ignorando los que ya existen)
    nuevos_registros = 0
    for linea_nombre in sorted(lineas_encontradas):
        try:
            supabase.table("catalogo_lineas").insert({"nombre_linea": linea_nombre}).execute()
            nuevos_registros += 1
        except:
            pass # Ya existía (quizás lo agregaste manual), se omite de forma segura.

    return nuevos_registros, len(lineas_encontradas)
    
def obtener_catalogo_lineas():
    """Descarga el catálogo maestro de líneas de Supabase"""
    try:
        resp = supabase.table("catalogo_lineas").select("nombre_linea").order("nombre_linea").execute()
        return [x['nombre_linea'] for x in resp.data] if resp.data else ["Sin Ubicaciones"]
    except:
        return ["Sin Ubicaciones"]
        
def limpiar_id(texto):
    if not texto: return ""
    # Convierte a texto, quita espacios raros, borra espacios al inicio/fin y lo hace mayúscula
    return str(texto).replace('\xa0', ' ').strip().upper()

def generar_html_reporte_calificaciones(df_calif, auditor):
    año_actual = datetime.today().strftime("%y")
    fecha_hoy = datetime.today().strftime("%d-%b-%Y")
    fecha_pie = datetime.today().strftime("%Y/%m/%d")
    
    # Construir las filas de la tabla
    filas_html = ""
    for i, row in enumerate(df_calif.to_dict('records'), 1):
        fecha = str(row.get('Fecha', 'N/D'))
        elemento = str(row.get('Elemento S20.20', 'N/D'))
        id_elem = str(row.get('ID Elemento', 'N/D'))
        notas = str(row.get('Notas', ''))
        if notas.lower() in ['nan', 'none']: notas = ""
        subido_por = str(row.get('Subido por', 'N/D'))
        
        # Extraer el nombre del archivo de la URL original
        url_doc = str(row.get('archivo_url_raw', ''))
        nombre_archivo = url_doc.split('/')[-1].replace('%20', ' ').replace('%28', '(').replace('%29', ')') if '/' in url_doc else 'Reporte_Adjunto.pdf'
        
        filas_html += f"""
        <tr class="text-center border-b border-gray-300 print:border-black">
            <td class="border-r border-gray-300 p-2 print:border-black">{i}</td>
            <td class="border-r border-gray-300 p-2 font-mono print:border-black">{fecha}</td>
            <td class="border-r border-gray-300 p-2 text-left print:border-black">{elemento}</td>
            <td class="border-r border-gray-300 p-2 font-bold text-left print:border-black">{id_elem}</td>
            <td class="border-r border-gray-300 p-2 text-left text-xs text-blue-800 font-mono print:text-black print:border-black">{nombre_archivo}</td>
            <td class="border-r border-gray-300 p-2 text-left text-xs print:border-black">{notas}</td>
            <td class="p-2 text-xs print:border-black">{subido_por}</td>
        </tr>
        """
        
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-RCAL-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@media print {{ body {{ -webkit-print-color-adjust: exact; }} }}</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-6xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm hover:bg-blue-700 transition">🖨️ Imprimir / Guardar PDF</button>
    </div>
    <div class="max-w-6xl mx-auto bg-white shadow-xl print:shadow-none print:w-full print:border print:border-black">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between print:border-black">
            <div class="w-1/4">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-2/4 text-center">
                <h1 class="text-lg font-bold text-gray-800">REPORTE DE ELEMENTOS CALIFICADOS (ESD)</h1>
                <p class="text-xs text-gray-600">Cumplimiento Integral ANSI/ESD S20.20</p>
            </div>
            <div class="w-1/4 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Folio: BCS-RCAL-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Emisión:</span><span>{fecha_hoy}</span>
                </div>
            </div>
        </div>

        <div class="p-6 space-y-6">
            <div>
                <div class="bg-[#003366] text-white font-bold px-2 py-1 uppercase text-xs print:bg-black">Desglose de Elementos con Calificación de Producto (Certificados)</div>
                <table class="w-full text-sm border-collapse border border-gray-300 print:border-black">
                    <tr class="bg-gray-200 border-b border-gray-300 print:bg-transparent print:border-black">
                        <th class="p-2 border-r border-gray-300 print:border-black w-10">No.</th>
                        <th class="p-2 border-r border-gray-300 print:border-black w-24">Fecha Reg.</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">Categoría S20.20</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">ID Elemento</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">Evidencia / Certificado</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">Observaciones</th>
                        <th class="p-2 w-24">Subido por</th>
                    </tr>
                    {filas_html}
                </table>
            </div>

            <div class="mt-16 mb-8 pt-8 [page-break-inside:avoid]">
                <div class="w-1/2 mx-auto text-center border-t-2 border-gray-800 pt-2 print:border-black">
                    <div class="font-bold uppercase text-sm mb-1">EMITIDO POR:</div>
                    <div class="text-center font-bold text-gray-700 print:text-black">{auditor}</div>
                    <div class="text-xs text-gray-500">Coordinador ESD</div>
                </div>
            </div>
            
            <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
                <div class="flex justify-between items-end">
                    <div class="text-left leading-tight">
                        <div>B_010_4_021_QRO_SP Rev. A</div>
                        <div>Registro de eventos ESD.</div>
                    </div>
                    <div class="text-center leading-tight">
                        <div>Fecha: {fecha_pie}</div>
                    </div>
                    <div class="text-right leading-tight">
                        <div>Ref.B_010_3_002_QRO_SP</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html, año_actual

def generar_html_reporte_linea(linea, df_linea, auditor, comentarios, db_id):
    año_actual = datetime.today().strftime("%y")
    fecha_hoy = datetime.today().strftime("%d-%b-%Y")
    fecha_pie = datetime.today().strftime("%Y/%m/%d")
    
    # Construir las filas de la tabla
    filas_html = ""
    for i, row in enumerate(df_linea.to_dict('records'), 1):
        categoria = str(row.get('Categoría', 'N/D'))
        id_elem = str(row.get('ID / Nombre', 'N/D'))
        clasif = str(row.get('Clasificación', 'N/D'))
        ultima_val = str(row.get('Última Medición', 'N/D'))  # <--- SE AGREGA LA FECHA DE VALIDACIÓN
        vencimiento = str(row.get('Próximo Vencimiento', 'N/D'))
        estatus_raw = str(row.get('Estatus', '')).upper()
        
        # Limpiar el emoji del estatus si viene con él
        estatus_limpio = estatus_raw.replace('🟢', '').replace('🔴', '').replace('🟡', '').strip()
        color_txt = "text-green-600" if "VIGENTE" in estatus_limpio or "PASA" in estatus_limpio else ("text-red-600" if "VENCIDO" in estatus_limpio or "FALLA" in estatus_limpio else "text-yellow-600")
        
        filas_html += f"""
        <tr class="text-center border-b border-gray-300 print:border-black">
            <td class="border-r border-gray-300 p-2 print:border-black">{i}</td>
            <td class="border-r border-gray-300 p-2 font-bold text-left print:border-black">{id_elem}</td>
            <td class="border-r border-gray-300 p-2 text-left print:border-black">{categoria} - {clasif}</td>
            <td class="border-r border-gray-300 p-2 font-mono text-gray-700 print:border-black">{ultima_val}</td>
            <td class="border-r border-gray-300 p-2 font-mono print:border-black">{vencimiento}</td>
            <td class="p-2 font-bold {color_txt}">{estatus_limpio}</td>
        </tr>
        """
        
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-LV-{db_id:03d}-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@media print {{ body {{ -webkit-print-color-adjust: exact; }} }}</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm">🖨️ Imprimir / Guardar PDF</button>
    </div>
    <div class="max-w-5xl mx-auto bg-white shadow-xl print:shadow-none print:w-full print:border print:border-black">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between print:border-black">
            <div class="w-1/3">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-1/3 text-center">
                <h1 class="text-lg font-bold text-gray-800">REPORTE DE VALIDACIÓN DE LÍNEA (ESD)</h1>
                <p class="text-xs text-gray-600">Cumplimiento Integral ANSI/ESD S20.20</p>
            </div>
            <div class="w-1/3 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Folio: BCS-LV-{db_id:03d}-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Emisión:</span><span>{fecha_hoy}</span>
                </div>
            </div>
        </div>

        <div class="p-6 space-y-6">
            <div class="bg-gray-100 p-4 border border-gray-300 rounded print:border-black print:bg-transparent">
                <div class="grid grid-cols-2 gap-4">
                    <div><span class="font-bold text-[#003366]">Línea Evaluada:</span> <span class="text-lg font-bold">{linea}</span></div>
                    <div><span class="font-bold text-[#003366]">Auditor Responsable:</span> {auditor}</div>
                </div>
            </div>

            <div>
                <div class="bg-[#003366] text-white font-bold px-2 py-1 uppercase text-xs print:bg-black">Desglose de Activos Operativos en Línea</div>
                <table class="w-full text-sm border-collapse border border-gray-300 print:border-black">
                    <tr class="bg-gray-200 border-b border-gray-300 print:bg-transparent print:border-black">
                        <th class="p-2 border-r border-gray-300 print:border-black w-10">No.</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">ID Elemento</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">Tipo de Equipo</th>
                        <th class="p-2 border-r border-gray-300 print:border-black">Última Validación</th>
                        <th class="p-2 border-r border-gray-300 print:border-black">Próx. Vencimiento</th>
                        <th class="p-2">Estatus Actual</th>
                    </tr>
                    {filas_html}
                </table>
            </div>

            <div class="mt-4 border border-gray-300 p-3 bg-gray-50 print:border-black print:bg-transparent">
                <div class="font-bold text-[#003366] text-xs uppercase mb-1 print:text-black">Comentarios / Observaciones de la Línea:</div>
                <div class="text-sm">{comentarios}</div>
            </div>

            <div class="mt-16 mb-8 pt-8 [page-break-inside:avoid]">
                <div class="w-1/2 mx-auto text-center border-t-2 border-gray-800 pt-2 print:border-black">
                    <div class="font-bold uppercase text-sm mb-1">CERTIFICADO POR:</div>
                    <div class="text-center font-bold text-gray-700 print:text-black">{auditor}</div>
                    <div class="text-xs text-gray-500">Coordinador ESD</div>
                </div>
            </div>
            
            <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
                <div class="flex justify-between items-end">
                    <div class="text-left leading-tight">
                        <div>B_010_4_013_QRO_SP Rev. A</div>
                        <div>Registro de eventos ESD.</div>
                    </div>
                    <div class="text-center leading-tight">
                        <div>Fecha: {fecha_pie}</div>
                    </div>
                    <div class="text-right leading-tight">
                        <div>Ref.B_010_3_002_QRO_SP</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html, año_actual

def generar_html_reporte_completo(row, index):
    """Genera el reporte HTML nativo leyendo las columnas individuales de medición en Supabase."""
    
    def get_sql_val(key, default="N/D"):
        v = row.get(key)
        if pd.isna(v) or v is None:
            return default
        return str(v).strip()

    # 1. Extraer las 5 columnas directamente
    mediciones_raw = [
        get_sql_val('medicion_1', ''),
        get_sql_val('medicion_2', ''),
        get_sql_val('medicion_3', ''),
        get_sql_val('medicion_4', ''),
        get_sql_val('medicion_5', '')
    ]
    
    mediciones = []
    for m in mediciones_raw:
        if m and m.lower() not in ['n/d', 'nan', 'none', 'null', '']:
            mediciones.append(m)
    
    # 2. Calcular promedio
    valid_nums = []
    for m in mediciones:
        try:
            valid_nums.append(float(m))
        except: pass
            
    promedio = sum(valid_nums) / len(valid_nums) if valid_nums else 0
    promedio_str = f"{promedio:.2E}" if promedio > 0 else "N/A"
    
    # Formato de Referencia
    ref_raw = get_sql_val('limite_referencia', '')
    try:
        ref_num = float(ref_raw)
        ref_str = f"{ref_num:.2E}" if ref_num > 1000 or ref_num < 0.01 else str(ref_num)
    except:
        ref_str = ref_raw

    metodo_prueba = get_sql_val('metodo', '')
    unidad_medida = get_sql_val('unidad', '')

    # 3. Generar las filas de la tabla
    html_rows = ""
    for i, val in enumerate(mediciones, 1):
        try:
            val_num = float(val)
            val_str = f"{val_num:.2E}" if val_num > 1000 or val_num < 0.01 else str(val)
        except:
            val_str = str(val)
            
        html_rows += f"""
        <tr class="border-b border-gray-200 hover:bg-blue-50 print:hover:bg-transparent text-center">
            <td class="p-1 border-r border-gray-300 font-bold">{i}</td>
            <td class="p-1 border-r border-gray-300">{ref_str}</td>
            <td class="p-1 border-r border-gray-300">0.0</td>
            <td class="p-1 border-r border-gray-300 bg-yellow-50 print:bg-transparent font-mono font-bold">{val_str}</td>
            <td class="p-1 border-r border-gray-300">{metodo_prueba}</td>
            <td class="p-1 border-r border-gray-300">{unidad_medida}</td>
        </tr>
        """
        
    # 4. Procesar Imagen
    img_url = get_sql_val('imagen_url', '')
    if img_url == 'N/D' or not img_url or img_url.lower() in ['nan', 'none', 'null', 'pendiente de storage']:
        img_tag = "<span class='text-gray-400 flex flex-col items-center'><br><br>Sin evidencia fotográfica</span>"
    else:
        img_tag = f'<img src="{img_url}" style="height: 190px; width: auto; max-width: 100%; object-fit: contain; margin: 0 auto;" />'
        
    # 5. Formatear la fecha
    fecha_raw = get_sql_val('fecha_auditoria', '')
    try:
        dt = datetime.fromisoformat(fecha_raw.split('.')[0])
        meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        fecha_ejecucion = f"{dt.day:02d}-{meses[dt.month-1]}-{dt.year}"
    except:
        fecha_ejecucion = fecha_raw.split('T')[0] if 'T' in fecha_raw else fecha_raw

    año_actual = datetime.today().strftime("%y")
    
    # 6. Extraer variables generales
    elemento = get_sql_val('elemento_s20_20', 'N/D')
    magnitud = INFO_ELEMENTOS_ESD.get(elemento, {}).get("magnitud", "N/D")

    id_elemento = get_sql_val('id_elemento')
    fabricante_elem = get_sql_val('fabricante_elem')
    modelo_elem = get_sql_val('modelo_elem')
    sn_elem = get_sql_val('sn_elem')
    
    temperatura = get_sql_val('temperatura')
    humedad = get_sql_val('humedad')
    ubicacion = get_sql_val('ubicacion')
    
    id_equipo = get_sql_val('id_equipo_utilizado')
    tipo_equipo = get_sql_val('tipo_equipo')
    reporte_cal = get_sql_val('reporte_cal')
    resolucion = get_sql_val('resolucion')
    
    fabricante_eq = get_sql_val('fabricante_eq')
    modelo_eq = get_sql_val('modelo_eq')
    sn_eq = get_sql_val('sn_eq')
    fecha_prox_cal = get_sql_val('fecha_prox_cal')
    
    notas = get_sql_val('notas', 'Sin observaciones adicionales.')
    resultado = get_sql_val('resultado')
    auditor = get_sql_val('auditor')
    
    # Lógica de color para el estatus
    # Lógica de color infalible para el estatus
    res_upper = str(resultado).upper()
    if "NO CUMPLE" in res_upper or "RECHAZADO" in res_upper or "FALLA" in res_upper:
        res_color = "text-red-600"
    else:
        res_color = "text-green-600"

# Generar fecha en formato YYYY/MM/DD para el pie de página
    fecha_pie_str = datetime.today().strftime("%Y/%m/%d")
# --- NUEVO: EXTRAER ID REAL DE LA BASE DE DATOS ---
    db_id = row.get('id', index)
    try:
        db_id = int(db_id)
    except:
        db_id = index
    # --------------------------------------------------
    # --- PLANTILLA HTML ---
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-PV-{db_id:03d}-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @media print {{ body {{ -webkit-print-color-adjust: exact; }} }}
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm">🖨️ Imprimir / Guardar PDF</button>
    </div>
    
    <div class="max-w-5xl mx-auto bg-white shadow-xl print:shadow-none print:w-full">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between">
            <div class="w-1/3">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-1/3 text-center">
                <h1 class="text-lg font-bold text-gray-800">FORMATO DE VALIDACIÓN DE PRODUCTO (ESD)</h1>
                <p class="text-xs text-gray-600">ANSI/ESD S20.20-2021</p>
            </div>
            <div class="w-1/3 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Reporte: BCS-PV-{db_id:03d}-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Ejecución:</span><span>{fecha_ejecucion}</span>
                </div>
            </div>
        </div>

        <div class="p-6 space-y-6">
            <div class="grid grid-cols-2 gap-6">
                <div>
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Datos del Elemento de Control</div>
                    <table class="w-full text-sm border-collapse border border-gray-300">
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">ID:</td><td class="p-1">{id_elemento}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Elemento:</td><td class="p-1">{elemento}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Fabricante:</td><td class="p-1">{fabricante_elem}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Modelo:</td><td class="p-1">{modelo_elem}</td></tr>
                        <tr><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">No. Serie:</td><td class="p-1">{sn_elem}</td></tr>
                    </table>
                </div>
                <div>
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Información General</div>
                    <table class="w-full text-sm border-collapse border border-gray-300 h-full">
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Temperatura:</td><td class="p-1">{temperatura}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Humedad:</td><td class="p-1">{humedad}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Ubicación:</td><td class="p-1">{ubicacion}</td></tr>
                        <tr><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Magnitud:</td><td class="p-1">{magnitud}</td></tr>
                    </table>
                </div>
            </div>

            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Trazabilidad (Equipo de Medición)</div>
                <div class="grid grid-cols-2 border-l border-t border-gray-300">
                    <div class="border-r border-b border-gray-300">
                        <table class="w-full text-sm">
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 w-1/3 border-r border-gray-300">ID:</td><td class="p-1">{id_equipo}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Equipo:</td><td class="p-1">{tipo_equipo}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Reporte Cal.:</td><td class="p-1">{reporte_cal}</td></tr>
                            <tr><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Resolución:</td><td class="p-1">{resolucion}</td></tr>
                        </table>
                    </div>
                    <div class="border-b border-gray-300">
                        <table class="w-full text-sm">
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 w-1/3 border-r border-gray-300">Fabricante:</td><td class="p-1">{fabricante_eq}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Modelo:</td><td class="p-1">{modelo_eq}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">No. Serie:</td><td class="p-1">{sn_eq}</td></tr>
                            <tr><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Vigencia Cal.:</td><td class="p-1">{fecha_prox_cal}</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Resultados (ANSI/ESD S20.20)</div>
                <table class="w-full text-sm border-collapse border border-gray-300 text-center">
                    <tr class="bg-gray-100 border-b border-gray-300">
                        <th class="p-2 border-r border-gray-300">No.</th>
                        <th class="p-2 border-r border-gray-300">Referencia</th>
                        <th class="p-2 border-r border-gray-300">Tolerancia</th>
                        <th class="p-2 border-r border-gray-300">Resultado Obtenido</th>
                        <th class="p-2 border-r border-gray-300">Método de Prueba</th>
                        <th class="p-2 border-r border-gray-300">Unidad</th>
                    </tr>
                    {html_rows}
                    <tr class="border-t-2 border-gray-400 bg-gray-50">
                        <td colspan="3" class="p-2 font-bold text-right border-r border-gray-300">Promedio / Final:</td>
                        <td class="p-2 font-mono font-bold text-center border-r border-gray-300">{promedio_str}</td>
                        <td colspan="2"></td>
                    </tr>
                </table>
            </div>

            <div class="grid grid-cols-2 gap-6 h-64">
                <div class="border border-gray-300 flex flex-col items-center justify-center bg-gray-50 overflow-hidden relative">
                    <div class="absolute top-0 left-0 bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full text-left z-10">Imagen del Producto / Evidencia</div>
                    <div class="mt-8 flex-1 flex items-center justify-center p-2">
                        {img_tag}
                    </div>
                </div>
                <div class="border border-gray-300 flex flex-col relative">
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full">Comentarios / Observaciones</div>
                    <div class="p-2 text-sm">{notas}</div>
                    <div class="absolute bottom-2 right-2 text-xl font-bold {res_color}">{resultado}</div>
                </div>
            </div>

            <div class="mt-12 mb-8 pt-8 [page-break-inside:avoid]">
                <div class="w-1/3 mx-auto text-center border-t border-gray-800 pt-2">
                    <div class="font-bold uppercase text-sm mb-1">APROBADO Y CERTIFICADO POR:</div>
                    <div class="text-center font-bold text-gray-700">{auditor}</div>
                </div>
            </div>
            
            <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
                <div class="flex justify-between items-end">
                    <div class="text-left leading-tight">
                        <div>B_010_4_018_QRO_SP_Rev. A</div>
                        <div>Formato de Validación de producto.</div>
                    </div>
                    <div class="text-center leading-tight">
                        <div>Fecha: Fecha: 08/ago/2025 </div>
                    </div>
                    <div class="text-right leading-tight">
                        <div>Ref.B_010_3_002_QRO_SP</div>
                    </div>
                </div>
            </div>
            
        </div>
    </div>
</body>
</html>"""
    return html
    
# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- NUEVA LECTURA DE DATOS UNIFICADA ---
@st.cache_data(ttl=10) 
def cargar_datos_cloud():
    try:
        resp_inv = supabase.table("inventario_esd").select("*").limit(3000).execute()
        df_inv = pd.DataFrame(resp_inv.data)
        
        if not df_inv.empty:
            rename_map = {
                "id_producto": "Id de producto",
                "linea_ubicacion": "Línea",
                "clasificacion": "Clasificación",
                "fabricante": "Fabricante",
                "limite_minimo": "Mínimo",
                "limite_maximo": "Maximo",
                "unidad_medida": "Unidad",
                "valor_actual": "Valor de verificación",
                "balance_ionizador": "Balance",
                "metodo_prueba": "Método",
                "fecha_ultima_verif": "Fecha de verificación",
                "fecha_proxima_verif": "Fecha de próxima verificación",
                "frecuencia": "Frecuencia de verificación",
                "estatus_verificacion": "Estatus de verificación",
                "estatus_operativo": "Estatus operativo",
                "comentarios": "Notas",
                "auditor_responsable": "Auditor"
            }
            df_inv = df_inv.rename(columns=rename_map)
            df_mob = df_inv[df_inv['categoria'] == 'Mobiliario']
            df_ion = df_inv[df_inv['categoria'] == 'Ionizador']
            df_piso = df_inv[df_inv['categoria'] == 'Piso']
            df_mon = df_inv[df_inv['categoria'] == 'Monitor Continuo']
        else:
            df_mob, df_ion, df_piso = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        resp_em = supabase.table("event_meter").select("*").execute()
        df_em = pd.DataFrame(resp_em.data) if resp_em.data else pd.DataFrame()
        if not df_em.empty:
            em_rename_map = {
                "linea_ubicacion": "Línea",
                "id_operacion": "Id de Operación",
                "tipo_contacto": "Tipo de contacto",
                "cantidad_eventos": "Detección (Cantidad)",
                "voltaje_maximo": "Voltaje máximo",
                "estatus_verificacion": "Estatus de verificación",
                "notas": "Notas",
                "auditor": "Auditor"
            }
            df_em = df_em.rename(columns=em_rename_map)
        else:
            df_em = pd.DataFrame(columns=['Línea', 'Id de Operación'])

        return df_inv, df_piso, df_mob, df_ion, df_mon, df_em
        
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None, None, None, None, None, None


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def codificar_sesion(nombre):
    return base64.b64encode(nombre.encode('utf-8')).decode('utf-8')

def decodificar_sesion(token):
    try:
        return base64.b64decode(token.encode('utf-8')).decode('utf-8')
    except:
        return None

def limpiar_url_escaneo():
    if "qr_id" in st.query_params:
        del st.query_params["qr_id"]
    if "ocr_val" in st.query_params:
        del st.query_params["ocr_val"]
    if "qr_baja" in st.query_params:
        del st.query_params["qr_baja"]

def subir_evidencia_storage(img_file, id_elemento):
    """Sube la imagen a Supabase Storage y retorna la URL pública."""
    if img_file is not None:
        try:
            img = Image.open(img_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((800, 800))
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=75)
            img_bytes = buffered.getvalue()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{id_elemento}_{timestamp}.jpg"
            
            res = supabase.storage.from_("evidencias_esd").upload(
                file=img_bytes,
                path=file_name,
                file_options={"content-type": "image/jpeg"}
            )
            
            url = supabase.storage.from_("evidencias_esd").get_public_url(file_name)
            return url
        except Exception as e:
            st.error(f"Error subiendo imagen a la nube: {e}")
            return ""
    return ""

def subir_reporte_storage(pdf_file, id_elemento):
    """Sube un documento PDF a Supabase Storage y retorna la URL pública."""
    if pdf_file is not None:
        try:
            file_bytes = pdf_file.read()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Reemplazamos espacios por guiones bajos por seguridad en la URL
            id_limpio = str(id_elemento).replace(" ", "_")
            file_name = f"{id_limpio}_{timestamp}.pdf"
            
            res = supabase.storage.from_("reportes_calificacion").upload(
                file=file_bytes,
                path=file_name,
                file_options={"content-type": "application/pdf"}
            )
            
            url = supabase.storage.from_("reportes_calificacion").get_public_url(file_name)
            return url
        except Exception as e:
            st.error(f"Error subiendo archivo PDF a la nube: {e}")
            return ""
    return ""

def safe_str(val, default="N/D"):
    val_str = str(val).strip()
    if pd.isna(val) or val_str.lower() in ['nan', 'none', 'null', '']:
        return default
    return val_str

def generar_html_reporte_esd(row, index):
    """Genera el HTML leyendo los datos de la fila de SQL."""
    med1 = safe_str(row.get('medicion_1', ''), '')
    med_extra = safe_str(row.get('mediciones_extra', ''), '')
    
    mediciones = [med1] if med1 else []
    if med_extra and med_extra != 'N/D':
        mediciones.extend([m.strip() for m in med_extra.split(',') if m.strip()])
    
    valid_nums = []
    for m in mediciones:
        try:
            valid_nums.append(float(m))
        except: pass
            
    promedio = sum(valid_nums) / len(valid_nums) if valid_nums else 0
    promedio_str = f"{promedio:.2E}" if promedio > 0 else "N/A"
    
    ref_raw = safe_str(row.get('limite_referencia'))
    try:
        ref_num = float(ref_raw)
        ref_str = f"{ref_num:.2E}"
    except:
        ref_str = ref_raw
        
    elemento = safe_str(row.get('elemento_s20_20', ''))
    metodo = INFO_ELEMENTOS_ESD.get(elemento, {}).get("metodo", "N/D")
    magnitud = INFO_ELEMENTOS_ESD.get(elemento, {}).get("magnitud", "")
    unidad = MAPA_UNIDADES.get(magnitud, "")
    
    html_rows = ""
    for i, val in enumerate(mediciones, 1):
        try:
            val_num = float(val)
            val_str = f"{val_num:.2E}" if val_num > 1000 or val_num < 0.01 else str(val)
        except:
            val_str = val
            
        html_rows += f"""
        <tr class="border-b border-gray-200 hover:bg-blue-50 print:hover:bg-transparent text-center">
            <td class="p-1 border-r border-gray-300 font-bold">{i}</td>
            <td class="p-1 border-r border-gray-300 font-mono">{ref_str}</td>
            <td class="p-1 border-r border-gray-300 bg-yellow-50 print:bg-transparent font-mono font-bold">{val_str}</td>
            <td class="p-1 border-r border-gray-300">{metodo}</td>
            <td class="p-1 border-r border-gray-300">{unidad}</td>
            <td class="p-1 border-r border-gray-300">N/A</td>
        </tr>
        """
        
    img_url = safe_str(row.get('imagen_url', ''))
    if img_url == 'N/D' or not img_url:
        img_tag = "<span class='text-gray-400 flex flex-col items-center'><br><br>Sin evidencia fotográfica</span>"
    else:
        img_tag = f'<img src="{img_url}" style="height: 190px; width: auto; max-width: 100%; object-fit: contain; margin: 0 auto;" />'
        
    fecha_raw = safe_str(row.get('fecha_auditoria'))
    fecha_ejecucion = fecha_raw.split('T')[0] if 'T' in fecha_raw else fecha_raw
    año_actual = datetime.today().strftime("%y")
    # --- NUEVO: EXTRAER ID REAL DE LA BASE DE DATOS ---
    db_id = row.get('id', index) # Intenta obtener la columna 'id', si falla usa el index como respaldo
    try:
        db_id = int(db_id)
    except:
        db_id = index
    # --------------------------------------------------
    resultado_str = safe_str(row.get('resultado', 'N/D'))
    res_upper = resultado_str.upper()
    
    if "NO CUMPLE" in res_upper or "RECHAZADO" in res_upper or "FALLA" in res_upper:
        res_color = "text-red-600"
    else:
        res_color = "text-green-600"
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-PV-{db_id:03d}-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@media print {{ body {{ -webkit-print-color-adjust: exact; }} }}</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm">🖨️ Imprimir / Guardar PDF</button>
    </div>
    <div class="max-w-5xl mx-auto bg-white shadow-xl print:shadow-none print:w-full">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between">
            <div class="w-1/3">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-1/3 text-center">
                <h1 class="text-lg font-bold text-gray-800">FORMATO DE VALIDACIÓN DE PRODUCTO (ESD)</h1>
                <p class="text-xs text-gray-600">ANSI/ESD S20.20-2021</p>
            </div>
            <div class="w-1/3 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Reporte: BCS-PV-{db_id:03d}-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Ejecución:</span><span>{fecha_ejecucion}</span>
                </div>
            </div>
        </div>
        <div class="p-6 space-y-6">
            <div class="grid grid-cols-2 gap-6">
                <div>
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Datos del Elemento de Control</div>
                    <table class="w-full text-sm border-collapse border border-gray-300">
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">ID:</td><td class="p-1">{safe_str(row.get('id_elemento'))}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Elemento:</td><td class="p-1">{safe_str(row.get('elemento_s20_20'))}</td></tr>
                    </table>
                </div>
            </div>
            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Resultados (ANSI/ESD S20.20)</div>
                <table class="w-full text-sm border-collapse border border-gray-300 text-center">
                    <tr class="bg-gray-100 border-b border-gray-300">
                        <th class="p-2 border-r border-gray-300">No.</th>
                        <th class="p-2 border-r border-gray-300">Referencia</th>
                        <th class="p-2 border-r border-gray-300">Resultado Obtenido</th>
                        <th class="p-2 border-r border-gray-300">Método de Prueba</th>
                        <th class="p-2 border-r border-gray-300">Unidad</th>
                        <th class="p-2 border-r border-gray-300">Punto de Colocación</th>
                    </tr>
                    {html_rows}
                    <tr class="border-t-2 border-gray-400 bg-gray-50">
                        <td colspan="2" class="p-2 font-bold text-right border-r border-gray-300">Promedio / Final:</td>
                        <td class="p-2 font-mono font-bold text-center border-r border-gray-300">{promedio_str}</td>
                        <td colspan="3"></td>
                    </tr>
                </table>
            </div>
            <div class="grid grid-cols-2 gap-6 h-64">
                <div class="border border-gray-300 flex flex-col items-center justify-center bg-gray-50 overflow-hidden relative">
                    <div class="absolute top-0 left-0 bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full text-left z-10">Evidencia</div>
                    <div class="mt-8 flex-1 flex items-center justify-center p-2">{img_tag}</div>
                </div>
                <div class="border border-gray-300 flex flex-col relative">
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full">Comentarios / Observaciones</div>
                    <div class="p-2 text-sm">{safe_str(row.get('notas'), 'Sin observaciones adicionales.')}</div>
                    <div class="absolute bottom-2 right-2 text-xl font-bold {res_color}">{resultado_str}</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html

# ==========================================
# SEGURIDAD Y ACCESO (SIN MURO DE LOGIN)
# ==========================================
token_actual = st.query_params.get("auth_token")

if token_actual and token_actual != "consulta_mode":
    token_decodificado = decodificar_sesion(token_actual)
    if token_decodificado:
        # Separamos el nombre del rol usando un separador especial "||"
        partes = token_decodificado.split("||")
        st.session_state.usuario_nombre = partes[0]
        st.session_state.rol_usuario = partes[1] if len(partes) > 1 else "Auditor"
        st.session_state.modo_lectura = False 
    else:
        st.session_state.usuario_nombre = "Usuario de Consulta"
        st.session_state.rol_usuario = "Consulta"
        st.session_state.modo_lectura = True
else:
    st.session_state.usuario_nombre = "Usuario de Consulta"
    st.session_state.rol_usuario = "Consulta"
    st.session_state.modo_lectura = True

# Al no haber muro, la aplicación principal se ejecuta SIEMPRE
# ==========================================
# APLICACIÓN PRINCIPAL // SIDEBAR
# ==========================================
RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# --- EVALUACIÓN DE ROLES (Asegúrate de tener esto antes del sidebar) ---
rol = st.session_state.get("rol_usuario", "Consulta")
es_admin = rol in ["Admin", "Auditor"]
es_rh = rol == "RH_Training"

# --- EVALUACIÓN DE ROLES (Asegúrate de tener esto antes del sidebar) ---
rol = st.session_state.get("rol_usuario", "Consulta")
es_admin = rol in ["Admin", "Auditor"]
es_rh = rol == "RH_Training"

with st.sidebar:
    # 1. LOGOTIPO (Siempre en la parte superior)
    st.image(
        "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/main/Logo_BCS_transparent%20(1).png", 
        use_container_width=True
    )
    st.divider()

    # 2. MENÚ PRINCIPAL EN ACORDEONES (Solo si no está en modo lectura)
    if not st.session_state.modo_lectura:
        st.markdown("### 🧭 MENÚ PRINCIPAL")
        
        # Modo Recursos Humanos
        if es_rh:
            st.info("👤 Modo RH: Acceso a Entrenamiento.")
            if st.session_state.vista_actual != "Entrenamiento":
                st.session_state.vista_actual = "Entrenamiento"
                st.rerun()
                
        # Modo Administradores / Auditores
        elif es_admin:
            secciones_esd = {
                "📊 Cumplimiento": [
                    ("🗺️ Mapa y Reportes", "Mapa"),
                    ("📅 Programación", "Schedule")
                ],
                "🏭 Auditorías": [
                    ("📱 Escáner QR", "Escáner"),
                    ("✅ Validación Integral", "Validación"),
                    ("🆕 Alta/Baja de Equipos", "Alta"),
                    ("🏭 Maquinaria", "Maquinaria")
                ],
                "🧪 Pruebas y análisis": [
                    ("⚡ Event Meter", "Event Meter"),
                    ("🚶‍♂️ Walking Test", "Walking Test"),
                    ("🔌 Sensibilidad", "Sensibilidad")
                ],
                "🌍 Infraestructura": [
                    ("🌍 Tierras y Piso", "Tierras")
                ], 
                "🎓 Gestión de personal": [
                    ("🎓 Entrenamiento", "Entrenamiento"),
                ]
            }

            # Renderizado dinámico de categorías mediante acordeones
            for categoria, vistas in secciones_esd.items():
                # expanded=True mantiene las cajas desplegadas por defecto para acceso rápido
                with st.expander(categoria, expanded=False): 
                    for nombre_vista, valor_real in vistas:
                        es_activa = (st.session_state.vista_actual == valor_real)
                        
                        # El botón de la vista activa se resalta automáticamente en color primario
                        if st.button(
                            nombre_vista, 
                            key=f"nav_{valor_real}", 
                            use_container_width=True, 
                            type="primary" if es_activa else "secondary"
                        ):
                            st.session_state.vista_actual = valor_real
                            limpiar_url_escaneo()
                            st.rerun()
                            
        st.divider()

    # 3. ZONA DE AUTENTICACIÓN / PERFIL DE USUARIO (Al fondo de la barra)
    if st.session_state.modo_lectura:
        st.warning("👁️ Modo Consulta Activo")
        st.markdown("---")
        st.markdown("#### 🔒 Ingreso de Auditor")
        with st.form("login_form_sidebar"):
            user_input = st.text_input("Usuario (ID)")
            pwd_input = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                with st.spinner("Autenticando..."):
                    try:
                        resp_user = supabase.table("usuarios_app").select("*").eq("usuario", user_input).execute()
                        if len(resp_user.data) > 0:
                            hash_guardado = resp_user.data[0]["password"]
                            if check_password_hash(hash_guardado, pwd_input):
                                nombre_real = resp_user.data[0]["nombre"]
                                rol_asignado = resp_user.data[0]["rol"]
                                
                                st.session_state.usuario_nombre = nombre_real
                                st.session_state.rol_usuario = rol_asignado
                                st.session_state.modo_lectura = False
                                
                                token_str = f"{nombre_real}||{rol_asignado}"
                                st.query_params["auth_token"] = codificar_sesion(token_str)
                                st.rerun()
                            else:
                                st.error("❌ Credenciales incorrectas")
                        else:
                            st.error("❌ Credenciales incorrectas")
                    except Exception as e:
                        st.error(f"⚠️ Error al conectar con la base de usuarios: {e}")
    else:
        # Perfil del usuario autenticado
        st.success(f"👤 Auditor: {st.session_state.usuario_nombre}")

        # Configuración de contraseña segura
        with st.expander("🔑 Cambiar mi contraseña"):
            with st.form("form_cambiar_pwd"):
                pwd_actual = st.text_input("Contraseña actual", type="password")
                pwd_nueva = st.text_input("Nueva contraseña", type="password")
                pwd_conf = st.text_input("Confirmar nueva contraseña", type="password")
                
                if st.form_submit_button("Actualizar", use_container_width=True):
                    if not pwd_actual or not pwd_nueva or not pwd_conf:
                        st.error("⚠️ Completa todos los campos.")
                    elif pwd_nueva != pwd_conf:
                        st.error("❌ Las contraseñas nuevas no coinciden.")
                    else:
                        with st.spinner("Actualizando..."):
                            try:
                                resp_actual = supabase.table("usuarios_app").select("id, password").eq("nombre", st.session_state.usuario_nombre).execute()
                                if len(resp_actual.data) > 0:
                                    hash_guardado = resp_actual.data[0]["password"]
                                    id_user_db = resp_actual.data[0]["id"]
                                    
                                    if check_password_hash(hash_guardado, pwd_actual):
                                        nuevo_hash = generate_password_hash(pwd_nueva)
                                        supabase.table("usuarios_app").update({"password": nuevo_hash}).eq("id", id_user_db).execute()
                                        st.success("✅ ¡Contraseña actualizada!")
                                        time.sleep(1.5)
                                        st.rerun()
                                    else:
                                        st.error("❌ La contraseña actual es incorrecta.")
                                else:
                                    st.error("❌ Error al ubicar tu usuario en la base de datos.")
                            except Exception as e:
                                st.error(f"Error de conexión: {e}")
        
        # Botón de Ajustes (Exclusivo administradores) fuera de los acordeones principales
        if st.session_state.rol_usuario == "Admin":
            if st.button("⚙️ Ajustes y Usuarios", use_container_width=True, type="primary" if st.session_state.vista_actual == "Ajustes" else "secondary"):
                st.session_state.vista_actual = "Ajustes"
                limpiar_url_escaneo()
                st.rerun()

        # Botón de salida
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_nombre = None
            st.session_state.modo_lectura = True
            st.session_state.rol_usuario = "Consulta"
            st.query_params.clear() 
            st.rerun()

def calcular_proxima_fecha(fecha_actual, frecuencia):
    frecuencia = str(frecuencia).strip().lower()
    if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
    elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
    elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
    elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
    else: return fecha_actual + relativedelta(years=1)

st.title("Sistema de Gestión ESD BCS-AIS Querétaro")

df_inv_full, df_piso_local, df_mob_local, df_ion_local, df_mon_local, df_em_local = cargar_datos_cloud()

# Y para evitar errores si está vacío:
if df_mon_local is None:
    df_mon_local = pd.DataFrame()

if df_inv_full is None:
    st.error("Falla al conectar con el servidor SQL.")
    st.stop()

if df_mob_local is None:
    st.error("Falla al conectar con el servidor SQL.")
    st.stop()

if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Escáner" 

id_escaneado_url = st.query_params.get("qr_id", "")
valor_ocr_detectado = st.query_params.get("ocr_val", "")
id_baja_url = st.query_params.get("qr_baja", "")

if id_escaneado_url or valor_ocr_detectado:
    st.session_state.vista_actual = "Escáner"
elif id_baja_url:
    st.session_state.vista_actual = "Alta"

# --- MENÚ DE NAVEGACIÓN DINÁMICO ---
rol = st.session_state.get("rol_usuario", "Consulta")

# Definir qué pestañas puede ver cada rol
es_admin = rol in ["Admin", "Auditor"]
es_rh = rol == "RH_Training"

# --- MENÚ DE NAVEGACIÓN DINÁMICO (SIDEBAR) ---
rol = st.session_state.get("rol_usuario", "Consulta")
es_admin = rol in ["Admin", "Auditor"]
es_rh = rol == "RH_Training"

# ==========================================
# VISTA: ALTA Y BAJA DE EQUIPOS
# ==========================================
if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
    st.markdown("### Gestión de Inventario ESD")
    
    with st.expander("📋 Directorio de IDs Existentes (Todos los Estatus)", expanded=False):
        tipo_dir = st.radio("Ver directorio de:", ["Mobiliario", "Ionizadores", "Maquinaria", "Equipos de Medición"], horizontal=True)
        
        st.info("💡 **Tip:** Aquí se muestran TODOS los equipos (Operativos y dados de Baja) para que verifiques disponibilidad. Haz clic en las columnas para ordenar.")
        
        df_dir = pd.DataFrame()
        if tipo_dir == "Mobiliario":
            df_dir = df_mob_local.copy() if df_mob_local is not None else pd.DataFrame()
        elif tipo_dir == "Ionizadores":
            df_dir = df_ion_local.copy() if df_ion_local is not None else pd.DataFrame()
        elif tipo_dir == "Maquinaria":
            try:
                resp_m = supabase.table("mediciones_maquinaria").select("linea_ubicacion, id_maquinaria, clasificacion, status_operativo").execute()
                df_dir = pd.DataFrame(resp_m.data)
                if not df_dir.empty:
                    df_dir = df_dir.rename(columns={'linea_ubicacion':'Línea', 'id_maquinaria':'Id de producto', 'clasificacion':'Clasificación', 'status_operativo':'Estatus operativo'})
            except: pass
        else:
            try:
                resp_e = supabase.table("equipos_medicion").select("id_equipo, tipo_equipo").execute()
                df_dir = pd.DataFrame(resp_e.data)
                if not df_dir.empty:
                    df_dir = df_dir.rename(columns={'id_equipo':'Id de producto', 'tipo_equipo':'Clasificación'})
                    df_dir['Línea'] = 'Laboratorio / N/A'
                    df_dir['Estatus operativo'] = 'OPERATIVO'
            except: pass
            
        if not df_dir.empty and 'Id de producto' in df_dir.columns:
            # Quitamos el filtro restrictivo para que incluya las bajas
            cols_to_show = [c for c in ['Línea', 'Id de producto', 'Clasificación', 'Estatus operativo'] if c in df_dir.columns]
            df_clean = df_dir[cols_to_show].dropna(subset=['Id de producto']).copy()
            
            # Resaltamos visualmente los que están dados de baja
            if 'Estatus operativo' in df_clean.columns:
                df_clean['Estatus operativo'] = df_clean['Estatus operativo'].apply(
                    lambda x: "🔴 DADO DE BAJA" if str(x).strip().upper() in ["NO OPERATIVO", "BAJA"] else f"🟢 {x}"
                )
                
            st.dataframe(df_clean.sort_values(by='Id de producto'), use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos disponibles en esta categoría.")
    
    st.divider()
    
    if "radio_alta_baja" not in st.session_state:
        st.session_state.radio_alta_baja = "🆕 Registrar Nuevo"
        
    if id_baja_url:
        st.session_state.radio_alta_baja = "🗑️ Dar de Baja"

    accion_seleccionada = st.radio(
        "Selecciona la acción a realizar:",
        ["🆕 Registrar Nuevo", "🗑️ Dar de Baja"],
        horizontal=True, label_visibility="collapsed", key="radio_alta_baja"
    )
    
    # --- SUB-VISTA 1: ALTA ---
    if accion_seleccionada == "🆕 Registrar Nuevo":
        tipo_alta = st.radio("Categoría del Equipo a Registrar:", ["Mobiliario", "Ionizador", "Monitor Continuo"], horizontal=True)
        
        if tipo_alta == "Mobiliario":
            df_target_alta = df_mob_local
        elif tipo_alta == "Ionizador":
            df_target_alta = df_ion_local
        else:
            df_target_alta = df_mon_local
            
        lineas_disponibles = obtener_catalogo_lineas()
        
        # --- CAMBIO CLAVE: LÍNEA AFUERA DEL FORMULARIO ---
        # Al estar afuera, cuando cambias de línea, el sistema reacciona y calcula el ID antes de que des click en guardar.
        nueva_linea = st.selectbox("📍 1. Selecciona la Línea (Ubicación) de destino", options=lineas_disponibles)
        
        # Lógica de Autocompletado del siguiente ID
        sugerencia_id = ""
        if tipo_alta == "Mobiliario":
            df_linea_mob = pd.DataFrame()
            if df_target_alta is not None and not df_target_alta.empty and 'Línea' in df_target_alta.columns:
                df_linea_mob = df_target_alta[df_target_alta['Línea'] == nueva_linea]
                
            if not df_linea_mob.empty:
                ids_actuales = df_linea_mob['Id de producto'].dropna().tolist()
                max_num = 0
                prefijo_comun = "MOB-"
                width_ceros = 2 # Por si usan 01 o 001
                
                for id_str in ids_actuales:
                    import re
                    # Extrae cualquier letra/guión al inicio y los números finales
                    match = re.search(r'^(.*?)(\d+)$', str(id_str).strip())
                    if match:
                        num = int(match.group(2))
                        if num > max_num:
                            max_num = num
                            prefijo_comun = match.group(1)
                            width_ceros = len(match.group(2))
                            
                if max_num > 0:
                    sugerencia_id = f"{prefijo_comun}{max_num + 1:0{width_ceros}d}"
                else:
                    sugerencia_id = f"{nueva_linea[:3].upper()}-01"
            else:
                sugerencia_id = f"{nueva_linea[:3].upper()}-01"
        else:
            sugerencia_id = "ION-001" if tipo_alta == "Ionizador" else "MON-001"

        if tipo_alta == "Mobiliario":
            st.info(f"💡 Siguiente ID detectado automáticamente para **{nueva_linea}**: `{sugerencia_id}`")

        with st.form("form_alta_equipo"):
            col1, col2 = st.columns(2)
            
            # El ID se llena solito con la sugerencia, pero te deja borrarlo y escribir otro si lo necesitas.
            nuevo_id = col1.text_input("2. ID de Producto a registrar", value=sugerencia_id)
            
            # --- CAMPOS PARA MOBILIARIO ---
            if tipo_alta == "Mobiliario":
                tipos_disponibles = sorted([str(x).strip() for x in df_target_alta.get('Clasificación', pd.Series()).unique() if pd.notna(x) and str(x).strip() != '']) if df_target_alta is not None and not df_target_alta.empty else []
                nuevo_tipo = col2.selectbox("Tipo / Clasificación", options=tipos_disponibles if tipos_disponibles else ["Mesa", "Silla"])
                
                with col1:
                    valor_alta_txt = st.text_input("Valor inicial (Ohms)", placeholder="Ej: 1e9 o 5.5e8")
                    valor_alta = parsear_resistencia(valor_alta_txt)
                    
                    if valor_alta == "ERROR":
                        st.error("❌ Formato inválido. Usa números o notación (ej: 1e9).")
                        valor_alta = None 
                    elif valor_alta is not None and valor_alta >= 1e9:
                        st.warning("⚠️ Atención: El valor ingresado excede el límite de 1e9 Ohms.")
            
                fabricante_opc = col2.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
                fabricante_final = col2.text_input("Especifique Fabricante") if fabricante_opc == "Otro" else fabricante_opc
                
                frecuencia_alta = col1.selectbox("Frecuencia", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
                col3, col4 = st.columns(2)
                nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
                limite_alta = col4.text_input("Límite Maximo", value="1.00E+09")
                balance_alta = 0.0
                
            # --- CAMPOS PARA IONIZADORES ---
            elif tipo_alta == "Ionizador":
                nuevo_tipo = col1.selectbox("Clasificación", options=["Ventilador", "Barra", "Pistola"])
                
                # Cambiado a text_input para liberar el teclado y permitir decimales sin bloqueos
                valor_alta_txt = col2.text_input("Descarga (Seg)", placeholder="Ej: 1.5")
                valor_alta = parsear_resistencia(valor_alta_txt)
                
                if valor_alta == "ERROR":
                    col2.error("❌ Formato de descarga inválido. Usa números (ej: 1.5).")
                    valor_alta = None
                
                fabricante_opc = col1.selectbox("Fabricante", options=["SMC", "Panasonic", "Keyence", "SIMCO", "Otro"])
                fabricante_final = col1.text_input("Especifique Fabricante") if fabricante_opc == "Otro" else fabricante_opc
                
                # Cambiado a text_input para permitir capturar voltajes negativos fácilmente (-5 V)
                balance_alta_txt = col2.text_input("Balance (V)", placeholder="Ej: 3 o -5")
                balance_alta = parsear_resistencia(balance_alta_txt)
                
                if balance_alta == "ERROR":
                    col2.error("❌ Formato de balance inválido. Usa números enteros o decimales.")
                    balance_alta = None
                    
                frecuencia_alta = "Trimestral"
                nuevo_minimo = 0.00
                limite_alta = "10.00"

            # --- CAMPOS PARA MONITORES CONTINUOS ---
            elif tipo_alta == "Monitor Continuo":
                nuevo_tipo = col1.selectbox("Clasificación", options=["Monitor Sencillo", "Monitor Dual", "Monitor de Superficie"])
                
                with col2:
                    # Eliminamos las tres columnas complejas y abrimos el teclado completo
                    valor_alta_txt = st.text_input("Resistencia inicial (Ohms)", placeholder="Ej: 1e6 o 1.2e7", key="txt_mon_res")
                    
                    valor_alta = parsear_resistencia(valor_alta_txt)
                    
                    if valor_alta == "ERROR":
                        st.error("❌ Formato inválido. Usa números o notación científica (ej: 1e6).")
                        valor_alta = None
                        
                fabricante_opc = col1.selectbox("Fabricante", options=["SCS", "Desco", "Transforming Technologies", "Botron", "Otro"])
                fabricante_final = col1.text_input("Especifique Fabricante") if fabricante_opc == "Otro" else fabricante_opc
                
                frecuencia_alta = col2.selectbox("Frecuencia", options=["Trimestral", "Semestral", "Anual"], index=0)
                
                col3, col4 = st.columns(2)
                nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e", key="min_mon")
                # Limite típico de monitor según tu diccionario (2.0) o (10 Megohms = 1.00E+07)
                limite_alta = col4.text_input("Límite Máximo", value="1.00E+07", key="lim_mon")
                balance_alta = 0.0
                
            comentarios = st.text_area("Comentarios")
            submit_alta = st.form_submit_button("Registrar en sistema", use_container_width=True)
            
        if submit_alta:
            # 0. BLOQUEO DE SEGURIDAD PARA FORMATOS INVÁLIDOS
            if valor_alta == "ERROR" or (tipo_alta == "Ionizador" and balance_alta == "ERROR"):
                st.error("❌ Hay valores de medición inválidos en el formulario. Corrígelos antes de guardar.")
            # 1. Dejamos solo los campos verdaderamente obligatorios para crear el registro
            elif not nuevo_id or not fabricante_final:
                st.error("⚠️ Por favor complete los campos obligatorios (ID y Fabricante).")
            else:
                id_limpio_alta = str(nuevo_id).strip().upper()
                
                check_inv = supabase.table("inventario_esd").select("id_producto").eq("id_producto", id_limpio_alta).execute()
                check_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria").eq("id_maquinaria", id_limpio_alta).execute()
                
                if len(check_inv.data) > 0 or len(check_maq.data) > 0:
                    st.error(f"❌ El ID '{nuevo_id}' ya se encuentra registrado en el sistema. Usa un ID diferente.")
                else:
                    with st.spinner("Guardando en SQL..."):
                        fecha_hoy = datetime.today().date()
                        dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                        proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                        
                        # Determinar el método de prueba correcto
                        if tipo_alta == "Ionizador":
                            metodo_final = "CPM"
                        elif tipo_alta == "Monitor Continuo":
                            metodo_final = "Anexo A.1"
                        else:
                            metodo_final = "RTG"

                        # 2. VARIABLE DE CONTROL
                        tiene_valor = valor_alta is not None and valor_alta != "ERROR"
                        
                        # 2.5 EVALUACIÓN AUTOMÁTICA DE ESTATUS (Estandarizado a VIGENTE/VENCIDO/PENDIENTE)
                        estatus_final = "PENDIENTE"
                        
                        # Parseo seguro del límite (usando nuestra función salvavidas)
                        limite_numerico = parsear_resistencia(limite_alta)
                        if limite_numerico == "ERROR":
                            limite_numerico = 1.0e9 # Valor de respaldo seguro
                            
                        if tiene_valor:
                            # Evaluamos si el valor capturado pasa la norma
                            if float(valor_alta) < limite_numerico:
                                estatus_final = "VIGENTE"
                            else:
                                estatus_final = "VENCIDO"
                                
                            # Si es ionizador, el balance también puede reprobar al equipo (ej. límite +/- 35V)
                            if tipo_alta == "Ionizador" and balance_alta is not None and balance_alta != "ERROR":
                                if abs(float(balance_alta)) > 35.0: # Ajusta el 35.0 según tu norma real para balance
                                    estatus_final = "VENCIDO"

                        # 3. DICCIONARIO BLINDADO
                        data_insert = {
                            "id_producto": id_limpio_alta,
                            "categoria": tipo_alta,
                            "linea_ubicacion": nueva_linea,
                            "clasificacion": nuevo_tipo,
                            "fabricante": fabricante_final,
                            "limite_minimo": float(nuevo_minimo),
                            "limite_maximo": float(limite_numerico), 
                            "unidad_medida": "Segundos" if tipo_alta == "Ionizador" else "Ohms",
                            "valor_actual": float(valor_alta) if tiene_valor else None,
                            "metodo_prueba": metodo_final,
                            "fecha_ultima_verif": fecha_hoy.isoformat() if tiene_valor else None,
                            "fecha_proxima_verif": proxima.isoformat() if tiene_valor else None,
                            "frecuencia": frecuencia_alta,
                            "estatus_verificacion": estatus_final, # <-- Automático e Inteligente
                            "estatus_operativo": "OPERATIVO",
                            "comentarios": comentarios,
                            "auditor_responsable": st.session_state.usuario_nombre
                        }
                        
                        # Manejo seguro para el balance del ionizador
                        if tipo_alta == "Ionizador":
                            data_insert["balance_ionizador"] = float(balance_alta) if (balance_alta is not None and balance_alta != "ERROR") else None
                        
                        try:
                            supabase.table("inventario_esd").insert(data_insert).execute()
                            st.success(f"✅ ¡Activo {nuevo_id} registrado con éxito en estatus: {estatus_final}!")
                            st.balloons()
                            st.cache_data.clear()
                            time.sleep(1.5) # <--- PAUSA AGREGADA
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error SQL: {e}")
                            
    # --- SUB-VISTA 2: BAJA (CON ESCÁNER QR REACTIVO INDEPENDIENTE) ---
    elif accion_seleccionada == "🗑️ Dar de Baja":
        st.markdown("#### 🗑️ Desactivación de Activos ESD")
        
        if not id_baja_url:
            st.markdown("### 📷 Apunta al Código QR del Equipo a Dar de Baja")
            html_code_qr_baja = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader_baja" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #dc3545; background-color: #f9f9f9;"></div>
            
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
                <button type="button" id="cam_wide_baja" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
                <button type="button" id="cam_cycle_baja" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
            </div>
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
                <button type="button" id="zoom_1x_baja" style="padding:10px 20px; background:#dc3545; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
                <button type="button" id="zoom_3x_baja" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
            </div>
            <p id="cam-status-baja" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
            
            <script>
            let html5QrCodeBaja;
            let rearCamsBaja = [];
            let currentIdxBaja = 0;
            let wideIdBaja = null;

            function applyZoomBaja(scale) {
                const vid = document.querySelector("#reader_baja video");
                if (vid) {
                    vid.style.transform = `scale(${scale})`;
                    vid.style.transformOrigin = "center center";
                }
                document.getElementById('zoom_1x_baja').style.background = (scale === 1) ? "#dc3545" : "#666";
                document.getElementById('zoom_3x_baja').style.background = (scale === 3) ? "#dc3545" : "#666";
            }

            function startScannerBaja(camId) {
                if(!html5QrCodeBaja) html5QrCodeBaja = new Html5Qrcode("reader_baja");
                if (html5QrCodeBaja.isScanning) {
                    html5QrCodeBaja.stop().then(() => { runScanBaja(camId); }).catch(e => console.log(e));
                } else {
                    runScanBaja(camId);
                }
            }

            function runScanBaja(camId) {
                html5QrCodeBaja.start(
                    camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCodeBaja.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_baja", decodedText);
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    }, (err) => {} 
                ).then(() => { 
                    let activeCam = rearCamsBaja.find(c => c.id === camId);
                    document.getElementById("cam-status-baja").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                    applyZoomBaja(1);
                }).catch(err => {
                    document.getElementById("cam-status-baja").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
                });
            }

            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    rearCamsBaja = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                    if(rearCamsBaja.length === 0) rearCamsBaja = devices;

                    wideIdBaja = rearCamsBaja[0].id;
                    for (let c of rearCamsBaja) {
                        let lbl = c.label.toLowerCase();
                        if (lbl.includes('wide') && !lbl.includes('ultra')) {
                            wideIdBaja = c.id; break;
                        }
                    }

                    currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                    if(currentIdxBaja === -1) currentIdxBaja = 0;

                    startScannerBaja(wideIdBaja);

                    document.getElementById('cam_wide_baja').addEventListener('click', () => {
                        currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                        startScannerBaja(wideIdBaja);
                    });

                    document.getElementById('cam_cycle_baja').addEventListener('click', () => {
                        currentIdxBaja = (currentIdxBaja + 1) % rearCamsBaja.length;
                        startScannerBaja(rearCamsBaja[currentIdxBaja].id);
                    });

                    document.getElementById('zoom_1x_baja').addEventListener('click', () => applyZoomBaja(1));
                    document.getElementById('zoom_3x_baja').addEventListener('click', () => applyZoomBaja(3));
                }
            }).catch(err => { document.getElementById("cam-status-baja").innerText = "Permisos de cámara denegados."; });
            </script>
            """
            components.html(html_code_qr_baja, height=750)
            
            id_manual_baja = st.text_input("O ingresa el ID manual para Baja:", key="input_manual_baja")
            if id_manual_baja:
                st.query_params["qr_baja"] = id_manual_baja
                st.rerun()
        else:
            colA, colB = st.columns([0.8, 0.2])
            with colA: st.error(f"🗑️ **ID a Procesar:** {id_baja_url}")
            with colB:
                if st.button("❌ Cancelar"):
                    limpiar_url_escaneo()
                    st.rerun()

            id_limpio_baja = str(id_baja_url).strip().upper()
            
            # --- INICIO DE LÓGICA DE VISUALIZACIÓN Y BAJA SELECTIVA ---
            # 1. Buscar en inventario_esd (Mobiliario / Ionizadores)
            equipo_encontrado_inv = df_inv_full[df_inv_full['Id de producto'].astype(str).str.upper() == id_limpio_baja]
            
            # 2. Buscar en mediciones_maquinaria (Maquinaria)
            try:
                resp_maq_baja = supabase.table("mediciones_maquinaria").select("*").eq("id_maquinaria", id_limpio_baja).order("fecha_medicion", desc=True).limit(1).execute()
                df_maq_baja = pd.DataFrame(resp_maq_baja.data)
            except:
                df_maq_baja = pd.DataFrame()

            if not equipo_encontrado_inv.empty or not df_maq_baja.empty:
                st.markdown(f"### 📋 Detalles del Equipo a Dar de Baja: `{id_limpio_baja}`")
                st.info("Selecciona de qué catálogo deseas dar de baja este ID de forma independiente.")
                
                col_b1, col_b2 = st.columns(2)
                
                # Panel para Inventario (Mobiliario/Ionizadores)
                with col_b1:
                    if not equipo_encontrado_inv.empty:
                        info_eq = equipo_encontrado_inv.iloc[0]
                        st.markdown("#### 🛋️/⚡ Registro en Inventario")
                        st.metric("Clasificación", str(info_eq.get('Clasificación', 'N/D')))
                        st.metric("Estatus Actual", str(info_eq.get('Estatus operativo', 'N/D')))
                        
                        with st.form("form_baja_inv"):
                            if st.form_submit_button("🗑️ Dar de Baja en Inventario", use_container_width=True):
                                with st.spinner("Actualizando SQL..."):
                                    try:
                                        # 1. Extraemos el ID exacto y original directamente desde el DataFrame
                                        id_exacto_db = str(info_eq['Id de producto'])
                                        
                                        # 2. Hacemos el update usando el texto literal de la base de datos
                                        supabase.table("inventario_esd").update({
                                            "estatus_operativo": "NO OPERATIVO",
                                            "estatus_verificacion": "PENDIENTE" # Estandarizado a PENDIENTE, como es baja, no debe ser VIGENTE ni VENCIDO.
                                        }).eq("id_producto", id_exacto_db).execute()
                                        
                                        st.success("✅ ¡Desactivado de Inventario!")
                                        st.cache_data.clear()
                                        limpiar_url_escaneo()
                                        st.balloons()
                                        time.sleep(1.5) # <--- PAUSA AGREGADA
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                    else:
                        st.warning("No existe en el catálogo de Inventario.")
                        
                # Panel para Maquinaria
                with col_b2:
                    if not df_maq_baja.empty:
                        info_maq = df_maq_baja.iloc[0]
                        st.markdown("#### 🏭 Registro en Maquinaria")
                        st.metric("Clasificación", str(info_maq.get('clasificacion', 'N/D')))
                        st.metric("Estatus Actual", str(info_maq.get('status_operativo', 'N/D')))
                        
                        with st.form("form_baja_maq"):
                            # Botón principal en rojo/destacado para maquinaria
                            if st.form_submit_button("🗑️ Dar de Baja en Maquinaria", type="primary", use_container_width=True):
                                with st.spinner("Actualizando SQL..."):
                                    try:
                                        supabase.table("mediciones_maquinaria").update({
                                            "status_operativo": "NO OPERATIVO",
                                            "resultado_estatus": "PENDIENTE" # Estandarizado a PENDIENTE.
                                        }).eq("id_maquinaria", id_limpio_baja).execute()
                                        st.success("✅ ¡Desactivado de Maquinaria!")
                                        st.cache_data.clear()
                                        limpiar_url_escaneo()
                                        st.balloons()
                                        time.sleep(1.5) # <--- PAUSA AGREGADA
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                    else:
                        st.warning("No existe en el registro de Maquinaria.")

            else:
                st.error(f"❌ No se encontró ningún registro con el ID: {id_limpio_baja}")
                if st.button("🔄 Volver a intentar", use_container_width=True):
                    limpiar_url_escaneo()
                    st.rerun()
            # --- FIN DE LÓGICA SELECTIVA ---
# ==========================================
# VISTA 1: MAPA Y REPORTES ESD
# ==========================================
elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
    st.markdown("### Mapa y Cumplimiento ESD")
    tab_mapa, tab_overview, tab_4q = st.tabs(["📍 Mapa Físico", "📊 Overview (S20.20)", "📋 4Q (Hallazgos)"])
    
    with tab_mapa:
        tipo_mapa = st.radio("Ver en mapa:", ["Mobiliario", "Ionizadores", "Maquinaria", "Pisos"], horizontal=True)
        
        # ==========================================
        # 1. LÓGICA EXCLUSIVA PARA PISOS (MAPA RADIAL + TABLA)
        # ==========================================
        if tipo_mapa == "Pisos":
            diagramas_cuartos = {
                "Cuarto 1": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/1.png",
                "Cuarto 2": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/2.png",
                "Cuarto 3": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/3.png",
                "Cuarto 4": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/4.png",
                "Cuarto 5": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/5.png",
                "Cuarto 6": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/6.png"
            }

            COORDENADAS_PISOS = {
                "Cuarto 1": {1: (53, 649), 2: (241, 656), 3: (508, 651), 4: (576, 568), 5: (484, 567), 6: (242, 567), 7: (56, 472), 8: (241, 466), 9: (471, 466), 10: (533, 381), 11: (243, 384), 12: (242, 259), 13: (593, 258), 14: (205, 173), 15: (561, 66)},
                "Cuarto 2": {1: (38, 404), 2: (174, 365), 3: (154, 277), 4: (255, 222), 5: (109, 65), 6: (346, 85), 7: (523, 90), 8: (579, 211), 9: (334, 201), 10: (330, 380), 11: (253, 461), 12: (251, 585), 13: (588, 385), 14: (590, 511), 15: (482, 595)},
                "Cuarto 3": {1: (74, 585), 2: (128, 422), 3: (126, 199), 4: (263, 93), 5: (329, 37), 6: (614, 71), 7: (545, 180), 8: (341, 259), 9: (233, 338), 10: (280, 474), 11: (225, 586), 12: (424, 394), 13: (424, 543), 14: (549, 472), 15: (633, 380)},
                "Cuarto 4": {1: (71, 425), 2: (84, 271), 3: (117, 59), 4: (375, 60), 5: (503, 65), 6: (581, 205), 7: (547, 328), 8: (175, 335), 9: (274, 381), 10: (434, 375), 11: (415, 466), 12: (174, 557), 13: (598, 517), 14: (293, 629), 15: (568, 629)},
                "Cuarto 5": {1: (50, 81), 2: (107, 309), 3: (176, 569), 4: (293, 487), 5: (523, 563), 6: (826, 488), 7: (923, 376), 8: (682, 369), 9: (391, 276), 10: (733, 239), 11: (389, 145), 12: (718, 128), 13: (905, 215), 14: (860, 89), 15: (963, 547)},
                "Cuarto 6": {1: (92, 567), 2: (135, 466), 3: (112, 313), 4: (147, 167), 5: (185, 40), 6: (370, 42), 7: (708, 46), 8: (702, 196), 9: (368, 197), 10: (705, 295), 11: (370, 297), 12: (602, 387), 13: (707, 587), 14: (437, 587), 15: (247, 596)}
            }

            c_p1, c_p2 = st.columns([1, 2])
            cuarto_visualizar = c_p1.selectbox("📍 Selecciona el Cuarto para visualización física:", list(diagramas_cuartos.keys()))
            
            with st.spinner(f"Generando mapa de calor radial para {cuarto_visualizar}..."):
                try:
                    import numpy as np
                    from scipy.spatial.distance import cdist
                    import plotly.graph_objects as go
                    import requests
                    from PIL import Image
                    from io import BytesIO

                    url_img = diagramas_cuartos[cuarto_visualizar]
                    response = requests.get(url_img)
                    img_pil = Image.open(BytesIO(response.content))
                    img_w, img_h = img_pil.size

                    # Obtener última auditoría del cuarto seleccionado
                    resp_db = supabase.table("validacion_piso").select("*").eq("cuarto", cuarto_visualizar).order("fecha_medicion", desc=True).limit(20).execute()
                    df_latest = pd.DataFrame(resp_db.data)

                    if not df_latest.empty:
                        ultima_fecha = df_latest['fecha_medicion'].max()
                        df_mapa = df_latest[df_latest['fecha_medicion'] == ultima_fecha].copy()
                        
                        coords_map = COORDENADAS_PISOS[cuarto_visualizar]
                        pts_x, pts_y, vals_log, info_reales = [], [], [], []

                        for _, r in df_mapa.iterrows():
                            p = int(r['punto'])
                            if p in coords_map:
                                v = float(r['medicion_ohms'])
                                lx = coords_map[p][0]
                                ly = img_h - coords_map[p][1] # Corrección eje Y
                                pts_x.append(lx); pts_y.append(ly)
                                vals_log.append(max(7.0, min(9.0, math.log10(v))))
                                info_reales.append({"X": lx, "Y": ly, "P": p, "R": f"{v:.2e}"})

                        if len(pts_x) >= 2:
                            rx = 200
                            ry = int(200 * (img_h / img_w))
                            gx, gy = np.mgrid[0:img_w:complex(0, rx), 0:img_h:complex(0, ry)]
                            g_coords = np.vstack([gx.ravel(), gy.ravel()]).T
                            k_coords = np.array([pts_x, pts_y]).T
                            
                            dists = cdist(g_coords, k_coords)
                            dists = np.where(dists == 0, 1e-10, dists)
                            weights = 1.0 / (dists ** 2.5)
                            gz = (np.sum(weights * np.array(vals_log), axis=1) / np.sum(weights, axis=1)).reshape(rx, ry)

                            fig_piso = go.Figure()
                            
                            # MAPA DE CALOR
                            fig_piso.add_trace(go.Heatmap(
                                z=gz.T, x=np.linspace(0, img_w, rx), y=np.linspace(0, img_h, ry),
                                colorscale=[
                                    [0.0, "rgba(40, 167, 69, 0.45)"], [0.25, "rgba(139, 195, 74, 0.5)"],
                                    [0.5, "rgba(255, 193, 7, 0.55)"], [0.75, "rgba(253, 126, 20, 0.65)"],
                                    [1.0, "rgba(220, 53, 69, 0.75)"]
                                ],
                                zmin=7, zmax=9, showscale=False, hoverinfo='skip'
                            ))

                            # PUNTOS CON HOVER
                            df_pts = pd.DataFrame(info_reales)
                            fig_piso.add_trace(go.Scatter(
                                x=df_pts['X'], y=df_pts['Y'], mode='markers+text', text=df_pts['P'],
                                marker=dict(size=20, color='black', line=dict(width=1, color='white')),
                                textposition="middle center", textfont=dict(color='white', size=10, weight='bold'),
                                hovertemplate="Punto %{text}<br>Resistencia: %{customdata} Ω<extra></extra>",
                                customdata=df_pts['R']
                            ))

                            fig_piso.update_layout(
                                xaxis=dict(visible=False, range=[0, img_w]),
                                yaxis=dict(visible=False, range=[0, img_h], scaleanchor="x", scaleratio=1),
                                images=[dict(source=img_pil, xref="x", yref="y", x=0, y=img_h, sizex=img_w, sizey=img_h, sizing="stretch", layer="below")],
                                margin=dict(l=0, r=0, t=0, b=0), height=600, showlegend=False
                            )
                            
                            # --- 1. RENDERIZAR MAPA ---
                            st.plotly_chart(fig_piso, use_container_width=True)
                            st.caption(f"📅 Auditoría del {str(ultima_fecha)[:10]}")
                            
                            # --- 2. RENDERIZAR TABLA CON VALORES EXACTAMENTE DEBAJO ---
                            st.divider()
                            st.markdown(f"##### 📋 Datos registrados en la última auditoría ({str(ultima_fecha)[:10]})")
                            df_mostrar_piso = df_mapa[['punto', 'medicion_ohms', 'temperatura', 'humedad', 'estatus', 'auditor']].copy()
                            df_mostrar_piso['medicion_ohms'] = df_mostrar_piso['medicion_ohms'].apply(lambda x: f"{float(x):.2e} Ω")
                            df_mostrar_piso.columns = ['Punto', 'Resistencia', 'Temp (°C)', 'Humedad (%)', 'Estatus', 'Auditor']
                            
                            df_mostrar_piso['Estatus'] = df_mostrar_piso['Estatus'].apply(lambda x: f"🟢 {x}" if "PASA" in str(x).upper() else f"🔴 {x}")
                            st.dataframe(df_mostrar_piso.sort_values(by='Punto'), use_container_width=True, hide_index=True)
                            
                        else:
                            st.warning("Se requieren al menos 2 puntos para el renderizado radial.")
                    else:
                        st.info("No hay datos históricos para este cuarto.")
                        st.image(url_img, use_container_width=True)
                except Exception as e:
                    st.error(f"Error en renderizado: {e}")

        # ==========================================
        # 2. LÓGICA PARA MAPA GENERAL (MOBILIARIO, IONIZADORES, MAQUINARIA)
        # ==========================================
        else:
            if tipo_mapa == "Mobiliario":
                df_total = df_mob_local.copy() if df_mob_local is not None else pd.DataFrame()
            elif tipo_mapa == "Ionizadores":
                df_total = df_ion_local.copy() if df_ion_local is not None else pd.DataFrame()
            elif tipo_mapa == "Maquinaria":
                try:
                    resp_maq_mapa = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
                    df_maq_mapa = pd.DataFrame(resp_maq_mapa.data)
                    if not df_maq_mapa.empty:
                        df_maq_mapa = df_maq_mapa.drop_duplicates(subset=['id_maquinaria'], keep='first')
                        df_total = df_maq_mapa.rename(columns={
                            'status_operativo': 'Estatus operativo',
                            'resultado_estatus': 'Estatus de verificación',
                            'linea_ubicacion': 'Línea',
                            'id_maquinaria': 'Id de producto',
                            'clasificacion': 'Clasificación'
                        })
                    else:
                        df_total = pd.DataFrame()
                except:
                    df_total = pd.DataFrame()
            
            if df_total.empty:
                st.warning(f"No hay datos registrados en {tipo_mapa}.")
            else:
                equipos_activos = df_total[df_total['Estatus operativo'].astype(str).str.upper() != 'NO OPERATIVO']
                total_equipos = len(equipos_activos)
                vencidos = equipos_activos[equipos_activos['Estatus de verificación'].astype(str).str.upper() == 'VENCIDO']
                total_vencidos = len(vencidos)
            
                if total_equipos > 0:
                    porcentaje = ((total_equipos - total_vencidos) / total_equipos) * 100
                else:
                    porcentaje = 100.0

                estatus_ser = equipos_activos['Estatus de verificación'].astype(str).str.strip().str.upper()
                es_nulo = equipos_activos['Estatus de verificación'].isna() | estatus_ser.isin(['', 'NONE', 'NAN', 'NULL', 'N/A', 'N/D', 'PENDIENTE'])
                
                df_alertas = equipos_activos[estatus_ser.str.contains('VENCIDO') | es_nulo].copy()
                total_alertas = len(df_alertas)
                
                if total_alertas > 0:
                    st.error(f"🚨 **Cumplimiento:** {porcentaje:.1f}% | **Requieren Atención:** {total_alertas} activos (🔴 Vencidos/🟡 Pendientes).")
                    
                    conteo_tipos = df_alertas.groupby(['Línea']).size().reset_index(name='Total Alertas')
                    prefijo = {"Mobiliario": "M: ", "Ionizadores": "I: ", "Maquinaria": "MQ: "}.get(tipo_mapa, "A: ")
                    conteo_tipos['Etiqueta'] = prefijo + conteo_tipos['Total Alertas'].astype(str)
                
                    if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                        img = Image.open(RUTA_MAPA)
                        width, height = img.size
                        df_coords = pd.read_csv(RUTA_COORDENADAS)
                        mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
                        
                        if not mapa_data.empty:
                            fig = px.scatter(
                                mapa_data, x="X", y="Y", color="Total Alertas", text="Etiqueta",
                                hover_data={"X": False, "Y": False, "Etiqueta": False, "Total Alertas": True},
                                color_continuous_scale="Reds"
                            )
                            
                            fig.update_traces(
                                textposition='middle center', 
                                textfont=dict(color='white', size=14, weight='bold'), 
                                marker=dict(symbol='circle', size=45, opacity=0.9, line=dict(width=2, color='black'))
                            )
                            
                            aspect_ratio = height / width
                            plot_height = int(1000 * aspect_ratio)

                            fig.update_layout(
                                height=plot_height,
                                images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")], 
                                xaxis=dict(visible=False, range=[0, width]), 
                                yaxis=dict(visible=False, range=[height, 0], scaleanchor="x", scaleratio=1), 
                                margin=dict(l=0, r=0, t=0, b=0),
                                coloraxis_showscale=False
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("##### 📋 Desglose de Activos en Alerta")
                    st.dataframe(df_alertas[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
                else:
                    st.success(f"✅ **100% Cumplimiento en {tipo_mapa}.** No hay alertas activas en el mapa general.")

    with tab_overview:
            st.markdown("#### 🌐 Dashboard Gerencial Integral (S20.20)")
            st.info("Resumen global del estado de cumplimiento, dinámica de auditorías y movimientos de inventario en la planta.")

            # --- 1. EXTRACCIÓN MASIVA DE DATOS ---
            with st.spinner("Compilando métricas globales y rastreando actividad..."):
                try:
                    # 🛠️ CORRECCIÓN: Definimos la función calculadora ANTES de usarla
                    def contar_estatus(df, col_estatus, val_vigente, val_vencido):
                        if df.empty or col_estatus not in df.columns: return 0, 0, 0
                        estatus_series = df[col_estatus].astype(str).str.upper()
                        
                        vig = estatus_series.str.contains(val_vigente, regex=True).sum()
                        ven = estatus_series.str.contains(val_vencido, regex=True).sum()
                        
                        pen = len(df) - (vig + ven)
                        return vig, ven, pen

                    # A. Maquinaria (último estado para cumplimiento) y Todas las fechas (para actividad)
                    resp_maq_ov = supabase.table("mediciones_maquinaria").select("id_maquinaria, status_operativo, resultado_estatus, fecha_medicion").execute()
                    df_maq_ov = pd.DataFrame(resp_maq_ov.data)
                    fechas_actividad = []
                    if not df_maq_ov.empty:
                        fechas_actividad.extend(df_maq_ov['fecha_medicion'].dropna().tolist())
                        # Para el estatus de cumplimiento, nos quedamos con la última medición válida
                        df_maq_ov = df_maq_ov.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'], keep='first')

                    pasa_t = 0
                    falla_t = 0
                    
                    # B. Tierras y Monitores Continuos
                    # 1. Cálculo de Tierras Auxiliares
                    # 🛠️ CORRECCIÓN: Agregamos 'linea' a la consulta SQL
                    resp_tierras_ov = supabase.table("tierras_auxiliares").select("id_punto, linea, estatus, fecha_medicion").execute()
                    df_tierras_ov = pd.DataFrame(resp_tierras_ov.data)
                    
                    if not df_tierras_ov.empty:
                        fechas_actividad.extend(df_tierras_ov['fecha_medicion'].dropna().tolist())
                        
                        # 🛠️ CORRECCIÓN: Ahora filtramos duplicados usando la combinación de Línea + ID
                        df_tierras_ov = df_tierras_ov.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['linea', 'id_punto'])
                        
                        p_t, f_t, _ = contar_estatus(df_tierras_ov, 'estatus', 'VIGENTE|APROBADO|PASA|CUMPLE', 'VENCIDO|FALLA|RECHAZADO|NO CUMPLE')
                        pasa_t += p_t
                        falla_t += f_t
            
                    # 2. Cálculo de Monitores Continuos (Directo desde el Inventario)
                    resp_monitores = supabase.table("inventario_esd").select("id_producto, estatus_verificacion, fecha_ultima_verif").eq("categoria", "Monitor Continuo").execute()
                    df_monitores = pd.DataFrame(resp_monitores.data)
                    
                    if not df_monitores.empty:
                        fechas_actividad.extend(df_monitores['fecha_ultima_verif'].dropna().tolist())
                        df_monitores = df_monitores.sort_values('fecha_ultima_verif', ascending=False).drop_duplicates(subset=['id_producto'])
                        
                        # 🛠️ CORRECCIÓN: Diccionario ampliado para Monitores
                        p_m, f_m, _ = contar_estatus(df_monitores, 'estatus_verificacion', 'VIGENTE|APROBADO|PASA|CUMPLE', 'VENCIDO|FALLA|RECHAZADO|NO CUMPLE')
                        pasa_t += p_m
                        falla_t += f_m

                    # C. Event Meter
                    resp_em_ov = supabase.table("event_meter").select("id_operacion, estatus_verificacion, fecha").execute()
                    df_em_ov = pd.DataFrame(resp_em_ov.data)
                    if not df_em_ov.empty:
                        fechas_actividad.extend(df_em_ov['fecha'].dropna().tolist())
                        df_em_ov = df_em_ov.sort_values('fecha', ascending=False).drop_duplicates(subset=['id_operacion'])

                    # D. Checadores
                    resp_chec_ov = supabase.table("verificacion_checadores").select("id_checador, estatus, fecha_verificacion").execute()
                    df_chec_ov = pd.DataFrame(resp_chec_ov.data)
                    if not df_chec_ov.empty:
                        fechas_actividad.extend(df_chec_ov['fecha_verificacion'].dropna().tolist())
                        df_chec_ov = df_chec_ov.sort_values('fecha_verificacion', ascending=False).drop_duplicates(subset=['id_checador'])

                    # E. Validaciones de Elementos (Materiales Validados)
                    resp_val_ov = supabase.table("validacion_esd").select("fecha_auditoria").execute()
                    df_val_ov = pd.DataFrame(resp_val_ov.data)
                    total_materiales_validados = len(df_val_ov)
                    if not df_val_ov.empty:
                        fechas_actividad.extend(df_val_ov['fecha_auditoria'].dropna().tolist())

                    # F. Reportes de Calificación (Certificados)
                    resp_cert_ov = supabase.table("reportes_calificacion").select("fecha_registro").execute()
                    df_cert_ov = pd.DataFrame(resp_cert_ov.data)
                    total_certificados = len(df_cert_ov)
                    if not df_cert_ov.empty:
                        fechas_actividad.extend(df_cert_ov['fecha_registro'].dropna().tolist())

                    # G. Historial de Mediciones
                    resp_hist_ov = supabase.table("historial_mediciones").select("fecha_modificacion").execute()
                    if resp_hist_ov.data:
                        fechas_actividad.extend([x['fecha_modificacion'] for x in resp_hist_ov.data if x.get('fecha_modificacion')])

                    # H. Sensibilidad Mínima en Planta
                    resp_sens = supabase.table("componentes_sensibilidad").select("esd_hbm, esd_cdm").execute()
                    df_sens = pd.DataFrame(resp_sens.data)
                    min_sensibilidad = "N/D"
                    alerta_sensibilidad = False
                    if not df_sens.empty:
                        df_sens['hbm'] = pd.to_numeric(df_sens['esd_hbm'].replace('-', pd.NA), errors='coerce')
                        df_sens['cdm'] = pd.to_numeric(df_sens['esd_cdm'].replace('-', pd.NA), errors='coerce')
                        min_val = df_sens[['hbm', 'cdm']].min().min()
                        if pd.notna(min_val):
                            min_sensibilidad = f"{min_val:g} V"
                            alerta_sensibilidad = min_val < 100

                    # ==========================================
                    # I. ALTAS Y BAJAS (Inventario y Maquinaria)
                    # ==========================================
                    hace_30_dias = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=30)
                    altas_inv_30d = 0; bajas_inv_total = 0
                    altas_maq_30d = 0; bajas_maq_total = 0

                    try:
                        # I.1 Movimientos en Inventario General (Mobiliario, Ionizadores, etc.)
                        resp_inv_mov = supabase.table("inventario_esd").select("created_at, estatus_operativo").execute()
                        df_inv_mov = pd.DataFrame(resp_inv_mov.data)
                        if not df_inv_mov.empty:
                            bajas_inv_total = len(df_inv_mov[df_inv_mov['estatus_operativo'].astype(str).str.upper() == 'NO OPERATIVO'])
                            if 'created_at' in df_inv_mov.columns:
                                df_inv_mov['created_at'] = pd.to_datetime(df_inv_mov['created_at'], format='ISO8601', errors='coerce', utc=True).dt.tz_localize(None)
                                altas_inv_30d = len(df_inv_mov[df_inv_mov['created_at'] >= hace_30_dias])

                        # I.2 Movimientos en Maquinaria
                        if not df_maq_ov.empty:
                            resp_maq_todas = supabase.table("mediciones_maquinaria").select("id_maquinaria, status_operativo, fecha_medicion").execute()
                            df_maq_todas = pd.DataFrame(resp_maq_todas.data)
                            
                            if not df_maq_todas.empty:
                                bajas_maq_total = len(df_maq_todas[df_maq_todas['status_operativo'].astype(str).str.upper() == 'NO OPERATIVO'])
                                df_maq_altas = df_maq_todas.sort_values('fecha_medicion', ascending=True).drop_duplicates(subset=['id_maquinaria'], keep='first')
                                df_maq_altas['fecha_medicion'] = pd.to_datetime(df_maq_altas['fecha_medicion'], format='ISO8601', errors='coerce', utc=True).dt.tz_localize(None)
                                altas_maq_30d = len(df_maq_altas[df_maq_altas['fecha_medicion'] >= hace_30_dias])

                    except Exception as e_mov:
                        st.toast(f"Aviso: No se pudieron cargar las métricas de expansión ({e_mov})")

                except Exception as e:
                    st.error(f"Error cargando datos para el overview: {e}")
                    df_maq_ov = pd.DataFrame(); df_tierras_ov = pd.DataFrame(); df_em_ov = pd.DataFrame(); df_chec_ov = pd.DataFrame()
                    total_materiales_validados = 0; total_certificados = 0; min_sensibilidad = "N/D"; alerta_sensibilidad = False
                    altas_inv_30d = 0; bajas_inv_total = 0; altas_maq_30d = 0; bajas_maq_total = 0

                # Inventario General (Mobiliario, Ionizadores, Monitores, Pisos)
                df_inv_ov = pd.DataFrame()
                if 'df_inv_full' in locals() and df_inv_full is not None and not df_inv_full.empty:
                    df_inv_ov = df_inv_full[df_inv_full['Estatus operativo'].astype(str).str.upper() != 'NO OPERATIVO'].copy()
                    
                # Maquinaria (Filtramos las operativas)
                if not df_maq_ov.empty:
                    df_maq_ov = df_maq_ov[df_maq_ov['status_operativo'].astype(str).str.upper() != 'NO OPERATIVO'].copy()

                # --- 2. CÁLCULO DE MÉTRICAS GLOBALES Y ACTIVIDAD ---
                fechas_limpias = pd.to_datetime(fechas_actividad, format='ISO8601', errors='coerce', utc=True).tz_localize(None)
                hoy = pd.Timestamp.utcnow().tz_localize(None)
                dias_diff = (hoy - fechas_limpias).days
                
                act_7d = (dias_diff <= 7).sum()
                act_30d = (dias_diff <= 30).sum()
                act_60d = (dias_diff <= 60).sum()

                # Las llamadas ahora funcionan perfecto
                vig_inv, ven_inv, pen_inv = contar_estatus(df_inv_ov, 'Estatus de verificación', 'VIGENTE|APROBADO|PASA', 'VENCIDO|FALLA|RECHAZADO')
                vig_maq, ven_maq, pen_maq = contar_estatus(df_maq_ov, 'resultado_estatus', 'VIGENTE|APROBADO|PASA', 'VENCIDO|FALLA|RECHAZADO')
                
                pasa_em, falla_em, _ = contar_estatus(df_em_ov, 'estatus_verificacion', 'APROBADO', 'RECHAZADO')
                pasa_ch, falla_ch, _ = contar_estatus(df_chec_ov, 'estatus', 'PASA', 'FALLA')

                total_activos = len(df_inv_ov) + len(df_maq_ov)
                total_vigentes = vig_inv + vig_maq
                total_vencidos = ven_inv + ven_maq
                total_pendientes = pen_inv + pen_maq

                cumplimiento_global = (total_vigentes / total_activos * 100) if total_activos > 0 else 100.0

            # --- 3. RENDERIZADO VISUAL ---
            st.markdown("##### 📈 Índice de Cumplimiento Global (Infraestructura y Activos)")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Cumplimiento General", f"{cumplimiento_global:.1f}%", f"{-total_vencidos} Vencidos" if total_vencidos > 0 else "Óptimo", delta_color="inverse" if total_vencidos > 0 else "normal")
            kpi2.metric("🟢 Activos Vigentes", total_vigentes)
            kpi3.metric("🔴 Activos Vencidos", total_vencidos)
            kpi4.metric("🟡 Pendientes / N/D", total_pendientes)

            st.divider()
            
            st.markdown("##### 🏆 Desempeño, Calificación y Carga de Trabajo")
            c_perf1, c_perf2, c_perf3, c_perf4 = st.columns(4)
            c_perf1.metric("📦 Materiales Validados", total_materiales_validados, "En Sistema", delta_color="off")
            c_perf2.metric("📑 Certificados de Cal.", total_certificados, "Documentados", delta_color="off")
            c_perf3.metric("⚡ Sensibilidad Mín. Planta", min_sensibilidad, "Riesgo Alto" if alerta_sensibilidad else "Riesgo Controlado", delta_color="inverse" if alerta_sensibilidad else "normal")
            c_perf4.metric("🔥 Validaciones (Últimos 7d)", act_7d, "Actualizaciones", delta_color="normal")

            st.caption("Tendencia de Auditorías a Mediano Plazo")
            st.progress(min(act_30d / 500, 1.0) if act_30d > 0 else 0.0, text=f"Últimos 30 días: {act_30d} actualizaciones / mediciones")
            st.progress(min(act_60d / 1000, 1.0) if act_60d > 0 else 0.0, text=f"Últimos 60 días: {act_60d} actualizaciones / mediciones")

            st.divider()
            
            st.markdown("##### 🔄 Movimientos de Inventario y Expansión")
            c_mov1, c_mov2, c_mov3, c_mov4 = st.columns(4)
            c_mov1.metric("Altas Inventario (30d)", altas_inv_30d, "Mobiliario / Otros", delta_color="normal")
            c_mov2.metric("Bajas Inventario", bajas_inv_total, "Desactivados históricamente", delta_color="inverse")
            c_mov3.metric("Altas Maquinaria (30d)", altas_maq_30d, "Nuevas estaciones", delta_color="normal")
            c_mov4.metric("Bajas Maquinaria", bajas_maq_total, "Desactivadas históricamente", delta_color="inverse")

            st.divider()

            col_graf, col_metricas = st.columns([1.5, 1])

            with col_graf:
                st.markdown("**Distribución de Estado (Inventario y Maquinaria)**")
                if total_activos > 0:
                    df_pie = pd.DataFrame({
                        "Estado": ["Vigente", "Vencido", "Pendiente"],
                        "Cantidad": [total_vigentes, total_vencidos, total_pendientes]
                    })
                    df_pie = df_pie[df_pie["Cantidad"] > 0]
                    
                    fig = px.pie(df_pie, values='Cantidad', names='Estado', color='Estado',
                                 color_discrete_map={"Vigente": "#28a745", "Vencido": "#dc3545", "Pendiente": "#ffc107"},
                                 hole=0.45)
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No hay datos de activos para graficar.")

            with col_metricas:
                st.markdown("**Últimas Pruebas de Infraestructura**")
                
                st.markdown(f"**🌍 Tierras y Conexiones:**")
                st.progress(pasa_t / (pasa_t + falla_t) if (pasa_t + falla_t) > 0 else 0.0, text=f"✅ {pasa_t} Pasan | ❌ {falla_t} Fallan")
                
                st.markdown(f"**⚡ Event Meter (Descargas):**")
                st.progress(pasa_em / (pasa_em + falla_em) if (pasa_em + falla_em) > 0 else 0.0, text=f"✅ {pasa_em} Aprobados | ❌ {falla_em} Rechazados")
                
                st.markdown(f"**🛂 Checadores de Calzado:**")
                st.progress(pasa_ch / (pasa_ch + falla_ch) if (pasa_ch + falla_ch) > 0 else 0.0, text=f"✅ {pasa_ch} Pasan | ❌ {falla_ch} Fallan")

            st.divider()

            # --- 4. ALERTAS DE ACCIÓN INMEDIATA ---
            st.markdown("##### 🚨 Alertas Requieren Acción Inmediata")
            
            alertas = []
            if not df_inv_ov.empty:
                ven_df = df_inv_ov[df_inv_ov['Estatus de verificación'].astype(str).str.upper().str.contains('VENCIDO|FALLA|RECHAZADO', regex=True)]
                for _, r in ven_df.iterrows():
                    cat = str(r.get('Categoría', 'Inventario'))
                    alertas.append({"Área": cat, "ID / Ubicación": f"{r.get('Id de producto')} ({r.get('Línea')})", "Problema": "Verificación Vencida"})
                    
            if not df_maq_ov.empty:
                ven_m_df = df_maq_ov[df_maq_ov['resultado_estatus'].astype(str).str.upper().str.contains('VENCIDO|FALLA|RECHAZADO', regex=True)]
                for _, r in ven_m_df.iterrows():
                    alertas.append({"Área": "Maquinaria", "ID / Ubicación": str(r.get('id_maquinaria')), "Problema": "Verificación Vencida"})
                    
            if not df_tierras_ov.empty:
                # 🛠️ CORRECCIÓN: Filtro robusto para detectar fallas sin importar el sinónimo
                fallas_t_df = df_tierras_ov[df_tierras_ov['estatus'].astype(str).str.upper().str.contains('VENCIDO|FALLA|RECHAZADO|NO CUMPLE', regex=True)]
                for _, r in fallas_t_df.iterrows():
                    alertas.append({"Área": "Tierras / Conexiones", "ID / Ubicación": str(r.get('id_punto')), "Problema": "Falla en Resistencia (Excede Límite)"})
                    
            if not df_chec_ov.empty:
                fallas_ch_df = df_chec_ov[df_chec_ov['estatus'].astype(str).str.upper() == 'FALLA']
                for _, r in fallas_ch_df.iterrows():
                    alertas.append({"Área": "Checadores de Ingreso", "ID / Ubicación": str(r.get('id_checador')), "Problema": "Desviación fuera de límite (>5%)"})

            if alertas:
                df_alertas = pd.DataFrame(alertas)
                st.dataframe(df_alertas, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 ¡Excelente trabajo! No hay activos vencidos ni fallas operativas recientes reportadas en la infraestructura.")
    #######################
    ### 4Q dashboard
    #######################
    
    with tab_4q:
        st.markdown("#### 📊 Dashboard 4Q - Sistema de Hallazgos y Auditorías")
        st.info("Sube el archivo CSV de hallazgos para actualizar la base de datos. El tablero siempre muestra la información histórica guardada en la nube.")

        # 1. MÓDULO DE ACTUALIZACIÓN (CARGA DE CSV)
        with st.expander("📥 Actualizar Base de Datos (Subir CSV)"):
            archivo_hallazgos = st.file_uploader("Subir archivo de Hallazgos de EASE (.csv)", type=["csv"], key="file_4q")

            if archivo_hallazgos:
                with st.spinner("Procesando, limpiando y sincronizando con la nube..."):
                    try:
                        df_new = pd.read_csv(archivo_hallazgos)
                        # Estandarizamos las columnas
                        df_new.columns = [str(c).strip() for c in df_new.columns]

                        if 'ID' not in df_new.columns:
                            st.error("❌ El archivo no contiene la columna 'ID' requerida para el cruce de datos.")
                        else:
                            # Ignorar Assessment description con "QMS"
                            if 'Assessment Description' in df_new.columns:
                                df_new = df_new[~df_new['Assessment Description'].astype(str).str.contains('QMS', case=False, na=False)]

                            # Asegurar y limpiar el ID principal
                            df_new = df_new.dropna(subset=['ID'])
                            df_new['ID'] = df_new['ID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

                            # Convertimos a diccionario crudo
                            records_raw = df_new.to_dict('records')
                            
                            # Limpieza absoluta de NaN a None para compatibilidad con JSON/Supabase
                            clean_records = []
                            for row in records_raw:
                                clean_row = {}
                                for key, val in row.items():
                                    if pd.isna(val):
                                        clean_row[key] = None
                                    else:
                                        clean_row[key] = val
                                clean_records.append(clean_row)

                            # Actualizamos en Supabase
                            supabase.table("hallazgos_4q").upsert(clean_records).execute()
                            
                            st.success(f"✅ ¡{len(df_new)} hallazgos sincronizados correctamente!")
                            time.sleep(1.5)
                            st.rerun() # Recargamos la página para que la gráfica de abajo tome los datos nuevos

                    except Exception as e:
                        st.error(f"Ocurrió un error al procesar el archivo: {e}")

        # 2. EXTRACCIÓN DE DATOS DESDE SUPABASE (SIEMPRE VISIBLE)
        try:
            # Traemos todo el histórico guardado
            resp_4q = supabase.table("hallazgos_4q").select("*").execute()
            df_4q_db = pd.DataFrame(resp_4q.data)
        except Exception as e:
            df_4q_db = pd.DataFrame()
            st.error(f"No se pudo conectar con la base de datos 4Q: {e}")

        # 3. RENDERIZADO DEL DASHBOARD
        if not df_4q_db.empty:
            st.divider()
            
            # --- CÁLCULO DE MÉTRICAS GLOBALES ---
            total_hallazgos = len(df_4q_db)
            estatus_col = 'Status' if 'Status' in df_4q_db.columns else ('Estatus' if 'Estatus' in df_4q_db.columns else None)
            
            if estatus_col:
                # 1. Identificar todos los que YA están cerrados/completados
                mask_cerrados = df_4q_db[estatus_col].astype(str).str.contains('Completed|Closed|Cerrado', case=False, na=False)
                cerrados = df_4q_db[mask_cerrados]
                
                # 2. Todo lo que NO está cerrado, está abierto (En Proceso)
                abiertos = df_4q_db[~mask_cerrados]
                
                # 3. De los abiertos, separamos los vencidos y los que van a tiempo
                mask_vencidos = abiertos[estatus_col].astype(str).str.contains('Past Due|Vencido', case=False, na=False)
                vencidos_activos = abiertos[mask_vencidos]
                en_proceso_on_time = abiertos[~mask_vencidos]
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total de Hallazgos", total_hallazgos)
                m2.metric("🟢 Completados / Cerrados", len(cerrados))
                m3.metric("🟡 En Proceso / On Time", len(en_proceso_on_time))
                m4.metric("🔴 Vencidos Activos (Past Due)", len(vencidos_activos), delta="Requieren Acción", delta_color="inverse" if len(vencidos_activos) > 0 else "normal")

            st.divider()

            # --- GRÁFICOS INTERACTIVOS ---
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                if estatus_col:
                    df_status = df_4q_db[estatus_col].value_counts().reset_index()
                    df_status.columns = ['Estatus', 'Cantidad']
                    fig_status = px.pie(df_status, values='Cantidad', names='Estatus', title="Distribución por Estatus", hole=0.45)
                    fig_status.update_layout(margin=dict(t=30, b=10, l=10, r=10))
                    st.plotly_chart(fig_status, use_container_width=True)

            with col_chart2:
                # Pareto de problemas
                cat_col = 'Question Title' if 'Question Title' in df_4q_db.columns else ('Location' if 'Location' in df_4q_db.columns else None)
                if cat_col:
                    df_cat = df_4q_db[cat_col].value_counts().head(10).reset_index()
                    df_cat.columns = ['Tipo de Hallazgo', 'Ocurrencias']
                    fig_pareto = px.bar(df_cat, x='Ocurrencias', y='Tipo de Hallazgo', orientation='h', title=f"Top 10 Hallazgos ({cat_col})", text_auto=True)
                    fig_pareto.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=30, b=10, l=10, r=10))
                    st.plotly_chart(fig_pareto, use_container_width=True)

            # --- TABLA DE DATOS INTERACTIVA ---
            st.markdown("##### 📋 Directorio y Seguimiento de Hallazgos")
            
            # Filtro ágil para la tabla
            if estatus_col:
                filtro_estatus = st.selectbox("Filtrar directorio por estatus:", options=["Todos"] + sorted(df_4q_db[estatus_col].dropna().unique()))
                df_mostrar = df_4q_db.copy()
                if filtro_estatus != "Todos":
                    df_mostrar = df_mostrar[df_mostrar[estatus_col] == filtro_estatus]
            else:
                df_mostrar = df_4q_db.copy()
                
            # Mostramos un dataframe estilizado seleccionando columnas clave si existen
            cols_clave = [c for c in ['ID', 'Status', 'Location', 'Question Title', 'Responsible Party', 'Finding Comment', 'Days Open'] if c in df_mostrar.columns]
            if cols_clave:
                df_mostrar = df_mostrar[cols_clave]
                
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
        else:
            st.info("La base de datos 4Q está vacía. Despliega el menú de arriba para subir tu primer archivo CSV.")
# ==========================================
# VISTA 2: ESCÁNER Y DETALLES
# ==========================================
elif st.session_state.vista_actual == "Escáner":
    id_escaneado_url = st.query_params.get("qr_id", "")
    
    # --- CONTROL DE PESTAÑAS MAESTRO (Evita el reinicio visual) ---
    if "sub_pestana_escaner" not in st.session_state:
        st.session_state.sub_pestana_escaner = "📷 Escáner QR / Manual"
        
    if id_escaneado_url:
        st.session_state.sub_pestana_escaner = "📷 Escáner QR / Manual"
        
    # Renderizamos un selector horizontal que actúa como pestañas persistentes
    opcion_pestana = st.radio(
        "Navegación Interna:", 
        ["📷 Escáner QR / Manual", "🚨 Próximos a Vencer"], 
        horizontal=True, 
        label_visibility="collapsed",
        key="sub_pestana_escaner_radio"
    )
    st.session_state.sub_pestana_escaner = opcion_pestana
    
    id_limpio = None

    # --- PESTAÑA 1: ESCÁNER ---
    if st.session_state.sub_pestana_escaner == "📷 Escáner QR / Manual":
        if not id_escaneado_url:
            st.markdown("### 📷 Apunta al Código QR")
            html_code_qr = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader_main" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc; background-color: #f9f9f9;"></div>
            
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
                <button type="button" id="cam_wide_main" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
                <button type="button" id="cam_cycle_main" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
            </div>
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
                <button type="button" id="zoom_1x_main" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
                <button type="button" id="zoom_3x_main" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
            </div>
            <p id="cam-status-main" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
            
            <script>
            let html5QrCodeMain;
            let rearCamsMain = [];
            let currentIdxMain = 0;
            let wideIdMain = null;
    
            function applyZoomMain(scale) {
                const vid = document.querySelector("#reader_main video");
                if (vid) {
                    vid.style.transform = `scale(${scale})`;
                    vid.style.transformOrigin = "center center";
                }
                document.getElementById('zoom_1x_main').style.background = (scale === 1) ? "#0052cc" : "#666";
                document.getElementById('zoom_3x_main').style.background = (scale === 3) ? "#0052cc" : "#666";
            }
    
            function startScannerMain(camId) {
                if(!html5QrCodeMain) html5QrCodeMain = new Html5Qrcode("reader_main");
                if (html5QrCodeMain.isScanning) {
                    html5QrCodeMain.stop().then(() => { runScanMain(camId); }).catch(e => console.log(e));
                } else {
                    runScanMain(camId);
                }
            }
    
            function runScanMain(camId) {
                html5QrCodeMain.start(
                    camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCodeMain.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_id", decodedText);
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    }, (err) => {} 
                ).then(() => { 
                    let activeCam = rearCamsMain.find(c => c.id === camId);
                    document.getElementById("cam-status-main").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                    applyZoomMain(1);
                }).catch(err => {
                    document.getElementById("cam-status-main").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
                });
            }
    
            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    rearCamsMain = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                    if(rearCamsMain.length === 0) rearCamsMain = devices;
    
                    wideIdMain = rearCamsMain[0].id;
                    for (let c of rearCamsMain) {
                        let lbl = c.label.toLowerCase();
                        if (lbl.includes('wide') && !lbl.includes('ultra')) {
                            wideIdMain = c.id; break;
                        }
                    }
    
                    currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                    if(currentIdxMain === -1) currentIdxMain = 0;
    
                    startScannerMain(wideIdMain);
    
                    document.getElementById('cam_wide_main').addEventListener('click', () => {
                        currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                        startScannerMain(wideIdMain);
                    });
    
                    document.getElementById('cam_cycle_main').addEventListener('click', () => {
                        currentIdxMain = (currentIdxMain + 1) % rearCamsMain.length;
                        startScannerMain(rearCamsMain[currentIdxMain].id);
                    });
    
                    document.getElementById('zoom_1x_main').addEventListener('click', () => applyZoomMain(1));
                    document.getElementById('zoom_3x_main').addEventListener('click', () => applyZoomMain(3));
                }
            }).catch(err => { document.getElementById("cam-status-main").innerText = "Permisos de cámara denegados."; });
            </script>
            """
            components.html(html_code_qr, height=750) 
            
            id_manual = st.text_input("O ingresa el ID manual:", key="input_manual")
            if id_manual:
                st.query_params["qr_id"] = id_manual
                st.rerun()
        else:
            colA, colB = st.columns([0.8, 0.2])
            with colA: st.info(f"🔍 **ID Escaneado:** {id_escaneado_url}")
            with colB:
                if st.button("❌ Cerrar Escáner", use_container_width=True):
                    limpiar_url_escaneo()
                    st.rerun()
            
            id_limpio = str(id_escaneado_url).strip().upper()

    # --- PESTAÑA 2: EQUIPOS POR VENCER ---
    elif st.session_state.sub_pestana_escaner == "🚨 Próximos a Vencer":
        st.markdown("#### 🚨 Equipos Vencidos o por Vencer (7 días)")
        st.info("Haz clic en cualquier fila de la tabla para auditar ese equipo. El formulario se abrirá automáticamente aquí abajo.")
        
        try:
            resp_vencidos = supabase.table("v_equipos_por_vencer").select("*").execute()
            df_vencidos = pd.DataFrame(resp_vencidos.data)
        except Exception as e:
            df_vencidos = pd.DataFrame()
            st.error(f"Error al cargar la tabla: {e}")
            
        if not df_vencidos.empty:
            col_id = next((c for c in df_vencidos.columns if 'id' in c.lower()), df_vencidos.columns[0])
            
            evento_tabla = st.dataframe(
                df_vencidos, 
                use_container_width=True, 
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            
            if len(evento_tabla.selection.rows) > 0:
                fila_idx = evento_tabla.selection.rows[0]
                id_seleccionado = str(df_vencidos.iloc[fila_idx][col_id]).strip().upper()
                id_limpio = id_seleccionado
                
                st.divider()
                st.markdown(f"📋 **Auditando Equipo Seleccionado:** `{id_limpio}`")
        else:
            st.success("🎉 ¡Excelente! No hay equipos vencidos ni próximos a vencer.")

    # ==========================================
    # LÓGICA DE AUDITORÍA UNIFICADA (Aparece abajo de la pestaña activa)
    # ==========================================
    if id_limpio:
        # Asegúrate de mantener la sangría (indentación) de un nivel (Tab)
        # para todo el bloque masivo de formularios que sigue aquí abajo:
        id_limpio = str(id_limpio).strip().upper()
        
        # 1. Extraemos las listas de IDs limpios de las tres categorías de inventario
        mob_ids_limpios = df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
        ion_ids_limpios = df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
        mon_ids_limpios = df_mon_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()

        # --- NUEVO: Búsqueda en tabla de Maquinaria ---
        try:
            resp_maq_scan = supabase.table("mediciones_maquinaria").select("*").eq("id_maquinaria", id_limpio).order("fecha_medicion", desc=True).execute()
            df_maq_scan = pd.DataFrame(resp_maq_scan.data)
            es_maq = not df_maq_scan.empty
        except:
            df_maq_scan = pd.DataFrame()
            es_maq = False
        # ----------------------------------------------

        # 2. Banderas de coincidencia
        es_mob = id_limpio in mob_ids_limpios.values
        es_ion = id_limpio in ion_ids_limpios.values
        es_mon = id_limpio in mon_ids_limpios.values

        # 3. Validamos si existe en cualquiera de las 4 tablas
        if es_mob or es_ion or es_mon or es_maq:
            
            # ==========================================
            # LÓGICA DE VISUALIZACIÓN: INVENTARIO GENERAL
            # ==========================================
            if es_mob or es_ion or es_mon:
                if es_mob:
                    df_actual = df_mob_local
                    serie_busqueda = mob_ids_limpios
                elif es_ion:
                    df_actual = df_ion_local
                    serie_busqueda = ion_ids_limpios
                else:
                    df_actual = df_mon_local
                    serie_busqueda = mon_ids_limpios
                idx = serie_busqueda[serie_busqueda == id_limpio].index[0]
                equipo = df_actual.loc[idx]
                
                estatus_op = str(equipo.get('Estatus operativo', '')).strip().upper()
                estatus_verif = str(equipo.get('Estatus de verificación', 'N/A')).strip().upper()
                
                # --- NUEVA LÓGICA DE ESTATUS VISUAL ---
                if estatus_op == "NO OPERATIVO":
                    estatus_mostrar = "🔴 NO OPERATIVO"
                else:
                    estatus_mostrar = estatus_verif
                
                texto_check = "✅ REACTIVAR" if estatus_op == "NO OPERATIVO" else "✅ Registrar medición"

               # === COMIENZA REEMPLAZO: AJUSTE DE LECTURA Y ESTATUS DINÁMICO ===
                id_exacto_db = str(equipo.get('Id de producto', id_limpio))

                # 1. Consultar de forma segura las fechas usando el ID exacto y literal de la base de datos
                try:
                    resp_fechas = supabase.table("inventario_esd").select("fecha_ultima_verif, fecha_proxima_verif").eq("id_producto", id_exacto_db).execute()
                    if resp_fechas.data:
                        f_val_sql = resp_fechas.data[0].get('fecha_ultima_verif')
                        f_venc_sql = resp_fechas.data[0].get('fecha_proxima_verif')
                    else:
                        f_val_sql, f_venc_sql = None, None
                except Exception as e:
                    f_val_sql, f_venc_sql = "Error", "Error"

                # 2. Calcular el Estatus de Inspección real en tiempo real (Python gobierna la visualización)
                from datetime import datetime, date
                estatus_op = str(equipo.get('Estatus operativo', '')).strip().upper()

                if estatus_op == "NO OPERATIVO":
                    estatus_real = "NO OPERATIVO"
                    color_estatus = "red"
                elif f_venc_sql and str(f_venc_sql).lower() not in ['n/a', 'none', 'nan', '']:
                    try:
                        fecha_vencimiento = datetime.strptime(str(f_venc_sql)[:10], '%Y-%m-%d').date()
                        fecha_val_date = datetime.strptime(str(f_val_sql)[:10], '%Y-%m-%d').date() if f_val_sql else None
                        hoy = date.today()

                        if fecha_val_date and fecha_val_date > hoy:
                            estatus_real = "ERROR: FECHA FUTURA"
                            color_estatus = "orange"
                        elif fecha_vencimiento < hoy:
                            estatus_real = "VENCIDO"
                            color_estatus = "red"
                        else:
                            estatus_real = "VIGENTE"
                            color_estatus = "green"
                    except ValueError:
                        estatus_real = "ERROR FORMATO"
                        color_estatus = "orange"
                else:
                    estatus_real = "PENDIENTE"
                    color_estatus = "orange"

                # 3. Despliegue de los paneles métricos unificados
                st.markdown(f"### 📊 Detalles del Equipo")
                c_linea, c_tipo, c_estatus = st.columns(3)
                c_linea.metric("Ubicación", str(equipo.get('Línea', 'N/A')))
                clasificacion_equipo = str(equipo.get('Clasificación', 'N/A'))
                c_tipo.metric("Clasificación", clasificacion_equipo)
                
                # Despliegue estilizado de estatus usando notación nativa de color de Streamlit
                c_estatus.markdown(f"**Estatus Real:**\n## :{color_estatus}[{estatus_real}]")
                
                c_val, c_bal = st.columns(2)
                val_previo = equipo.get('Valor de verificación', 0)
                if es_ion:
                    c_val.metric("Descarga", f"{float(val_previo):.2f} s" if pd.notna(val_previo) else "N/A")
                    bal_previo = equipo.get('Balance')
                    if pd.notna(bal_previo) and str(bal_previo).strip() not in ['', 'N/A', 'nan', 'None']:
                        c_bal.metric("Balance", f"{float(bal_previo):.2f} V")
                    else:
                        c_bal.metric("Balance", "N/A")
                else:
                    c_val.metric("Resistencia", f"{float(val_previo):.2E} Ω" if pd.notna(val_previo) else "N/A")

                c_fval, c_fvenc = st.columns(2)
                c_fval.metric("Fecha de Última Validación", str(f_val_sql)[:10] if f_val_sql else "N/A")
                c_fvenc.metric("Fecha de Próximo Vencimiento", str(f_venc_sql)[:10] if f_venc_sql else "N/A")
                
                if estatus_real == "VENCIDO":
                    st.error("⚠️ Alerta de Calidad: Este elemento ha excedido su periodo de vigencia y requiere validación inmediata.")
                #### TERMINA CAMBIO DE VENCIMIENTOS ACTUALIZADOS 6/24/2026
                
                with st.expander("🕰️ Consultar Historial de Mediciones Anteriores"):
                    try:
                        resp_hist = supabase.table("historial_mediciones").select("*").eq("id_equipo", id_limpio).order("fecha_modificacion", desc=True).execute()
                        df_historial = pd.DataFrame(resp_hist.data)
                        if not df_historial.empty:
                            
                            # --- NUEVO: FORMATEO DINÁMICO ---
                            def formatear_valor_historial(val, es_ionizador):
                                try:
                                    v = float(val)
                                    if es_ionizador:
                                        return f"{v:.2f}" # Ionizadores se miden en segundos (números pequeños)
                                    else:
                                        return f"{v:.2e}" # Resistencias en notación científica estricta
                                except:
                                    return "N/D"

                            if es_ion and 'balance_ionizador' in df_historial.columns:
                                df_historial = df_historial[['fecha_modificacion', 'valor_actual', 'balance_ionizador', 'fecha_validacion', 'ubicacion', 'auditor']]
                                df_historial.columns = ['Actualizado el', 'T. Descarga (s)', 'Balance (V)', 'Fecha Val.', 'Ubicación', 'Auditor']
                                df_historial['T. Descarga (s)'] = df_historial['T. Descarga (s)'].apply(lambda x: formatear_valor_historial(x, True))
                            else:
                                df_historial = df_historial[['fecha_modificacion', 'valor_actual', 'fecha_validacion', 'ubicacion', 'auditor']]
                                df_historial.columns = ['Actualizado el', 'Valor', 'Fecha Val.', 'Ubicación', 'Auditor']
                                df_historial['Valor'] = df_historial['Valor'].apply(lambda x: formatear_valor_historial(x, False))
                            
                            # Formateo limpio de la fecha de actualización
                            df_historial['Actualizado el'] = pd.to_datetime(df_historial['Actualizado el'], errors='coerce').dt.strftime('%d-%b-%Y %H:%M')
                            
                            st.dataframe(df_historial, use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay mediciones históricas registradas para este equipo aún.")
                    except Exception as e:
                        st.error(f"Error al cargar el historial: {e}")

                st.divider()

                if not st.session_state.modo_lectura:
                    hacer_medicion = st.checkbox(texto_check)
                    if hacer_medicion:
                        with st.form("form_actualizacion"):
                            # --- NUEVO: SELECTOR DINÁMICO DE CLASIFICACIÓN ---
                            clasif_disp = sorted([str(x).strip() for x in df_actual.get('Clasificación', pd.Series()).unique() if pd.notna(x) and str(x).strip() != ''])
                            if clasificacion_equipo and clasificacion_equipo not in clasif_disp:
                                clasif_disp = [clasificacion_equipo] + clasif_disp
                            if not clasif_disp: 
                                clasif_disp = ["Mesa", "Silla", "Carrito", "Rack", "Tapete", "Otro"] # Respaldo seguro
                                
                            idx_c = clasif_disp.index(clasificacion_equipo) if clasificacion_equipo in clasif_disp else 0
                            nueva_clasif_upd = st.selectbox("Clasificación (Tipo de Equipo)", options=clasif_disp, index=idx_c)
                            # ------------------------------------------------
                            
                            # --- 1. LÍNEA POR DEFECTO ASEGURADA ---
                            if 'obtener_catalogo_lineas' in globals():
                                lineas_opc = obtener_catalogo_lineas()
                            else:
                                lineas_opc = sorted([str(x).strip() for x in df_mob_local['Línea'].dropna().unique()])
                                
                            ub_actual = str(equipo.get('Línea', '')).strip()
                            
                            # Si la ubicación actual no está en la lista del catálogo, la inyectamos para no perder la referencia visual
                            if ub_actual and ub_actual not in lineas_opc:
                                lineas_opc = [ub_actual] + lineas_opc
                                
                            idx_l = lineas_opc.index(ub_actual) if ub_actual in lineas_opc else 0
                            nueva_linea_upd = st.selectbox("Línea / Ubicación", options=lineas_opc, index=idx_l)
                            
                            # --- 2. CAMPOS VACÍOS (value=None) ---
                            if es_ion:
                                c_ion1, c_ion2 = st.columns(2)
                                v_act = c_ion1.number_input("Descarga (s)", value=None, format="%.2f", placeholder="0.0")
                                bal_act = c_ion2.number_input("Balance (V)", value=None, format="%.2f", placeholder="0.0")
                            else:
                                c_b, c_e = st.columns(2)
                                base_upd = c_b.number_input("Base (Ohms)", value=None, placeholder="Ej: 3.5")
                                exp_upd = c_e.number_input("Exponente", value=None, step=1, placeholder="Ej: 6")
                                
                            fecha_hoy = datetime.today().date()
                            nueva_fecha = st.date_input("Fecha de Validación", fecha_hoy)
                            
                            if st.form_submit_button("💾 Guardar Actualización e Historial"):
                                # --- 3. VALIDACIÓN DE CAMPOS ---
                                if es_ion and (v_act is None or bal_act is None):
                                    st.error("⚠️ Debes ingresar los valores de Descarga y Balance.")
                                elif not es_ion and (base_upd is None or exp_upd is None):
                                    st.error("⚠️ Debes ingresar los valores de Base y Exponente.")
                                else:
                                    with st.spinner("Guardando registro..."):
                                        if es_ion:
                                            nuevo_valor_final = float(v_act)
                                            bal_act = float(bal_act)
                                        else:
                                            nuevo_valor_final = float(base_upd) * (10 ** int(exp_upd))
                                            bal_act = None
                                            
                                        freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                        proxy = calcular_proxima_fecha(nueva_fecha, freq)
                                        
                                        try:
                                            # --- 4. GUARDAR EL ESTADO ANTERIOR EN LA TABLA HISTORIAL ---
                                            val_previo_hist = str(equipo.get('Valor de verificación', 0))
                                            ubicacion_previa = str(equipo.get('Línea', 'N/D'))
                                            auditor_previo = str(equipo.get('Auditor', st.session_state.usuario_nombre))
                                            
                                            if f_val_sql != 'N/A' and f_val_sql != 'Error':
                                                historial_data = {
                                                    "id_equipo": id_limpio,
                                                    "tipo_equipo": clasificacion_equipo, # Aquí guardamos lo que era antes
                                                    "ubicacion": ubicacion_previa,
                                                    "valor_actual": val_previo_hist,
                                                    "fecha_validacion": f_val_sql,
                                                    "fecha_vencimiento": f_venc_sql if f_venc_sql != 'N/A' else None,
                                                    "auditor": auditor_previo,
                                                    "fecha_modificacion": datetime.now().isoformat()
                                                }
                                                if es_ion:
                                                    historial_data["balance_ionizador"] = str(equipo.get('Balance', 0))
                                                    
                                                supabase.table("historial_mediciones").insert(historial_data).execute()

                                            # --- 5. ACTUALIZAR EL ESTADO NUEVO EN INVENTARIO MAESTRO ---
                                            update_data = {
                                                "clasificacion": nueva_clasif_upd,
                                                "linea_ubicacion": nueva_linea_upd,
                                                "valor_actual": float(nuevo_valor_final),
                                                "fecha_ultima_verif": nueva_fecha.isoformat(),
                                                "fecha_proxima_verif": proxy.isoformat(),
                                                "estatus_verificacion": "VIGENTE",
                                                "estatus_operativo": "OPERATIVO",
                                                "auditor_responsable": st.session_state.usuario_nombre,
                                            }
                                            if es_ion:
                                                update_data["balance_ionizador"] = float(bal_act)
                                            
                                            # --- EL TRUCO ESTÁ AQUÍ: Extraer el ID literal de la base de datos ---
                                            id_exacto_db = str(equipo.get('Id de producto', id_limpio))
                                            
                                            res_upd = supabase.table("inventario_esd").update(update_data).eq("id_producto", id_exacto_db).execute()
                                            
                                            # Verificación de seguridad: ¿Se actualizó realmente alguna fila?
                                            if len(res_upd.data) == 0:
                                                st.error(f"❌ Fallo silencioso evitado: El ID '{id_exacto_db}' tiene un formato especial (minúsculas o espacios) en la base de datos que impidió la actualización. Búscalo en la pestaña de Alta/Baja para corregirlo.")
                                            else:
                                                st.success("💾 ¡Equipo actualizado exitosamente!")
                                                st.cache_data.clear()
                                                limpiar_url_escaneo()
                                                time.sleep(1.5)
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error actualizando el equipo en SQL: {e}")
                # --- NUEVO: LISTADO DE OTROS EQUIPOS EN LA MISMA LÍNEA ---
                if es_mob:
                    ub_actual_lista = str(equipo.get('Línea', '')).strip()
                    if ub_actual_lista and ub_actual_lista != 'N/A' and 'df_inv_full' in locals() and not df_inv_full.empty:
                        st.divider()
                        st.markdown(f"#### 📍 Otros equipos en la línea: `{ub_actual_lista}`")
                        
                        # Filtramos el inventario por la misma línea, quitamos el equipo actual y los que estén dados de baja
                        df_otros = df_inv_full[
                            (df_inv_full['Línea'].astype(str).str.strip() == ub_actual_lista) & 
                            (df_inv_full['Id de producto'].astype(str).str.strip().str.upper() != id_limpio) &
                            (df_inv_full['Estatus operativo'].astype(str).str.strip().str.upper() != 'NO OPERATIVO')
                        ]
                        
                        if not df_otros.empty:
                            # Seleccionamos columnas clave para mostrar
                            df_mostrar_otros = df_otros[['Id de producto', 'Clasificación', 'Estatus de verificación', 'Fecha de próxima verificación']].copy()
                            df_mostrar_otros = df_mostrar_otros.rename(columns={
                                'Id de producto': 'ID Equipo', 
                                'Fecha de próxima verificación': 'Vencimiento'
                            })
                            
                            # Formateamos la fecha visualmente para que sea corta
                            df_mostrar_otros['Vencimiento'] = pd.to_datetime(df_mostrar_otros['Vencimiento'], errors='coerce').dt.strftime('%d-%b-%Y').fillna('N/D')
                            
                            # Agregamos emojis de estatus rápido
                            def emoji_estatus(val):
                                v = str(val).upper()
                                if 'VIGENTE' in v: return f"🟢 {val}"
                                if 'VENCIDO' in v: return f"🔴 {val}"
                                return f"🟡 {val}"
                                
                            df_mostrar_otros['Estatus de verificación'] = df_mostrar_otros['Estatus de verificación'].apply(emoji_estatus)
                            
                            st.dataframe(df_mostrar_otros, use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay otros equipos operativos registrados en esta línea.")
                # ---------------------------------------------------------
            # ==========================================
            # LÓGICA DE VISUALIZACIÓN: MAQUINARIA
            # ==========================================
            elif es_maq:
                equipo = df_maq_scan.iloc[0]
                maquina_sel = str(equipo.get('id_maquinaria', ''))
                linea_ubicacion = str(equipo.get('linea_ubicacion', ''))
                
                estatus_op = str(equipo.get('status_operativo', '')).strip().upper()
                resultado_est = str(equipo.get('resultado_estatus', 'N/A')).strip().upper()
                
                if estatus_op == "NO OPERATIVO":
                    estatus_mostrar = "🔴 NO OPERATIVO"
                else:
                    estatus_mostrar = resultado_est
                
                st.markdown(f"### 🏭 Detalles de la Maquinaria")
                c_linea, c_tipo, c_estatus = st.columns(3)
                c_linea.metric("Ubicación", linea_ubicacion)
                clasificacion_equipo = str(equipo.get('clasificacion', 'N/A'))
                c_tipo.metric("Clasificación", clasificacion_equipo)
                c_estatus.metric("Estatus", estatus_mostrar)
                
                c_val, c_bal = st.columns(2)
                res_tierra = equipo.get('resistencia_tierra')
                c_val.metric("Resistencia a Tierra", f"{float(res_tierra):.2E} Ω" if pd.notna(res_tierra) and res_tierra else "N/D")
                campo_est = equipo.get('campo_estatico_voltaje')
                c_bal.metric("Campo Estático", f"{float(campo_est):.1f} V" if pd.notna(campo_est) else "N/D")

                f_val_sql = str(equipo.get('fecha_medicion', 'N/A'))[:10]
                f_venc_sql = str(equipo.get('fecha_proxima', 'N/A'))[:10]
                
                c_fval, c_fvenc = st.columns(2)
                c_fval.metric("Fecha de Validación", f_val_sql)
                c_fvenc.metric("Fecha de Vencimiento", f_venc_sql)
                
                with st.expander("🕰️ Consultar Historial de Mediciones Anteriores"):
                    df_maq_hist = df_maq_scan[['fecha_medicion', 'resistencia_tierra', 'campo_estatico_voltaje', 'tomacorriente_estatus', 'resultado_estatus', 'auditor']].copy()
                    df_maq_hist.columns = ['Fecha', 'Resistencia (Ω)', 'Campo (V)', 'Toma', 'Estatus', 'Auditor']
                    
                    def formatear_res_hist(val):
                        try:
                            v = float(val)
                            return f"{v:.2f}" if v < 10 else f"{v:.2e}" # <--- Forzado a minúscula (.2e)
                        except:
                            return "N/D"
                            
                    if 'Resistencia (Ω)' in df_maq_hist.columns:
                        df_maq_hist['Resistencia (Ω)'] = df_maq_hist['Resistencia (Ω)'].apply(formatear_res_hist)
                        
                    df_maq_hist['Fecha'] = pd.to_datetime(df_maq_hist['Fecha'], format='ISO8601', errors='coerce').dt.strftime('%d-%b-%Y %H:%M')
                    st.dataframe(df_maq_hist.fillna("N/D"), use_container_width=True, hide_index=True)

                st.divider()

                if not st.session_state.modo_lectura:
                    # --- RUTA 1: VINO DESDE EL ESCÁNER QR ---
                    if st.session_state.sub_pestana_escaner == "📷 Escáner QR / Manual":
                        st.info("💡 Para registrar una nueva validación, utiliza el módulo de maquinaria.")
                        if st.button("🏭 Ir al Módulo de Maquinaria", use_container_width=True, type="primary"):
                            st.session_state.vista_actual = "Maquinaria"
                            # Guardamos en memoria el ID y la Línea para que el otro módulo los atrape
                            st.session_state.nav_linea = linea_ubicacion
                            st.session_state.nav_maq = maquina_sel
                            limpiar_url_escaneo()
                            st.rerun()
                            
                    # --- RUTA 2: VINO DESDE LA LISTA DE VENCIMIENTOS ---
                    else:
                        st.markdown("##### ⚡ Registrar Medición Directa")
                        st.caption("Actualiza los parámetros normativos de esta estación sin necesidad de cambiar de módulo.")
                        
                        hacer_medicion = st.checkbox(f"✅ Habilitar captura para {maquina_sel}")
                        
                        if hacer_medicion:
                            limite_fijo = 1e9 if str(clasificacion_equipo).strip().upper() == "MOBILIARIO" else 1.0
                            
                            with st.form("form_medicion_maq_directa"):
                                c_amb1, c_amb2, c_amb3 = st.columns(3)
                                temperatura_maq = c_amb1.number_input("Temperatura (°C)", value=23.5, step=0.1)
                                humedad_maq = c_amb2.number_input("Humedad (%)", value=45, step=1)
                                status_maq = c_amb3.selectbox("Estatus Operativo", ["OPERATIVO", "NO OPERATIVO", "MANTENIMIENTO"])
                                
                                st.markdown("##### ⚡ 1. Resistencia a Tierra")
                                col_r1, col_r2, col_r3 = st.columns([1.5, 1, 2])
                                resistencia = col_r1.number_input("Valor (Ohms)*", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="0.0")
                                limite_str = f"{limite_fijo:.2e} Ω" if limite_fijo > 10 else f"{limite_fijo:.2f} Ω"
                                col_r2.text_input("Límite Máximo", value=limite_str, disabled=True)
                                comentario_res = col_r3.text_input("Nota / Ubicación (Obligatorio)*", placeholder="Ej. Chasis principal")
                                
                                st.markdown("##### 🔌 2. Tomacorriente")
                                col_t1, col_t2 = st.columns(2)
                                aplica_toma = col_t1.checkbox("Aplica medición a la red", value=True)
                                estado_toma = "N/A"
                                comentario_toma = ""
                                if aplica_toma:
                                    estado_toma = col_t1.radio("Estatus Conexión", ["PASA", "FALLA"], horizontal=True)
                                    if estado_toma == "FALLA":
                                        comentario_toma = col_t2.text_input("Comentario Falla (Requerido)")
                                        
                                st.markdown("##### 🧲 3. Campo Estático")
                                c_campo1, c_campo2, c_campo3 = st.columns([1.5, 1, 2])
                                voltaje_campo = c_campo1.number_input("Voltaje (V)*", min_value=0.0, format="%.2f", step=1.0, value=None, placeholder="0")
                                c_campo2.text_input("Límite Max.", value="< 100 V", disabled=True)
                                comentario_campo = c_campo3.text_input("Nota / Ubicación (Obligatorio)*", placeholder="Ej. Pantalla touch")
                                
                                # --- INYECCIÓN: MEDICIONES OPCIONALES ---
                                with st.expander("➕ Añadir Mediciones Adicionales (Opcional)", expanded=False):
                                    st.info("Utiliza estos campos si el protocolo requiere muestreo múltiple en esta máquina.")
                                    col_opt1, col_opt2 = st.columns(2)
                                    res_opt = col_opt1.number_input("Resistencia Adicional (Ω)", value=None, step=0.01, format="%.2f")
                                    com_res_opt = col_opt1.text_input("Nota (Resistencia Adicional)")
                                    
                                    volt_opt = col_opt2.number_input("Voltaje Adicional (V)", value=None, step=1.0)
                                    com_volt_opt = col_opt2.text_input("Nota (Voltaje Adicional)")

                                obs_maq = st.text_area("Notas / Observaciones Generales")
                                
                                if st.form_submit_button("💾 Guardar Validación Directa", use_container_width=True, type="primary"):
                                    # Validaciones estrictas
                                    if resistencia is None or not comentario_res.strip():
                                        st.error("⚠️ El valor y comentario de la Resistencia a Tierra son obligatorios.")
                                    elif voltaje_campo is None or not comentario_campo.strip():
                                        st.error("⚠️ El valor y comentario del Campo Estático son obligatorios.")
                                    elif aplica_toma and estado_toma == "FALLA" and not comentario_toma.strip():
                                        st.error("⚠️ Debes escribir un comentario justificando la falla del tomacorriente.")
                                    else:
                                        with st.spinner("Guardando registro en SQL..."):
                                            try:
                                                fecha_hoy = datetime.today().date()
                                                from dateutil.relativedelta import relativedelta
                                                proxima_fecha = fecha_hoy + relativedelta(years=1)
                                                
                                                # Empaquetado de JSON para opcionales
                                                extra_data = {}
                                                if res_opt is not None:
                                                    extra_data["resistencia_2"] = {"valor": res_opt, "comentario": com_res_opt}
                                                if volt_opt is not None:
                                                    extra_data["voltaje_2"] = {"valor": volt_opt, "comentario": com_volt_opt}

                                                # Lógica de estatus oficial
                                                if proxima_fecha < fecha_hoy:
                                                    estatus_calculado = "VENCIDO"
                                                elif resistencia > limite_fijo or voltaje_campo >= 100 or (aplica_toma and estado_toma == "FALLA"):
                                                    estatus_calculado = "FALLA"
                                                else:
                                                    estatus_calculado = "VIGENTE"
                                                    
                                                data_insert = {
                                                    "linea_ubicacion": linea_ubicacion,
                                                    "id_maquinaria": maquina_sel,
                                                    "clasificacion": clasificacion_equipo,
                                                    "marca": equipo.get('marca', 'N/D'),
                                                    "status_operativo": status_maq,
                                                    "temperatura": temperatura_maq,
                                                    "humedad": humedad_maq,
                                                    "frecuencia_verificacion": "Anual",
                                                    "fecha_proxima": proxima_fecha.isoformat(),
                                                    "resistencia_tierra": float(resistencia),
                                                    "resistencia_max": limite_fijo,
                                                    "comentario_resistencia": comentario_res, # Nueva DB column
                                                    "tomacorriente_aplica": aplica_toma,
                                                    "tomacorriente_estatus": estado_toma,
                                                    "tomacorriente_comentario": comentario_toma,
                                                    "campo_estatico_voltaje": float(voltaje_campo),
                                                    "campo_estatico_comentario": comentario_campo, # Nueva DB column
                                                    "mediciones_extra": extra_data, # JSONB DB column
                                                    "observaciones": obs_maq,
                                                    "fecha_medicion": datetime.now().isoformat(),
                                                    "auditor": st.session_state.usuario_nombre,
                                                    "resultado_estatus": estatus_calculado
                                                }
                                                
                                                supabase.table("mediciones_maquinaria").insert(data_insert).execute()
                                                st.success(f"✅ ¡Validación guardada exitosamente para {maquina_sel}!")
                                                st.cache_data.clear()
                                                time.sleep(1.5)
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error al guardar: {e}")

        else:
            # ==========================================
            # LÓGICA DE ALTA RÁPIDA (SÓLO CÁMARA)
            # ==========================================
            st.error(f"❌ El ID `{id_limpio}` no se encontró en la base de datos actual.")
            
            # 1. El truco: Verificamos si vino de la cámara o del teclado
            valor_teclado = str(st.session_state.get("input_manual", "")).strip().upper()
            
            if valor_teclado == id_limpio:
                # Vino de un ingreso manual
                st.warning("⚠️ **Alta Rápida Deshabilitada.**\nPara evitar registrar equipos con errores tipográficos, el alta automática sólo se activa al escanear el código QR físico con la cámara.")
            else:
                # Vino directamente del escáner
                st.info("💡 **QR Físico Detectado.**\nComo este ID proviene directamente del escáner, tienes autorización para darlo de alta en el sistema en este momento.")
                
                with st.expander("➕ Abrir Formulario de Alta Rápida", expanded=True):
                    with st.form("form_alta_escaner"):
                        st.markdown(f"#### Registro de Nuevo Equipo: `{id_limpio}`")
                        
                        col_md, col_cat = st.columns(2)
                        modulo_dest = col_md.selectbox("Módulo de Destino", ["Inventario ESD (General)", "Maquinaria"])
                        
                        cat_opciones = ["Mobiliario", "Ionizador", "Monitor Continuo", "Tapete", "Prendas/Zapatos", "Otro"]
                        categoria = col_cat.selectbox("Categoría", cat_opciones) if modulo_dest != "Maquinaria" else "Maquinaria"
                        
                        if 'obtener_catalogo_lineas' in globals():
                            lineas_opc = obtener_catalogo_lineas()
                        else:
                            lineas_opc = ["N/D"]
                            
                        col_l, col_c = st.columns(2)
                        linea = col_l.selectbox("Línea / Ubicación", options=lineas_opc)
                        clasificacion = col_c.text_input("Clasificación (Ej. Mesa, Rack, SMT, Router)")
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        marca = col_m1.text_input("Marca", "N/D")
                        modelo = col_m2.text_input("Modelo", "N/D")
                        serie = col_m3.text_input("No. Serie", "N/D")
                        
                        freq = st.selectbox("Frecuencia de Verificación Normativa", ["Anual", "Semestral", "Trimestral", "Mensual", "Semanal", "Diario"])
                        
                        # Usamos 'stretch' para cumplir con los nuevos estándares de Streamlit
                        if st.form_submit_button("💾 Guardar y Registrar en Base de Datos", type="primary", use_container_width=True):
                            if not clasificacion.strip():
                                st.error("⚠️ La clasificación es un campo obligatorio.")
                            else:
                                with st.spinner("Inyectando nuevo registro en SQL..."):
                                    try:
                                        from datetime import datetime
                                        fecha_hoy = datetime.now().date()
                                        
                                        # Recicla tu función maestra para proyecciones
                                        f_prox = calcular_proxima_fecha(fecha_hoy, freq)
                                        
                                        if modulo_dest == "Maquinaria":
                                            payload = {
                                                "id_maquinaria": id_limpio,
                                                "linea_ubicacion": linea,
                                                "clasificacion": clasificacion,
                                                "marca": marca,
                                                "modelo": modelo,
                                                "numero_serie": serie,
                                                "frecuencia_verificacion": freq,
                                                "fecha_medicion": fecha_hoy.isoformat(),
                                                "fecha_proxima": f_prox.isoformat(),
                                                "status_operativo": "OPERATIVO",
                                                "resultado_estatus": "PENDIENTE",
                                                "auditor": st.session_state.usuario_nombre
                                            }
                                            supabase.table("mediciones_maquinaria").insert(payload).execute()
                                        else:
                                            payload = {
                                                "id_producto": id_limpio,
                                                "linea_ubicacion": linea,
                                                "categoria": categoria,
                                                "clasificacion": clasificacion,
                                                # Se omiten marca, modelo y serie para cumplir con el esquema de inventario_esd
                                                "frecuencia": freq,
                                                "fecha_ultima_verif": fecha_hoy.isoformat(),
                                                "fecha_proxima_verif": f_prox.isoformat(),
                                                "estatus_operativo": "OPERATIVO",
                                                "estatus_verificacion": "PENDIENTE",
                                                "auditor_responsable": st.session_state.usuario_nombre
                                            }
                                            supabase.table("inventario_esd").insert(payload).execute()
                                            
                                        st.success(f"✅ ¡El equipo {id_limpio} ha sido dado de alta oficialmente!")
                                        st.cache_data.clear()
                                        import time
                                        time.sleep(1.5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Fallo de inserción en base de datos: {e}")
# ==========================================
# VISTA 3: EVENT METER
# ==========================================
elif st.session_state.vista_actual == "Event Meter" and not st.session_state.modo_lectura:
    st.markdown("### ⚡ Estudio de Event Meter (PCBA)")
    st.info("Mide descargas electrostáticas y transitorios durante la operación normal de la maquinaria/proceso.")

    # --- SECCIÓN: GENERADOR DE REPORTE POR LÍNEA (ESTILO WALKING TEST) ---
    with st.expander("📄 Generar Reporte Oficial por Línea (Estilo Walking Test)", expanded=False):
        st.write("Selecciona una línea para consolidar todas sus operaciones guardadas en la base de datos en un único reporte oficial.")
        
        lineas_reporte = []
        if df_em_local is not None and not df_em_local.empty and 'Línea' in df_em_local.columns:
            lineas_reporte = sorted([str(x).strip() for x in df_em_local['Línea'].dropna().unique() if str(x).strip() != ''])
        
        if not lineas_reporte:
            st.warning("⚠️ No hay registros históricos en 'event_meter' para generar reportes consolidados.")
        else:
            linea_rep_sel = st.selectbox("Seleccionar Línea para el Reporte Consolidado:", options=lineas_reporte, key="em_linea_rep_sel")
            
            with st.form("form_reporte_em_consolidado"):
                st.markdown("#### Datos Generales del Estudio")
                col_g1, col_g2 = st.columns(2)
                auditor_em = col_g1.text_input("Auditor / Técnico", value=st.session_state.usuario_nombre if st.session_state.usuario_nombre else "")
                periodo_em = col_g2.selectbox("Periodo de Evaluación", ["Semestre 1", "Semestre 2", "Evaluación Anual"])
                
                col_g3, col_g4 = st.columns(2)
                equipo_em = col_g3.text_input("Equipo de Medición Utilizado", value="SCS EM EYE")
                serial_em = col_g4.text_input("No. de Serie del Equipo", value="2451005")
                
                # --- NUEVOS CAMPOS AMBIENTALES PARA EL REPORTE ---
                col_g5, col_g6 = st.columns(2)
                temp_rep = col_g5.text_input("Temperatura de la Línea", value="23.5 °C")
                hum_rep = col_g6.text_input("Humedad de la Línea", value="45 %")
                
                submit_reporte_em = st.form_submit_button("Generar Reporte Consolidado por Línea", use_container_width=True)
                
                if submit_reporte_em:
                    df_filtrado = df_em_local[df_em_local['Línea'].astype(str).str.strip() == linea_rep_sel].copy()
                    
                    if df_filtrado.empty:
                        st.error("No se encontraron registros en la base de datos para la línea seleccionada.")
                    else:
                        with st.spinner("Generando folio único y construyendo reporte..."):
                            # --- 1. LÓGICA DE NOMENCLATURA ---
                            año_actual = datetime.today().strftime("%y")
                            
                            try:
                                # Registramos la descarga en la bitácora para obtener el consecutivo (XXX)
                                resp_log_em = supabase.table("log_reportes_em").insert({
                                    "linea_ubicacion": linea_rep_sel,
                                    "auditor": auditor_em
                                }).execute()
                                db_id_em = resp_log_em.data[0]['id']
                            except Exception as e:
                                db_id_em = 999
                                st.warning(f"Aviso: Usando folio 999 por error de conexión con la bitácora: {e}")
                            
                            # Construimos el Folio Final
                            folio_em = f"BCS-QRO-ESDEV-{db_id_em:03d}-{año_actual}"
                            # ---------------------------------

                            html_rows = ""
                            for i, row in enumerate(df_filtrado.to_dict('records'), 1):
                                op = str(row.get('Id de Operación', 'N/A'))
                                tipo_c = str(row.get('Tipo de contacto', 'N/D'))
                                
                                raw_eventos = row.get('Detección (Cantidad)', 0)
                                eventos = int(float(raw_eventos)) if pd.notna(raw_eventos) and str(raw_eventos).strip() != '' else 0
                                
                                raw_vmax = row.get('Voltaje máximo', 0.0)
                                vmax = float(raw_vmax) if pd.notna(raw_vmax) and str(raw_vmax).strip() != '' else 0.0
                                
                                estatus = str(row.get('Estatus de verificación', '')).upper()
                                notas = str(row.get('Notas', ''))
                                if notas.lower() in ['nan', 'none', 'null']: 
                                    notas = ""
                                
                                color_estatus = "text-green-600" if "APROBADO" in estatus else "text-red-600"
                                pass_fail = "PASA" if "APROBADO" in estatus else "FALLA"
                                
                                html_rows += f"""
                                <tr class="text-center border-b border-gray-300">
                                    <td class="border border-gray-800 p-2 font-bold text-gray-600">{i}</td>
                                    <td class="border border-gray-800 p-2 text-left">{op}</td>
                                    <td class="border border-gray-800 p-2">{tipo_c}</td>
                                    <td class="border border-gray-800 p-2 font-mono">{eventos}</td>
                                    <td class="border border-gray-800 p-2 font-mono font-bold">{vmax}V</td>
                                    <td class="border border-gray-800 p-2 font-bold {color_estatus}">{pass_fail}</td>
                                    <td class="border border-gray-800 p-2 text-left text-xs">{notas}</td>
                                </tr>
                                """
                            
                            fecha_hoy_str = datetime.today().strftime("%Y-%m-%d")
                            fecha_pie_str = datetime.today().strftime("%Y/%m/%d")
                            
                            # --- 2. INYECCIÓN DEL FOLIO EN LA PLANTILLA HTML ---
                            html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte {folio_em} - {linea_rep_sel}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @media print {{
        body {{ background-color: white; padding: 0; }}
        .no-print {{ display: none !important; }}
        .print-border {{ border: 1px solid #000; }}
        .shadow-lg {{ box-shadow: none; }}
    }}
</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 text-gray-800 font-sans">
<div class="max-w-5xl mx-auto bg-white p-8 shadow-lg print:shadow-none print:w-full">
    <div class="flex justify-end space-x-4 mb-6 no-print">
        <button onclick="window.print()" class="bg-gray-800 text-white px-4 py-2 rounded shadow hover:bg-gray-900 transition flex items-center font-bold">
            🖨️ Imprimir / Guardar PDF
        </button>
    </div>
    
    <div class="border-2 border-gray-800 mb-6 flex flex-col md:flex-row text-sm print-border">
        <div class="p-4 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 flex items-center justify-center w-full md:w-1/4">
            <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="Logo BCS" class="max-h-20 object-contain">
        </div>
        <div class="p-4 flex-1 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 text-center flex flex-col justify-center">
            <h1 class="text-lg font-bold uppercase">Registro de Estudio de Eventos ESD (Event Meter)</h1>
            <p class="text-gray-600 font-semibold">Norma de Referencia: ANSI/ESD S20.20</p>
        </div>
        <div class="p-2 w-full md:w-1/4 flex flex-col justify-center text-xs space-y-1">
            <div class="flex justify-between"><span class="font-bold">Código:</span> <span>F-ESD-001</span></div>
            <div class="flex justify-between"><span class="font-bold">Límite Permitido:</span> <span class="font-bold text-red-600">&lt; 100V</span></div>
            <div class="flex justify-between mt-2 pt-2 border-t border-gray-300"><span class="font-bold text-red-700 text-sm">Folio:</span> <span class="font-bold text-red-700 text-sm">{folio_em}</span></div>
        </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 text-sm">
        <div class="space-y-2">
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Fecha de Estudio:</span><span>{fecha_hoy_str}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Línea / Área Evaluada:</span><span>{linea_rep_sel}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Auditor / Técnico:</span><span>{auditor_em}</span></div>
        </div>
        <div class="space-y-2">
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Periodo de Evaluación:</span><span>{periodo_em}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Equipo de Medición (SN):</span><span>{equipo_em} ({serial_em})</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Temperatura / Humedad:</span><span>{temp_rep} / {hum_rep}</span></div>
        </div>
    </div>
    
    <div class="overflow-x-auto mb-8">
        <table class="w-full text-sm border-collapse border border-gray-800 print-border">
            <thead>
                <tr class="bg-gray-200 text-center">
                    <th class="border border-gray-800 p-2 w-10">No.</th>
                    <th class="border border-gray-800 p-2 text-left">Operación / Estación</th>
                    <th class="border border-gray-800 p-2">Tipo de Contacto</th>
                    <th class="border border-gray-800 p-2 w-24">Eventos</th>
                    <th class="border border-gray-800 p-2 w-24">Voltaje Máx.</th>
                    <th class="border border-gray-800 p-2 w-24">Resultado</th>
                    <th class="border border-gray-800 p-2 text-left">Observaciones</th>
                </tr>
            </thead>
            <tbody>
                {html_rows}
            </tbody>
        </table>
    </div>
    
    <div class="grid grid-cols-2 gap-8 mt-12 text-sm text-center">
        <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Realizado por: {auditor_em}</p></div>
        <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Revisado / Aprobado por: Coordinador ESD</p></div>
    </div>

    <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans">
        <div class="flex justify-between items-end">
            <div class="text-left leading-tight">
                <div>B_010_4_013_QRO_SP_Rev. A</div>
                <div>Registro de eventos ESD</div>
            </div>
            <div class="text-center leading-tight">
                <div>Fecha: 14/ago/2025</div>
            </div>
            <div class="text-right leading-tight">
                <div>Ref. B_010_3_002_QRO_SP</div>
            </div>
        </div>
    </div>
</div>
</body>
</html>"""
                            
                            b64_html = base64.b64encode(html_template.encode('utf-8')).decode('utf-8')
                            nombre_archivo = f"{folio_em}_{linea_rep_sel.replace(' ', '_')}.html"
                            
                            st.success(f"✅ ¡Reporte {folio_em} generado con éxito!")
                            href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Oficial ({folio_em})</a>'
                            st.markdown(href, unsafe_allow_html=True)

    # --- SECCIÓN DEL TEMPORIZADOR (5 MINUTOS) ---
    st.divider()
    st.markdown("#### ⏱️ Temporizador de Medición")
    st.info("Utiliza este temporizador para asegurar la medición estándar de 5 minutos por estación antes de guardar el registro.")
    
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        iniciar_timer = st.button("▶️ Iniciar 5 Minutos", use_container_width=True)
    with col_t2:
        timer_placeholder = st.empty()
        if iniciar_timer:
            for t in range(300, -1, -1):
                mins, secs = divmod(t, 60)
                timer_placeholder.markdown(f"### ⏳ Tiempo restante: {mins:02d}:{secs:02d}")
                time.sleep(1)
            
            timer_placeholder.success("✅ ¡Tiempo de medición completado! Procede a registrar los datos.")
            st.balloons()

    # --- FORMULARIO DE CAPTURA DE NUEVOS REGISTROS ---
    st.divider()
    st.markdown("#### 📍 Ubicación y Operación")
    c_loc1, c_loc2 = st.columns(2)

    lineas_existentes = obtener_catalogo_lineas()
    linea_seleccionada = c_loc1.selectbox("Línea", options=lineas_existentes, key="em_linea_seleccionada_captura")
    nueva_op_check = c_loc2.checkbox("➕ Registrar nueva Operación o Línea")

    if nueva_op_check:
        linea_final = c_loc1.text_input("Ingresa Nueva Línea", value=linea_seleccionada if linea_seleccionada != "Sin registros" else "")
        id_operacion_final = c_loc2.text_input("Ingresa Nuevo ID de Operación (Ej: OP50-AUDIO)")
    else:
        linea_final = linea_seleccionada
        ops_existentes = []
        if not df_em_local.empty and 'Id de Operación' in df_em_local.columns:
            ops_filtradas = df_em_local[df_em_local['Línea'].astype(str).str.strip() == linea_seleccionada]
            ops_existentes = sorted([str(x).strip() for x in ops_filtradas['Id de Operación'].dropna().unique() if str(x).strip() != ''])
        
        if not ops_existentes:
            id_operacion_final = c_loc2.selectbox("ID de Operación", options=["(Sin operaciones previas)"])
        else:
            id_operacion_final = c_loc2.selectbox("Selecciona ID de Operación", options=ops_existentes)

    with st.form("form_event_meter_captura"):
        col1, col2 = st.columns(2)
        tipo_contacto = col1.selectbox("Tipo de contacto", options=["Maquinaria", "EOLT", "AOI", "Herramienta Manual", "Humano", "Otro"])
        if tipo_contacto == "Otro":
            tipo_contacto = col1.text_input("Especifique Tipo de Contacto")

        # (Este código va justo debajo de donde pides el 'tipo_contacto')
        
        st.markdown("#### 🌡️ Condiciones Ambientales")
        col_amb1, col_amb2 = st.columns(2)
        temperatura_em = col_amb1.number_input("Temperatura (°C)", value=23.5, step=0.1)
        humedad_em = col_amb2.number_input("Humedad Relativa (%)", value=45, step=1)

        st.markdown("#### ⚡ Resultados de Detección")
        col_d1, col_d2 = st.columns(2)
        deteccion_eventos = col_d1.number_input("Cantidad de Eventos Detectados", min_value=0, step=1, value=None, placeholder="Ej: 5")
        voltaje_max = col_d2.number_input("Voltaje máximo de descarga (V)", min_value=0.0, max_value=999.0, step=0.1, value=None, placeholder="0.0")

        notas_em = st.text_area("Notas / Observaciones")

        # Eliminamos la evaluación temprana de estatus que causaba el crash
        fecha_hoy = datetime.today().date()
        frecuencia_em = "Semestral" 
        proxima_fecha = calcular_proxima_fecha(fecha_hoy, frecuencia_em)

        submit_em = st.form_submit_button("💾 Guardar Registro de Event Meter", use_container_width=True)

        if submit_em:
            if not id_operacion_final or id_operacion_final == "(Sin operaciones previas)":
                st.error("⚠️ Debes proporcionar un ID de Operación válido.")
            elif deteccion_eventos is None or voltaje_max is None:
                st.error("⚠️ Debes capturar la cantidad de eventos y el voltaje máximo.")
            else:
                # AQUÍ es donde evaluamos, porque ya sabemos que voltaje_max es un número
                estatus_verificacion = "APROBADO" if voltaje_max <= 100.0 else "RECHAZADO"
                
                with st.spinner("Guardando en la tabla EVENT_METER de SQL..."):
                    try:
                        supabase.table("event_meter").insert({
                            "linea_ubicacion": linea_final,
                            "id_operacion": id_operacion_final.upper(),
                            "tipo_contacto": tipo_contacto,
                            "cantidad_eventos": int(deteccion_eventos),
                            "voltaje_maximo": float(voltaje_max),
                            "temperatura": float(temperatura_em), # <- NUEVO CAMPO
                            "humedad": int(humedad_em),           # <- NUEVO CAMPO
                            "estatus_verificacion": estatus_verificacion,
                            "notas": notas_em,
                            "auditor": st.session_state.usuario_nombre,
                            "fecha": datetime.now().isoformat()
                        }).execute()
                        
                        st.success(f"✅ ¡Estudio de {id_operacion_final} registrado exitosamente! Estatus: {estatus_verificacion}")
                        st.cache_data.clear()
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error SQL al guardar en Event Meter: {e}")

# ==========================================
# VISTA 4: WALKING TEST
# ==========================================
elif st.session_state.vista_actual == "Walking Test" and not st.session_state.modo_lectura:
    st.markdown("### 🚶‍♂️ Análisis y Registro de Walking Test")
    
    # --- CONTROL DE PESTAÑAS MAESTRO ---
    if "sub_pestana_wt" not in st.session_state:
        st.session_state.sub_pestana_wt = "📄 Nuevo Reporte (OCR)"
        
    opcion_pestana_wt = st.radio(
        "Navegación Interna:", 
        ["📄 Nuevo Reporte (OCR)", "🗄️ Consultar Historial"], 
        horizontal=True, 
        label_visibility="collapsed",
        key="radio_pestanas_wt"
    )
    st.session_state.sub_pestana_wt = opcion_pestana_wt

    # =========================================================
    # PESTAÑA 1: EXTRACCIÓN OCR Y GUARDADO
    # =========================================================
    if st.session_state.sub_pestana_wt == "📄 Nuevo Reporte (OCR)":
        st.info("Sube uno o varios archivos PDF generados por el equipo de medición para extraer los datos automáticamente vía OCR y generar un reporte consolidado.")

        archivos_pdf = st.file_uploader("Selecciona los archivos PDF", type=["pdf"], accept_multiple_files=True)

        if archivos_pdf:
            st.markdown("#### Resultados Extraídos")
            datos_extraidos_wt = [] 
            
            for archivo in archivos_pdf:
                with st.expander(f"📄 Reporte: {archivo.name}", expanded=True):
                    try:
                        doc = fitz.open(stream=archivo.read(), filetype="pdf")
                        pagina = doc[0] 
                        imagen_grafica = None
                        texto_ocr = ""
                        img_b64 = "" 

                        imagenes_pdf = pagina.get_images(full=True)
                        if imagenes_pdf:
                            xref = imagenes_pdf[0][0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            imagen_grafica = Image.open(io.BytesIO(image_bytes))

                            with st.spinner("Analizando imagen con OCR..."):
                                texto_ocr = pytesseract.image_to_string(imagen_grafica)
                            
                            buffered = io.BytesIO()
                            imagen_grafica.save(buffered, format="PNG")
                            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        else:
                            st.warning("No se detectó ninguna imagen/gráfica en este PDF para analizar.")
                            continue

                        fecha_hora_match = re.search(r"(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})", texto_ocr)
                        fecha = fecha_hora_match.group(1) if fecha_hora_match else "N/D"
                        hora = fecha_hora_match.group(2) if fecha_hora_match else "N/D"

                        hum_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?\s*RH", texto_ocr, re.IGNORECASE)
                        humedad = f"{hum_match.group(1)} %" if hum_match else "N/D"

                        temp_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*[^C]*C", texto_ocr, re.IGNORECASE)
                        temperatura = f"{temp_match.group(1)} °C" if temp_match else "N/D"

                        peaks_match = re.search(r"highest peaks:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        picos = peaks_match.group(1).strip() if peaks_match else "N/D"

                        valleys_match = re.search(r"highest valleys:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        valles = valleys_match.group(1).strip() if valleys_match else "N/D"

                        max_abs = 0.0
                        promedio_picos = 0.0
                        pico_max_positivo = 0.0
                        pico_max_negativo = 0.0
                        
                        try:
                            p_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", picos)]
                            v_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", valles)]
                            todos_los_valores = p_vals + v_vals
                            
                            if todos_los_valores:
                                max_abs = max(abs(x) for x in todos_los_valores)
                            if p_vals:
                                promedio_picos = sum(p_vals) / len(p_vals)
                                pico_max_positivo = max(p_vals)
                            if v_vals:
                                pico_max_negativo = min(v_vals)
                        except:
                            pass

                        col_datos1, col_datos2 = st.columns(2)
                        with col_datos1:
                            st.metric("📅 Fecha", fecha)
                            st.metric("🌡️ Temperatura", temperatura)
                            st.metric("⚡ Voltaje Máx (Absoluto)", f"{max_abs:.2f} V")
                        with col_datos2:
                            st.metric("🕒 Hora", hora)
                            st.metric("💧 Humedad", humedad)
                            st.metric("📊 Promedio Picos", f"{promedio_picos:.2f} V")

                        st.divider()
                        st.markdown("**Gráfica Extraída:**")
                        st.image(imagen_grafica, width="stretch")

                        datos_extraidos_wt.append({
                            "archivo": archivo.name, "fecha": fecha, "temp": temperatura,
                            "hum": humedad, "max_abs": max_abs, "promedio_picos": promedio_picos,
                            "img_b64": img_b64
                        })
                        
                        # --- NUEVO: Extraer listas completas (hasta 5 valores) ---
                        st.session_state.wt_p_vals_mem = p_vals[:5] if 'p_vals' in locals() and p_vals else []
                        st.session_state.wt_v_vals_mem = v_vals[:5] if 'v_vals' in locals() and v_vals else []
                        
                        st.session_state.wt_temp_mem = temp_match.group(1) if temp_match else ""
                        st.session_state.wt_hum_mem = hum_match.group(1) if hum_match else ""
                        st.session_state.wt_p_pos_mem = pico_max_positivo
                        st.session_state.wt_p_neg_mem = pico_max_negativo
                        
                        if fecha != "N/D":
                            try:
                                f_obj = datetime.strptime(fecha, "%d/%m/%y")
                                st.session_state.wt_fecha_mem = f_obj.date().isoformat()
                            except:
                                st.session_state.wt_fecha_mem = datetime.now().date().isoformat()
                        else:
                            st.session_state.wt_fecha_mem = datetime.now().date().isoformat()
                            
                        st.success("📊 ¡Datos del PDF extraídos y respaldados en memoria con éxito!")
                    except Exception as e:
                        st.error(f"Ocurrió un error al procesar el archivo {archivo.name}: {e}")

            if datos_extraidos_wt:
                st.divider()
                st.markdown("### 📄 Generar Reporte Oficial Consolidado")
                st.write("Completa la información general para generar un solo reporte con todas las ubicaciones procesadas.")
                
                fecha_defecto = datos_extraidos_wt[0]['fecha'] if datos_extraidos_wt[0]['fecha'] != "N/D" else datetime.today().strftime("%d/%m/%Y")
                temp_defecto = datos_extraidos_wt[0]['temp']
                hum_defecto = datos_extraidos_wt[0]['hum']
                
                with st.form("form_reporte_wt"):
                    st.markdown("#### Datos Generales")
                    col_g1, col_g2, col_g3 = st.columns(3)
                    auditor_wt = col_g1.text_input("Auditor / Técnico", value=st.session_state.usuario_nombre if st.session_state.usuario_nombre else "")
                    operador_wt = col_g2.text_input("Operador de Prueba")
                    periodo_wt = col_g3.selectbox("Periodo de Evaluación", ["Semestre 1", "Semestre 2"])
                    
                    col_g4, col_g5 = st.columns(2)
                    equipo_wt = col_g4.text_input("Equipo de Medición Utilizado", value="DESCO 46006")
                    calzado_wt = col_g5.text_input("Calzado ESD Utilizado", value="Zapato antiestático Workman")
                    
                    st.markdown("#### 🌡️ Condiciones Ambientales (Edítalas si es necesario)")
                    col_amb1, col_amb2, col_amb3 = st.columns(3)
                    fecha_gen = col_amb1.text_input("Fecha de Prueba", value=fecha_defecto)
                    temp_gen = col_amb2.text_input("Temperatura", value=temp_defecto)
                    hum_gen = col_amb3.text_input("Humedad", value=hum_defecto)
                    
                    st.markdown("#### Configuración de Ubicaciones")
                    bloques_ubicaciones = []
                    
                    for i, dato in enumerate(datos_extraidos_wt):
                        st.markdown(f"**Ubicación {i+1} (Archivo: {dato['archivo']})**")
                        c_ub1, c_ub2, c_ub3 = st.columns([1.5, 1.5, 1])
                        nombre_ub = c_ub1.text_input(f"Nombre de Línea/Área", value=dato['archivo'].replace(".pdf", ""), key=f"nombre_{i}")
                        tipo_piso = c_ub2.selectbox(f"Tipo de Piso", ["Piso Epóxico ESD", "Loseta Vinílica Conductiva", "Tapete Antifatiga ESD", "Otro"], key=f"piso_{i}")
                        
                        limpieza_chk = c_ub3.checkbox("Limpieza previa", value=False, key=f"limpieza_{i}")
                        
                        bloques_ubicaciones.append({
                            "nombre": nombre_ub, 
                            "piso": tipo_piso, 
                            "limpieza": "Sí" if limpieza_chk else "No",
                            "datos": dato
                        })
                        st.write("") 

                    submit_reporte = st.form_submit_button("Generar Reporte Consolidado en PDF/HTML", width="stretch")
                
                if submit_reporte:
                    try:
                        fecha_limpia = str(fecha_gen).replace('-', '/')
                        año_prueba = fecha_limpia.split('/')[-1][-2:]
                    except:
                        año_prueba = datetime.today().strftime("%y")

                    try:
                        resp_log_wt = supabase.table("log_reportes_wt").insert({
                            "fecha_prueba": fecha_gen,
                            "auditor": auditor_wt
                        }).execute()
                        db_id_wt = resp_log_wt.data[0]['id']
                    except Exception as e:
                        db_id_wt = 999
                        st.warning(f"Error de conexión con la bitácora de folios. Usando 999. Error: {e}")

                    folio_wt = f"BCS-QRO-WLK-{db_id_wt:03d}-{año_prueba}"

                    html_ubicaciones = ""
                    for idx, block in enumerate(bloques_ubicaciones, 1):
                        data = block['datos']
                        if data['max_abs'] < 100:
                            res_text, res_color = "CUMPLE (PASS)", "text-green-600"
                            obs = "Ninguna anomalía. Los picos se mantuvieron por debajo del límite normativo de 100V."
                        else:
                            res_text, res_color = "NO CUMPLE (FAIL)", "text-red-600"
                            obs = f"ATENCIÓN: Se registró un pico absoluto de {data['max_abs']:.2f}V, superando el límite permitido de 100V. Se requiere limpieza o revisión."

                        img_tag = f'<img src="data:image/png;base64,{data["img_b64"]}" class="max-w-full max-h-full object-contain" alt="Gráfica">' if data['img_b64'] else '<i class="text-gray-400">Sin gráfica disponible</i>'

                        html_ubicaciones += f"""
                        <div class="border-2 border-[#003366] rounded-md p-5 mb-8 [page-break-inside:avoid] print:border-black">
                            <div class="text-[18px] font-bold text-white bg-[#003366] p-2.5 -mx-5 -mt-5 mb-5 rounded-t-sm print:bg-black">Ubicación {idx}: {block['nombre']}</div>
                            <table class="w-full text-sm border-collapse mb-5 text-center">
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/4 print:border-black">Tipo de Piso:</th>
                                    <td class="border border-gray-300 p-2 text-left w-1/4 print:border-black">{block['piso']}</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/4 print:border-black">Limpieza previa:</th>
                                    <td class="border border-gray-300 p-2 text-left w-1/4 print:border-black">{block['limpieza']}</td>
                                </tr>
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold print:border-black">Voltaje Máx (Abs):</th>
                                    <td class="border border-gray-300 p-2 text-left font-mono font-bold print:border-black">{data['max_abs']:.2f} V</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold print:border-black">Promedio de Picos:</th>
                                    <td class="border border-gray-300 p-2 text-left font-mono print:border-black">{data['promedio_picos']:.2f} V</td>
                                </tr>
                            </table>
                            <div class="w-full h-64 bg-gray-50 border-2 border-dashed border-gray-300 flex items-center justify-center my-5 overflow-hidden print:border-black">
                                {img_tag}
                            </div>
                            <table class="w-full text-sm border-collapse">
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/5 print:border-black">Observaciones:</th>
                                    <td class="border border-gray-300 p-2 text-left print:border-black">{obs}</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/5 print:border-black">Resultado Final:</th>
                                    <td class="border border-gray-300 p-2 text-center font-bold text-base print:border-black {res_color}">{res_text}</td>
                                </tr>
                            </table>
                        </div>
                        """
                        
                    html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{folio_wt}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @media print {{ body {{ -webkit-print-color-adjust: exact; }} }}
</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
<div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
    <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm hover:bg-blue-700 transition">🖨️ Imprimir / Guardar PDF</button>
</div>
<div class="max-w-5xl mx-auto bg-white p-8 shadow-lg print:shadow-none print:p-0">
    <div class="border-b-4 border-[#003366] pb-4 mb-6 flex justify-between items-start print:border-black">
        <div class="w-1/4">
            <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
        </div>
        <div class="w-2/4 text-center">
            <h1 class="text-2xl font-bold text-[#003366] mb-1 print:text-black">Reporte de Walking Test</h1>
            <p class="text-gray-600 text-sm font-medium">Evaluación de Sistema de Piso y Calzado ESD</p>
            <p class="text-gray-500 text-xs mt-1"><strong>Estándares:</strong> ANSI/ESD S20.20 y ANSI/ESD STM97.2</p>
        </div>
        <div class="w-1/4 text-right">
            <div class="text-red-700 font-bold text-lg">{folio_wt}</div>
        </div>
    </div>
    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-3 uppercase tracking-wide print:text-black print:border-black">1. Información General y Condiciones Ambientales</h2>
    <table class="w-full text-sm border-collapse mb-6">
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Fecha de Prueba:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{fecha_gen}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Periodo:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{periodo_wt}</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Auditor / Técnico:</th>
            <td class="border border-gray-300 p-2 print:border-black">{auditor_wt}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Operador de Prueba:</th>
            <td class="border border-gray-300 p-2 print:border-black">{operador_wt}</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Temperatura:</th>
            <td class="border border-gray-300 p-2 print:border-black">{temp_gen}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Humedad:</th>
            <td class="border border-gray-300 p-2 print:border-black">{hum_gen}</td>
        </tr>
    </table>
    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-3 uppercase tracking-wide print:text-black print:border-black">2. Equipo de Medición y Sistema Evaluado</h2>
    <table class="w-full text-sm border-collapse mb-6">
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Equipo Utilizado:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{equipo_wt}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Criterio Aceptación:</th>
            <td class="border border-gray-300 p-2 w-1/4 font-bold text-[#003366] print:border-black print:text-black">&lt; 100 Voltios (Absoluto)</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Calzado ESD Evaluado:</th>
            <td colspan="3" class="border border-gray-300 p-2 print:border-black">{calzado_wt}</td>
        </tr>
    </table>
    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-4 uppercase tracking-wide print:text-black print:border-black">3. Resultados Consolidados por Ubicación</h2>
    {html_ubicaciones}
    <div class="flex justify-between mt-12 [page-break-inside:avoid]">
        <div class="w-[45%] text-center">
            <div class="border-t border-black mt-10 pt-1.5 text-sm"><strong>Realizado por:</strong><br>{auditor_wt}</div>
        </div>
        <div class="w-[45%] text-center">
            <div class="border-t border-black mt-10 pt-1.5 text-sm"><strong>Revisado / Aprobado por:</strong><br>Coordinador ESD</div>
        </div>
    </div>
    <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
        <div class="flex justify-between items-end">
            <div class="text-left leading-tight">
                <div> B_010_4_020_QRO_EN_Rev. A</div>
                <div>Formato de Walking Test.</div>
            </div>
            <div class="text-center leading-tight">
                <div>Fecha: Fecha: 15/Ago/2025</div>
            </div>
            <div class="text-right leading-tight">
                <div>Ref.B_010_3_002_QRO_SP</div>
            </div>
        </div>
    </div>
</div>
</body>
</html>"""
                    
                    b64_html = base64.b64encode(html_completo.encode('utf-8')).decode('utf-8')
                    nombre_archivo = f"{folio_wt}.html"
                    
                    st.success(f"✅ ¡Reporte {folio_wt} estandarizado y generado con éxito!")
                    href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Oficial ({folio_wt})</a>'
                    st.markdown(href, unsafe_allow_html=True)

            if "wt_temp_mem" in st.session_state:
                st.divider()
                st.markdown("### 💾 Centralizar Registro en Base de Datos")
                st.caption("Guarda los parámetros extraídos por el OCR directamente en el historial maestro de Walking Tests.")

                with st.form("form_guardar_walking_test"):
                    st.markdown("#### Configuración General")
                    col_w1, col_w2 = st.columns(2)
                    
                    if 'obtener_catalogo_lineas' in globals():
                        lineas_test = obtener_catalogo_lineas()
                    else:
                        lineas_test = ["N/D"]
                        
                    ubicacion_w = col_w1.selectbox("Confirmar Línea / Ubicación", options=lineas_test)
                    operador_w = col_w2.text_input("Nombre / No. de Empleado Evaluado (Opcional)", value="N/D")
                    
                    st.markdown("#### ✏️ Revisión de OCR (Corrige si es necesario)")
                    col_e1, col_e2 = st.columns(2)
                    # El value lee lo que extrajo el OCR, pero te permite sobreescribirlo
                    temp_edit = col_e1.text_input("Temperatura (°C)", value=str(st.session_state.wt_temp_mem) if st.session_state.wt_temp_mem else "")
                    hum_edit = col_e2.text_input("Humedad (%)", value=str(st.session_state.wt_hum_mem) if st.session_state.wt_hum_mem else "")
                    
                    notas_w = st.text_area("Notas u observaciones del Walking Test")

                    if st.form_submit_button("🚀 Confirmar y Almacenar en Supabase", type="primary", width="stretch"):
                        import math
                        with st.spinner("Purificando datos e inyectando en SQL..."):
                            
                            def limpiar_num(val):
                                if val is None or str(val).strip() == "" or pd.isna(val): return None
                                try:
                                    # Extrae solo números y puntos por si escribes accidentalmente "23 °C" en la caja
                                    limpio = re.sub(r'[^\d.-]', '', str(val))
                                    f = float(limpio)
                                    return None if math.isnan(f) else f
                                except:
                                    return None

                            try:
                                p_pos = abs(float(st.session_state.wt_p_pos_mem)) if st.session_state.wt_p_pos_mem else 0
                                p_neg = abs(float(st.session_state.wt_p_neg_mem)) if st.session_state.wt_p_neg_mem else 0
                                estatus_final_w = "FALLA" if (p_pos >= 100 or p_neg >= 100) else "PASA"
                            except:
                                estatus_final_w = "PENDIENTE"

                            # Convertimos las listas extraídas a strings limpios
                            str_picos_pos = ", ".join(map(str, st.session_state.wt_p_vals_mem)) if st.session_state.wt_p_vals_mem else "N/D"
                            str_picos_neg = ", ".join(map(str, st.session_state.wt_v_vals_mem)) if st.session_state.wt_v_vals_mem else "N/D"

                            payload_walking = {
                                "fecha_medicion": st.session_state.wt_fecha_mem,
                                "nombre_empleado": operador_w.strip(),
                                "linea_ubicacion": ubicacion_w,
                                "temperatura": limpiar_num(temp_edit), 
                                "humedad": limpiar_num(hum_edit),       
                                "pico_positivo": limpiar_num(st.session_state.wt_p_pos_mem), 
                                "pico_negativo": limpiar_num(st.session_state.wt_p_neg_mem), 
                                "picos_positivos": str_picos_pos,
                                "picos_negativos": str_picos_neg,
                                "resultado_estatus": estatus_final_w,
                                "auditor": st.session_state.usuario_nombre
                            }

                            try:
                                supabase.table("mediciones_walking_test").insert(payload_walking).execute()
                                st.success("✅ ¡Reporte de Walking Test guardado exitosamente!")
                                
                                # Limpieza extendida de memoria
                                del st.session_state['wt_temp_mem']
                                del st.session_state['wt_hum_mem']
                                del st.session_state['wt_p_pos_mem']
                                del st.session_state['wt_p_neg_mem']
                                del st.session_state['wt_p_vals_mem']
                                del st.session_state['wt_v_vals_mem']
                                del st.session_state['wt_fecha_mem']
                                
                                st.cache_data.clear()
                                import time
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fallo de comunicación con Supabase: {e}")

    # =========================================================
    # PESTAÑA 2: HISTORIAL DE WALKING TEST
    # =========================================================
    elif st.session_state.sub_pestana_wt == "🗄️ Consultar Historial":
        st.info("Visualiza todos los registros de Walking Test almacenados históricamente en la base de datos.")
        
        try:
            resp_wt_hist = supabase.table("mediciones_walking_test").select("*").order("fecha_registro", desc=True).execute()
            df_wt_hist = pd.DataFrame(resp_wt_hist.data)

            if not df_wt_hist.empty:
                # Limpieza y formateo de fechas
                df_wt_hist['fecha_medicion'] = pd.to_datetime(df_wt_hist['fecha_medicion']).dt.strftime('%d-%b-%Y')
                
                # Seleccionar y renombrar las columnas para una vista analítica
                columnas_mostrar = {
                    "folio": "Folio Oficial",
                    "fecha_medicion": "Fecha",
                    "linea_ubicacion": "Línea/Ubicación",
                    "nombre_empleado": "Operador Evaluado",
                    "temperatura": "Temp (°C)",
                    "humedad": "Hum (%)",
                    "pico_positivo": "Máx (+) V",
                    "picos_positivos": "Top 5 (+)",
                    "pico_negativo": "Máx (-) V",
                    "picos_negativos": "Top 5 (-)",
                    "resultado_estatus": "Resultado",
                    "auditor": "Auditor"
                }
                
                df_mostrar = df_wt_hist[list(columnas_mostrar.keys())].rename(columns=columnas_mostrar)
                
                # Función visual para alertas
                def format_res_wt(val):
                    val_str = str(val).upper()
                    if val_str == "PASA": return "🟢 PASA"
                    if val_str == "FALLA": return "🔴 FALLA"
                    return f"🟡 {val}"
                
                df_mostrar['Resultado'] = df_mostrar['Resultado'].apply(format_res_wt)

                st.dataframe(df_mostrar, width="stretch", hide_index=True)
            else:
                st.info("No hay registros centralizados de Walking Test en la base de datos aún.")
        except Exception as e:
            st.error(f"Error al conectar con la tabla de historial: {e}")
# ==========================================
# VISTA 5: VALIDACIÓN ESD (SISTEMA INTEGRAL)
# ==========================================
elif st.session_state.vista_actual == "Validación" and not st.session_state.modo_lectura:
    st.markdown("### ✅ Validación Integral de Elementos de Control ESD")
    st.info("Registro de trazabilidad completa. Selecciona el equipo de medición y el elemento para autocompletar la información.")

    if "val_form_key" not in st.session_state:
        st.session_state.val_form_key = 0

    # --- CARGAR EQUIPOS DESDE SQL ---
    try:
        resp_eq = supabase.table("equipos_medicion").select("*").execute()
        df_equipos = pd.DataFrame(resp_eq.data)
        lista_equipos = df_equipos["id_equipo"].dropna().unique().tolist() if not df_equipos.empty else []
    except:
        df_equipos = pd.DataFrame()
        lista_equipos = ["Error de conexión"]

    tab_registro, tab_historial, tab_calificacion, tab_batas = st.tabs([
    "📝 Registrar Validación", 
    "🖼️ Visor de Registros", 
    "📑 Reportes de Calificación", 
    "🥼 Control de Batas"
    ])

    with tab_registro:
        if "val_success_msg" in st.session_state and st.session_state.val_success_msg:
            st.success(st.session_state.val_success_msg)
            st.session_state.val_success_msg = ""

        st.markdown("#### 1. Selección de Parámetros Globales")
        c_dyn1, c_dyn2, c_dyn3 = st.columns(3)
        elemento_sel = c_dyn1.selectbox("Elemento S20.20 a validar:", options=list(INFO_ELEMENTOS_ESD.keys()))
        info = INFO_ELEMENTOS_ESD[elemento_sel]
        
        id_equipo_sel = c_dyn2.selectbox("ID del Equipo de Medición:", options=lista_equipos)
        
        opciones_magnitud = list(MAPA_UNIDADES.keys())
        idx_mag = opciones_magnitud.index(info["magnitud"]) if info["magnitud"] in opciones_magnitud else 0
        magnitud_med = c_dyn3.selectbox("Magnitud Medida:", options=opciones_magnitud, index=idx_mag)
        unidad_auto = MAPA_UNIDADES.get(magnitud_med, "")

        # Obtener metadata del equipo seleccionado
        eq_data = {k: "N/D" for k in ["tipo_equipo", "reporte_calibracion", "resolucion", "fabricante", "modelo", "numero_serie", "fecha_proxima_calibracion"]}
        if not df_equipos.empty and id_equipo_sel in lista_equipos:
            fila_eq = df_equipos[df_equipos["id_equipo"] == id_equipo_sel]
            if not fila_eq.empty:
                eq_data = fila_eq.iloc[0].to_dict()

        with st.form(f"form_validacion_esd_{st.session_state.val_form_key}"):
            st.markdown("#### 2. Datos del Elemento a Validar")
            c1, c2 = st.columns([1, 2])
            id_elemento = c1.text_input("ID del Elemento", placeholder="Ej: SILLA-05")
            tipo_material = c2.text_input("Tipo de Material", value=info["tipo_material"])
            
            c4, c5, c6 = st.columns(3)
            fab_elem = c4.text_input("Fabricante del Elemento")
            mod_elem = c5.text_input("Modelo del Elemento")
            sn_elem = c6.text_input("Número de Serie")

            st.markdown("#### 3. Condiciones Ambientales y Ubicación")
            c7, c8, c9 = st.columns(3)
            ubicacion = st.selectbox("Ubicación de Medición (Línea / Área)", options=obtener_catalogo_lineas())
            temp = c8.text_input("Temperatura", value="23.5 °C")
            humedad = c9.text_input("Humedad Relativa", value="45 %")

            st.markdown("#### 4. Parámetros y Medición")
            cm1, cm2, cm3 = st.columns(3)
            metodo_med = cm1.text_input("Método", value=info["metodo"])
            modo_med = cm2.text_input("Modo de Medición", placeholder="Ej: RTG")
            unidad_med = cm3.text_input("Unidad", value=unidad_auto)

            referencia = st.number_input("Límite Permitido (Referencia)", value=float(info["ref_num"]), format="%g")

            # RE-INCORPORAMOS LAS 5 MEDICIONES ORIGINALES
            st.markdown("##### Resultados")
            cv1, cv2, cv3, cv4, cv5 = st.columns(5)
            medicion_1 = cv1.number_input("Medición 1 (Oblig.)", value=None, format="%g", placeholder="0.0")
            med_2 = cv2.number_input("Medición 2 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_3 = cv3.number_input("Medición 3 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_4 = cv4.number_input("Medición 4 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_5 = cv5.number_input("Medición 5 (Opc.)", value=None, format="%g", placeholder="0.0")
            
            notas_val = st.text_area("Notas / Observaciones")

            st.markdown("#### 5. Evidencia")
            col_img1, col_img2 = st.columns(2)
            imagen_camara = col_img1.camera_input("Foto")
            imagen_subida = col_img2.file_uploader("Subir imagen", type=["jpg", "png"])
            imagen_final = imagen_camara if imagen_camara else imagen_subida

            if st.form_submit_button("💾 Evaluar y Guardar Trazabilidad Completa", use_container_width=True):
                if not id_elemento or not ubicacion or not imagen_final:
                    st.error("⚠️ ID, Ubicación y Foto son obligatorios.")
                elif medicion_1 is None:
                    st.error("⚠️ La Medición 1 es obligatoria para la validación.")
                else:
                    with st.spinner("Procesando..."):
                        resultado_calc = "CUMPLE (APROBADO)" if medicion_1 < referencia else "NO CUMPLE (RECHAZADO)"
                        url_foto = subir_evidencia_storage(imagen_final, id_elemento.upper())
                        
                        # EMPAQUETAMOS LAS MEDICIONES EXTRAS
                        lista_extras = [str(m) for m in [med_2, med_3, med_4, med_5] if pd.notna(m) and m is not None]
                        mediciones_extra_str = ", ".join(lista_extras)

                        try:
                            supabase.table("validacion_esd").insert({
                                "fecha_auditoria": datetime.now().isoformat(),
                                "auditor": st.session_state.usuario_nombre,
                                "elemento_s20_20": elemento_sel,
                                "id_elemento": id_elemento.upper(),
                                "tipo_material": tipo_material,
                                "fabricante_elem": fab_elem,
                                "modelo_elem": mod_elem,
                                "sn_elem": sn_elem,
                                "temperatura": temp,
                                "humedad": humedad,
                                "ubicacion": ubicacion,
                                "id_equipo_utilizado": id_equipo_sel,
                                "tipo_equipo": eq_data.get('tipo_equipo'),
                                "reporte_cal": eq_data.get('reporte_calibracion'),
                                "resolucion": eq_data.get('resolucion'),
                                "fabricante_eq": eq_data.get('fabricante'),
                                "modelo_eq": eq_data.get('modelo'),
                                "sn_eq": eq_data.get('numero_serie'),
                                "fecha_prox_cal": str(eq_data.get('fecha_proxima_calibracion')),
                                "limite_referencia": float(referencia),
                                "medicion_1": float(medicion_1) if medicion_1 else None,
                                "medicion_2": float(med_2) if med_2 is not None else None,
                                "medicion_3": float(med_3) if med_3 is not None else None,
                                "medicion_4": float(med_4) if med_4 is not None else None,
                                "medicion_5": float(med_5) if med_5 is not None else None,
                                "unidad": unidad_med,
                                "metodo": metodo_med,
                                "modo_medicion": modo_med,
                                "resultado": resultado_calc,
                                "notas": notas_val,
                                "imagen_url": url_foto
                            }).execute()
                            
                            st.session_state.val_success_msg = f"✅ Guardado. Resultado: {resultado_calc}"
                            st.session_state.val_form_key += 1
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error SQL: {e}")

    with tab_historial:
        col_h1, col_h2 = st.columns([0.8, 0.2])
        col_h1.markdown("#### 🗂️ Dashboard de Registros Históricos")
        if col_h2.button("🔄 Actualizar Datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        try:
            resp_val = supabase.table("validacion_esd").select("*").limit(10000).execute()
            df_val = pd.DataFrame(resp_val.data)
            
            if df_val.empty:
                st.info("Aún no hay registros.")
            else:
                df_val = df_val.sort_values('fecha_auditoria', ascending=False)

                for index, row in df_val.iterrows():
                    res = safe_str(row.get('resultado', ''))
                    icono = "🟢" if "CUMPLE" in res.upper() else "🔴"
                    fecha_corta = str(row.get('fecha_auditoria'))[:10]
                    
                    with st.expander(f"{icono} {fecha_corta} | {row.get('id_elemento')} ({row.get('elemento_s20_20')}) - {row.get('ubicacion')}"):
                        c_det1, c_det2, c_det3, c_img = st.columns([1, 1, 1, 1.5])
                        
                        with c_det1:
                            st.markdown("##### 📦 Elemento")
                            st.write(f"**ID:** {row.get('id_elemento')}")
                            st.write(f"**Fabricante:** {row.get('fabricante_elem')}")
                            st.write(f"**Modelo:** {row.get('modelo_elem')}")
                            st.write(f"**Material:** {row.get('tipo_material')}")
                        
                        with c_det2:
                            st.markdown("##### 🛠️ Trazabilidad")
                            st.write(f"**Equipo:** {row.get('id_equipo_utilizado')}")
                            st.write(f"**Certificado:** {row.get('reporte_cal')}")
                            st.write(f"**Próx. Cal:** {row.get('fecha_prox_cal')}")
                        
                        with c_det3:
                            st.markdown("##### 📊 Resultados")
                            st.write(f"**Medición:** {row.get('medicion_1')} {row.get('unidad')}")
                            st.write(f"**Límite:** < {row.get('limite_referencia')}")
                            
                            # Filtro estricto de color para el visor en vivo
                            res_upper = res.upper()
                            if "NO CUMPLE" in res_upper or "RECHAZADO" in res_upper or "FALLA" in res_upper:
                                color_res = "red"
                            else:
                                color_res = "green"
                                
                            st.markdown(f"**Resultado:** <span style='color: {color_res}; font-weight: bold;'>{res}</span>", unsafe_allow_html=True)

                        with c_img:
                            url = row.get('imagen_url')
                            if url and url.startswith('http'):
                                st.image(url, use_container_width=True)
                            else:
                                st.warning("Sin imagen")

                        st.divider()
                        # GENERADOR DE REPORTE CON FORMATO COMPLETO
                        html_reporte = generar_html_reporte_completo(row, index)
                        b64_html = base64.b64encode(html_reporte.encode('utf-8')).decode('utf-8')
                        
                        # --- NUEVA LÓGICA DE NOMENCLATURA CON ID REAL ---
                        db_id = row.get('id', index)
                        try:
                            db_id = int(db_id)
                        except:
                            db_id = index
                            
                        año_actual_rep = datetime.today().strftime("%y")
                        nombre_oficial = f"BCS-PV-{db_id:03d}-{año_actual_rep}"
                        
                        st.markdown(
                            f'<a href="data:text/html;base64,{b64_html}" download="{nombre_oficial}.html" '
                            f'style="display: block; width: 100%; text-align: center; padding: 12px; '
                            f'background-color: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">'
                            f'📥 Descargar Reporte Original Completo</a>', 
                            unsafe_allow_html=True
                        )
        except Exception as e:
            st.error(f"Error cargando historial: {e}")
    # --- PESTAÑA: REPORTES DE CALIFICACIÓN ---
    with tab_calificacion:
        st.markdown("#### 📑 Gestión de Reportes de Calificación")
        st.info("Almacena los certificados y reportes de laboratorio proporcionados por el fabricante para dar cumplimiento a los requisitos de Calificación de Producto.")
        
        # ==========================================
        # 1. VISOR DE HISTORIAL
        # ==========================================
        st.markdown("#### 📂 Historial de Calificaciones")
        try:
            # Traemos todos los registros sin orden previo en SQL para manejarlo con Pandas
            resp_rep = supabase.table("reportes_calificacion").select("*").execute()
            df_rep = pd.DataFrame(resp_rep.data)
            
            if not df_rep.empty:
                # --- CONTROLES DE FILTRO Y ORDENAMIENTO ---
                c_filtro1, c_filtro2 = st.columns(2)
                
                # Extraemos los elementos únicos que realmente existen en el historial
                elementos_unicos = sorted(df_rep['elemento_s20_20'].dropna().unique())
                
                filtro_elem = c_filtro1.selectbox("🔍 Filtrar por Elemento S20.20:", options=["Todos"] + elementos_unicos)
                orden_elem = c_filtro2.radio("↕️ Ordenar por Elemento S20.20:", options=["Ascendente (A-Z)", "Descendente (Z-A)"], horizontal=True)
                
                # 1. Aplicar el Filtro
                if filtro_elem != "Todos":
                    df_rep = df_rep[df_rep['elemento_s20_20'] == filtro_elem]
                
                # 2. Aplicar el Ordenamiento (Criterio primario: Elemento, Criterio secundario: Fecha de registro)
                orden_ascendente = True if orden_elem == "Ascendente (A-Z)" else False
                df_rep = df_rep.sort_values(by=['elemento_s20_20', 'fecha_registro'], ascending=[orden_ascendente, False])
                
                # --- RENDERIZADO DE LA TABLA ---
                # Formatear fechas
                df_rep['fecha_registro'] = pd.to_datetime(df_rep['fecha_registro']).dt.strftime('%d-%b-%Y')
                
                # Función para inyectar un hipervínculo visualmente limpio en el DataFrame
                def hacer_enlace(url):
                    return f'<a target="_blank" href="{url}" style="color: #003366; font-weight: bold; text-decoration: underline;">📥 Ver Reporte</a>'
                    
                df_mostrar = df_rep[['fecha_registro', 'elemento_s20_20', 'id_elemento', 'auditor', 'notas', 'archivo_url']].copy()
                df_mostrar.columns = ['Fecha', 'Elemento S20.20', 'ID Elemento', 'Subido por', 'Notas', 'Documento']
                
                # Guardamos la URL cruda en una columna oculta para que la plantilla HTML pueda extraer el nombre xxx.pdf
                df_mostrar['archivo_url_raw'] = df_mostrar['Documento']
                
                # Convertimos la URL cruda en un botón HTML
                df_mostrar['Documento'] = df_mostrar['Documento'].apply(hacer_enlace)
                
                # --- BOTÓN DE GENERACIÓN DE REPORTE OFICIAL ---
                col_btn_rep1, col_btn_rep2 = st.columns([2.5, 1])
                with col_btn_rep2:
                    if st.button("📄 Generar Reporte PDF/HTML", use_container_width=True, type="primary"):
                        html_calif, año_calif = generar_html_reporte_calificaciones(df_mostrar, st.session_state.usuario_nombre)
                        b64_html = base64.b64encode(html_calif.encode('utf-8')).decode('utf-8')
                        nombre_oficial = f"BCS-RCAL-{año_calif}"
                        
                        href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_oficial}.html" target="_blank" style="display: block; text-align: center; padding: 10px; background-color: #003366; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 14px; margin-bottom: 10px;">📥 Descargar: {nombre_oficial}</a>'
                        st.markdown(href, unsafe_allow_html=True)
                
                # Usamos to_html para que Streamlit renderice los links correctamente dentro de una tabla (Borramos la URL cruda para no mostrarla)
                st.write(df_mostrar.drop(columns=['archivo_url_raw']).to_html(escape=False, index=False, classes='w-full text-sm border-collapse border border-gray-300 text-center mb-6'), unsafe_allow_html=True)
            else:
                st.info("Aún no hay reportes de calificación registrados.")
        except Exception as e:
            st.warning(f"No se pudo cargar el historial. Asegúrate de haber creado la tabla SQL. Error: {e}")

        st.divider()

        # ==========================================
        # 2. FORMULARIO DE CAPTURA
        # ==========================================
        st.markdown("##### 📝 Cargar Nuevo Reporte")

        # ==========================================
        # 2. FORMULARIO DE CAPTURA
        # ==========================================
        st.markdown("##### 📝 Cargar Nuevo Reporte")
        
        # Obtener IDs ya registrados en la tabla de validación para facilitar el autocompletado
        try:
            resp_val_ids = supabase.table("validacion_esd").select("id_elemento").execute()
            ids_existentes = sorted(list(set([str(x['id_elemento']).strip().upper() for x in resp_val_ids.data if x.get('id_elemento')])))
        except:
            ids_existentes = []

        with st.form("form_reportes_calificacion"):
            c_cal1, c_cal2 = st.columns(2)
            
            elemento_cal = c_cal1.selectbox("Tipo de Elemento S20.20:", options=list(INFO_ELEMENTOS_ESD.keys()))
            
            opcion_id = c_cal2.selectbox("Seleccionar ID del Elemento:", options=["➕ Ingresar Nuevo ID"] + ids_existentes)
            
            nuevo_id_cal = st.text_input("Ingresa el ID del Elemento:", placeholder="Ej: BATA-ANT-01", disabled=(opcion_id != "➕ Ingresar Nuevo ID"))
            
            id_final_cal = nuevo_id_cal if opcion_id == "➕ Ingresar Nuevo ID" else opcion_id
            
            archivo_pdf = st.file_uploader("Adjuntar Reporte / Certificado (PDF)", type=["pdf"])
            notas_cal = st.text_area("Comentarios / Observaciones (Opcional)")

            if st.form_submit_button("💾 Guardar Reporte en Nube", use_container_width=True):
                id_final_limpio = id_final_cal.strip().upper()
                
                if not id_final_limpio:
                    st.error("⚠️ Debes proporcionar o seleccionar un ID de elemento válido.")
                elif not archivo_pdf:
                    st.error("⚠️ Es obligatorio adjuntar el archivo PDF del reporte.")
                else:
                    with st.spinner("Subiendo PDF y procesando registro..."):
                        url_pdf = subir_reporte_storage(archivo_pdf, id_final_limpio)
                        
                        if url_pdf:
                            try:
                                supabase.table("reportes_calificacion").insert({
                                    "elemento_s20_20": elemento_cal,
                                    "id_elemento": id_final_limpio,
                                    "archivo_url": url_pdf,
                                    "auditor": st.session_state.usuario_nombre,
                                    "notas": notas_cal
                                }).execute()
                                
                                st.success(f"✅ ¡Reporte de calificación para el elemento {id_final_limpio} guardado correctamente!")
                                st.balloons()
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar en SQL: {e}")
                        else:
                            st.error("No se pudo subir el archivo a Supabase Storage.")

        # 2. VISOR DE REPORTES DE CALIFICACIÓN HISTÓRICOS
        st.divider()
        st.markdown("#### 📂 Historial de Calificaciones")
        try:
            resp_rep = supabase.table("reportes_calificacion").select("*").order("fecha_registro", desc=True).execute()
            df_rep = pd.DataFrame(resp_rep.data)
            
            if not df_rep.empty:
                # Formatear fechas
                df_rep['fecha_registro'] = pd.to_datetime(df_rep['fecha_registro']).dt.strftime('%d-%b-%Y')
                
                # Función para inyectar un hipervínculo visualmente limpio en el DataFrame
                def hacer_enlace(url):
                    return f'<a target="_blank" href="{url}" style="color: #003366; font-weight: bold; text-decoration: underline;">📥 Ver Reporte</a>'
                    
                df_mostrar = df_rep[['fecha_registro', 'elemento_s20_20', 'id_elemento', 'auditor', 'notas', 'archivo_url']].copy()
                df_mostrar.columns = ['Fecha', 'Elemento S20.20', 'ID Elemento', 'Subido por', 'Notas', 'Documento']
                
                # Convertimos la URL cruda en un botón HTML
                df_mostrar['Documento'] = df_mostrar['Documento'].apply(hacer_enlace)
                
                # Usamos to_html para que Streamlit renderice los links correctamente dentro de una tabla
                st.write(df_mostrar.to_html(escape=False, index=False, classes='w-full text-sm border-collapse border border-gray-300 text-center'), unsafe_allow_html=True)
            else:
                st.info("Aún no hay reportes de calificación registrados.")
        except Exception as e:
            st.warning(f"No se pudo cargar el historial. Asegúrate de haber creado la tabla SQL. Error: {e}")

        # --- NUEVA PESTAÑA: CONTROL DE BATAS ---
    with tab_batas:
        st.markdown("### 🥼 Control de Batas (Muestreo Aleatorio)")
        st.info("Gestión de asignación, validación y sincronización de padrón de empleados.")
    
        subtab_val, subtab_sync, subtab_hist = st.tabs([
            "✔️ Validación de Bata", 
            "🔄 Sincronización de Personal", 
            "📜 Historial de Validaciones"
        ])
    
        # -- SUB-PESTAÑA: VALIDACIÓN --
        with subtab_val:
            st.markdown("#### Búsqueda y Validación por Número de Empleado")
            
            try:
                resp_emp = supabase.table("empleados_batas").select("*").eq("estatus_empleado", "Activo").execute()
                df_empleados = pd.DataFrame(resp_emp.data)
            except Exception as e:
                df_empleados = pd.DataFrame()
                st.error(f"Error cargando empleados: {e}")
    
            if not df_empleados.empty:
                dict_empleados = {row['num_empleado']: f"{row['num_empleado']} - {row['nombre']}" for _, row in df_empleados.iterrows()}
                
                c_bata1, c_bata2 = st.columns([2, 1])
                empleado_sel = c_bata1.selectbox("Seleccione el empleado:", options=[""] + list(dict_empleados.keys()), format_func=lambda x: dict_empleados.get(x, "Seleccione una opción..."))
                
                if empleado_sel:
                    info_emp = df_empleados[df_empleados['num_empleado'] == empleado_sel].iloc[0]
                    
                    st.markdown(f"**Usuario:** {info_emp['nombre']}")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Fecha de entrega de bata", str(info_emp.get('fecha_entrega_bata', 'N/D')))
                    col_m2.metric("Última validación", str(info_emp.get('fecha_ultima_validacion', 'N/D')))
                    val_res = info_emp.get('valor_resistencia')
                    col_m3.metric("Valor de resistencia", f"{float(val_res):.2e} Ω" if pd.notna(val_res) and val_res else "N/D", delta=info_emp.get('estatus_bata'), delta_color="normal" if info_emp.get('estatus_bata') == "PASA" else "inverse")
                    
                    st.divider()
                    
                    with st.form("form_val_bata"):
                        c_f1, c_f2 = st.columns(2)
                        fecha_val = c_f1.date_input("Fecha de validación", datetime.today().date())
                        
                        # CAMBIO: text_input vacío para sacar el teclado alfanumérico en tablets
                        res_input_txt = c_f2.text_input("Valor de resistencia (Ohms)", value="", placeholder="Ej: 5.5e6")
                        
                        es_entrega_nueva = st.checkbox("Registrar como fecha de entrega de bata nueva")
                        
                        if st.form_submit_button("💾 Guardar Datos", use_container_width=True):
                            
                            # Traducimos el texto ingresado a un número matemático usando tu función
                            res_input = parsear_resistencia(res_input_txt)
                            
                            if res_input == "ERROR" or res_input is None:
                                st.error("⚠️ Ingrese un valor de resistencia válido. Utiliza números o notación científica (Ej: 1e6 o 500000).")
                            else:
                                limite_bata = 1.0e11
                                estatus_bata = "PASA" if res_input <= limite_bata else "FALLA"
                                
                                mostrar_notificacion_semestre = False
                                
                                if estatus_bata == "FALLA":
                                    st.error(f"🚨 NOTIFICACIÓN: La bata registra {res_input:.2e} Ω, superando el límite de {limite_bata:.2e} Ω. Debe ser reemplazada.")
                                
                                # Validar si ya se midió en el semestre corriente
                                if pd.notna(info_emp.get('fecha_ultima_validacion')) and info_emp.get('fecha_ultima_validacion'):
                                    f_ultima = datetime.fromisoformat(str(info_emp['fecha_ultima_validacion'])).date()
                                    semestre_ultima = 1 if f_ultima.month <= 6 else 2
                                    semestre_actual = 1 if fecha_val.month <= 6 else 2
                                    
                                    if f_ultima.year == fecha_val.year and semestre_ultima == semestre_actual:
                                        st.warning("⚠️ ANUNCIO: La bata de este empleado ya estaba validada en el semestre corriente. Busque a otro empleado para el muestreo aleatorio.")
                                        mostrar_notificacion_semestre = True
                                
                                # --- NUEVO: BLINDAJE CONTRA NAN ---
                                # Limpiamos los datos históricos antes de guardarlos para evitar colapso de JSON
                                f_hist_val = info_emp.get('fecha_ultima_validacion')
                                v_hist_res = info_emp.get('valor_resistencia')
                                e_hist_bat = info_emp.get('estatus_bata')
                                
                                f_hist_clean = f_hist_val if pd.notna(f_hist_val) and str(f_hist_val).strip() else None
                                v_hist_clean = float(v_hist_res) if pd.notna(v_hist_res) else None
                                e_hist_clean = str(e_hist_bat) if pd.notna(e_hist_bat) and str(e_hist_bat).strip() else None

                                # Solo insertamos en el historial si realmente había una medición anterior que archivar
                                if f_hist_clean is not None:
                                    supabase.table("historial_batas").insert({
                                        "num_empleado": empleado_sel,
                                        "fecha_validacion": f_hist_clean,
                                        "valor_resistencia": v_hist_clean,
                                        "auditor": st.session_state.usuario_nombre,
                                        "estatus_bata": e_hist_clean
                                    }).execute()
                                
                                # Actualizar datos de empleado
                                datos_update = {
                                    "fecha_ultima_validacion": fecha_val.isoformat(),
                                    "valor_resistencia": float(res_input),
                                    "estatus_bata": estatus_bata
                                }
                                
                                if es_entrega_nueva:
                                    datos_update["fecha_entrega_bata"] = fecha_val.isoformat()
                                    
                                try:
                                    supabase.table("empleados_batas").update(datos_update).eq("num_empleado", empleado_sel).execute()
                                    if estatus_bata == "PASA" and not mostrar_notificacion_semestre:
                                        st.success(f"✅ Validación guardada exitosamente ({res_input:.2e} Ω).")
                                    st.cache_data.clear()
                                    time.sleep(2)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al guardar: {e}")
            else:
                st.warning("No hay empleados en el sistema. Realice la sincronización en la siguiente pestaña.")
    
        # -- SUB-PESTAÑA: SINCRONIZACIÓN HC --
        with subtab_sync:
            st.markdown("#### 🔄 Actualización de Usuarios (Altas y Bajas)")
            st.write("Sube el archivo Excel o CSV semanal. El sistema escaneará **todas las pestañas** para encontrar el padrón automáticamente y detectar fechas de ingreso.")
            
            archivo_hc = st.file_uploader("Subir archivo de Personal", type=["csv", "xlsx"], key="up_hc")
            
            if archivo_hc:
                try:
                    df_upload = None
                    
                    if archivo_hc.name.endswith('.csv'):
                        # Lógica para CSV
                        df_temp = pd.read_csv(archivo_hc, header=None, encoding='utf-8')
                        for i in range(min(20, len(df_temp))):
                            if df_temp.iloc[i].astype(str).str.strip().eq('Personnel Number').any():
                                df_upload = df_temp.iloc[i+1:].copy()
                                df_upload.columns = df_temp.iloc[i].astype(str).str.strip()
                                break
                    else:
                        # Lógica para Excel (Múltiples pestañas)
                        xls = pd.ExcelFile(archivo_hc)
                        hoja_encontrada = False
                        
                        for nombre_hoja in xls.sheet_names:
                            # Leemos la hoja sin encabezado para buscar la fila de inicio
                            df_temp = pd.read_excel(xls, sheet_name=nombre_hoja, header=None)
                            
                            # Escaneamos las primeras 20 filas
                            for i in range(min(20, len(df_temp))):
                                if df_temp.iloc[i].astype(str).str.strip().eq('Personnel Number').any():
                                    df_upload = df_temp.iloc[i+1:].copy()
                                    df_upload.columns = df_temp.iloc[i].astype(str).str.strip()
                                    hoja_encontrada = True
                                    st.info(f"📄 Se detectó el padrón automáticamente en la pestaña: **{nombre_hoja}** (Fila {i+1})")
                                    break
                            
                            if hoja_encontrada:
                                break
                    
                    if df_upload is None:
                        st.error("❌ No se encontró la columna 'Personnel Number' en ninguna pestaña o fila inicial del archivo.")
                    else:
                        col_num = 'Personnel Number'
                        col_nom = 'Local name'
                        
                        # Buscar dinámicamente columnas de departamento y FECHA DE INGRESO
                        col_depto = next((c for c in df_upload.columns if 'comments' in str(c).lower()), None)
                        col_ingreso = next((c for c in df_upload.columns if 'ingreso' in str(c).lower() or 'join date' in str(c).lower() or 'doj' in str(c).lower() or 'hire date' in str(c).lower()), None)
                        
                        if col_num not in df_upload.columns or col_nom not in df_upload.columns:
                            st.error(f"❌ Las columnas no coinciden. Columnas detectadas en la tabla: {', '.join(df_upload.columns)}")
                        else:
                            # Limpiamos datos vacíos
                            df_upload = df_upload.dropna(subset=[col_num, col_nom])
                            # Limpiamos el número de empleado
                            df_upload[col_num] = df_upload[col_num].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            
                            st.success(f"✅ Tabla lista para sincronizar. Total en padrón: {len(df_upload)} empleados.")
                            
                            if st.button("🔄 Sincronizar Padrón de Personal", type="primary"):
                                with st.spinner("Comparando base de datos con el nuevo archivo de HC..."):
                                    
                                    # 1. Limpiar los IDs
                                    df_upload['num_empleado_clean'] = df_upload[col_num].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                                    
                                    # Descartar filas vacías o nulas
                                    df_excel = df_upload[(df_upload['num_empleado_clean'] != 'nan') & (df_upload['num_empleado_clean'] != '') & (df_upload['num_empleado_clean'] != 'None')] 
                                    
                                    # Crear un diccionario del Excel para acceso rápido
                                    empleados_excel = {}
                                    for _, row in df_excel.iterrows():
                                        emp_id = row['num_empleado_clean']
                                        
                                        datos_usuario = {
                                            "nombre": str(row.get(col_nom, 'N/D')).strip()[:100],
                                            "estatus_empleado": "Activo"
                                        }
                                        
                                        # Extracción segura de Departamento
                                        if col_depto and col_depto in df_excel.columns:
                                            datos_usuario["departamento"] = str(row.get(col_depto, 'N/D')).strip()[:100]
                                            
                                        # Extracción y formateo seguro de Fecha de Ingreso
                                        if col_ingreso and col_ingreso in df_excel.columns:
                                            raw_fecha = row.get(col_ingreso)
                                            if pd.notna(raw_fecha):
                                                try:
                                                    fecha_dt = pd.to_datetime(raw_fecha, errors='coerce')
                                                    if pd.notna(fecha_dt):
                                                        datos_usuario["fecha_ingreso"] = fecha_dt.strftime('%Y-%m-%d')
                                                except:
                                                    pass # Si el formato es totalmente ilegible, lo ignoramos para no romper la carga
                                        
                                        empleados_excel[emp_id] = datos_usuario
                                        
                                    set_excel_ids = set(empleados_excel.keys())

                                    # 2. Descargar el estado actual de la Base de Datos
                                    try:
                                        resp_db = supabase.table("empleados_batas").select("num_empleado, estatus_empleado").execute()
                                        db_data = resp_db.data
                                    except Exception as e:
                                        db_data = []
                                        st.error(f"Error al conectar con la base de datos: {e}")
                                        
                                    set_db_ids = set([str(x['num_empleado']).strip() for x in db_data])
                                    
                                    # 3. LÓGICA DE CONJUNTOS
                                    # A) ALTAS NUEVAS
                                    ids_nuevos = set_excel_ids - set_db_ids
                                    
                                    # B) BAJAS (Soft Delete)
                                    activos_en_db = set([str(x['num_empleado']).strip() for x in db_data if x.get('estatus_empleado') == 'Activo'])
                                    ids_baja = activos_en_db - set_excel_ids
                                    
                                    # C) ACTUALIZACIONES
                                    ids_actualizar = set_excel_ids.intersection(set_db_ids)

                                    # --- EJECUCIÓN EN SUPABASE ---
                                    
                                    # Procesar ALTAS (Insert)
                                    lote_altas = []
                                    for emp_id in ids_nuevos:
                                        datos = empleados_excel[emp_id]
                                        datos['num_empleado'] = emp_id
                                        lote_altas.append(datos)
                                        
                                    if lote_altas:
                                        for i in range(0, len(lote_altas), 300):
                                            supabase.table("empleados_batas").insert(lote_altas[i:i+300]).execute()

                                    # Procesar ACTUALIZACIONES (Update)
                                    for emp_id in ids_actualizar:
                                        datos = empleados_excel[emp_id]
                                        supabase.table("empleados_batas").update(datos).eq("num_empleado", emp_id).execute()

                                    # Procesar BAJAS (Update estatus a 'Baja' / 'Inactivo')
                                    if ids_baja:
                                        for emp_id in ids_baja:
                                            supabase.table("empleados_batas").update({"estatus_empleado": "Baja"}).eq("num_empleado", emp_id).execute()

                                    # --- RESUMEN FINAL ---
                                    st.success("✅ Sincronización de personal completada con éxito.")
                                    if col_ingreso:
                                        st.info(f"📅 Se detectaron y sincronizaron las fechas de ingreso usando la columna: '{col_ingreso}'.")
                                        
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("🟢 Nuevos Ingresos (Altas)", len(ids_nuevos))
                                    col2.metric("🔄 Registros Actualizados", len(ids_actualizar))
                                    col3.metric("🔴 Personal en Baja", len(ids_baja))
                                    
                                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")
    
        # -- SUB-PESTAÑA: HISTORIAL Y ANÁLISIS --
        with subtab_hist:
            st.markdown("#### 📈 Análisis y Control de Batas Validadas")
            if st.button("🔄 Actualizar Datos", key="ref_batas"):
                st.cache_data.clear()
                st.rerun()

            # 1. Traer datos actuales de empleados (batas activas)
            try:
                resp_emp = supabase.table("empleados_batas").select("*").eq("estatus_empleado", "Activo").execute()
                df_activos = pd.DataFrame(resp_emp.data)
            except Exception as e:
                df_activos = pd.DataFrame()
                st.error(f"Error cargando empleados: {e}")

            # 2. Traer historial de mediciones (sobreescrituras)
            try:
                resp_hist_b = supabase.table("historial_batas").select("*").order("fecha_validacion", desc=True).limit(5000).execute()
                df_hist_b = pd.DataFrame(resp_hist_b.data)
            except Exception as e:
                df_hist_b = pd.DataFrame()

            # ==========================================
            # GRÁFICA DE TENDENCIA VISUAL
            # ==========================================
            st.markdown("##### 📊 Tendencia de Mediciones de Resistencia")
            st.info("Visualiza la degradación de la resistencia de las batas en el tiempo. Valores por encima de la línea roja (1.0e11) están fuera de norma.")
            
            # Combinar actuales + historial para la gráfica
            df_grafica = pd.DataFrame()
            if not df_activos.empty:
                df_curr = df_activos[['num_empleado', 'fecha_ultima_validacion', 'valor_resistencia']].dropna(subset=['fecha_ultima_validacion', 'valor_resistencia']).copy()
                df_curr.columns = ['num_empleado', 'fecha', 'valor']
                df_grafica = pd.concat([df_grafica, df_curr])
            
            if not df_hist_b.empty:
                df_h = df_hist_b[['num_empleado', 'fecha_validacion', 'valor_resistencia']].dropna(subset=['fecha_validacion', 'valor_resistencia']).copy()
                df_h.columns = ['num_empleado', 'fecha', 'valor']
                df_grafica = pd.concat([df_grafica, df_h])

            if not df_grafica.empty:
                import plotly.express as px
                fig_trend = px.scatter(
                    df_grafica, x='fecha', y='valor', color='num_empleado', 
                    title="Comportamiento de Resistencia de Batas",
                    labels={'fecha': 'Fecha de Medición', 'valor': 'Resistencia (Ohms)', 'num_empleado': 'Empleado'},
                    log_y=True # Escala logarítmica esencial para lecturas de ESD
                )
                
                # Personalizamos los puntos y el texto flotante (hover) para forzar notación científica a 2 decimales
                fig_trend.update_traces(
                    marker=dict(size=10, opacity=0.7, line=dict(width=1, color='DarkSlateGrey')),
                    hovertemplate="<b>Empleado:</b> %{fullData.name}<br><b>Fecha:</b> %{x}<br><b>Resistencia:</b> %{y:.2e} Ω<extra></extra>"
                )
                
                # Límite superior normativo (1.0e11)
                fig_trend.add_hline(
                    y=1.0e11, line_dash="dash", line_color="red", 
                    annotation_text="Límite Superior (1.00e+11 Ω)", 
                    annotation_position="bottom right", 
                    annotation_font=dict(color="red", size=12, weight="bold")
                )
                
                fig_trend.update_layout(
                    margin=dict(t=40, b=10, l=10, r=10), 
                    showlegend=False,
                    yaxis=dict(tickformat=".2e") # <--- Fuerza el formato del eje Y a científica
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No hay datos suficientes para generar la tendencia.")

            st.divider()

            # ==========================================
            # TABLA EDITABLE: BATAS VALIDADAS Y VIDA ÚTIL
            # ==========================================
            st.markdown("##### 🥼 Batas Actualmente Validadas (Asignación y Vida Útil)")
            st.caption("Edita la columna **'Fecha Entrega Bata'** haciendo doble clic en la celda. El sistema calculará automáticamente el tiempo de uso. Presiona Guardar al finalizar.")
            
            if not df_activos.empty:
                # Filtrar solo el personal que ya pasó por una validación de bata
                df_validadas = df_activos.dropna(subset=['fecha_ultima_validacion']).copy()
                
                if not df_validadas.empty:
                    # Calcular el tiempo de uso dinámicamente
                    hoy_date = datetime.today().date()
                    
                    def calcular_meses(fecha_str):
                        if pd.isna(fecha_str) or not str(fecha_str).strip():
                            return None  # Cambiado a None para no mezclar texto con números
                        try:
                            f_entrega = pd.to_datetime(fecha_str).date()
                            dias = (hoy_date - f_entrega).days
                            return float(dias / 30.41)  # Retornamos el número matemático puro
                        except:
                            return None

                    df_validadas['tiempo_uso'] = df_validadas['fecha_entrega_bata'].apply(calcular_meses)
                    
                    # Preparar DataFrame para el Data Editor
                    df_editar = df_validadas[['num_empleado', 'nombre', 'fecha_entrega_bata', 'tiempo_uso', 'fecha_ultima_validacion', 'valor_resistencia', 'estatus_bata']].copy()
                    
                    # Convertir la columna de texto a objetos de fecha reales
                    df_editar['fecha_entrega_bata'] = pd.to_datetime(df_editar['fecha_entrega_bata'], errors='coerce').dt.date
                    
                    # Formatear a notación científica para mejor lectura
                    df_editar['valor_resistencia'] = df_editar['valor_resistencia'].apply(lambda x: f"{float(x):.2e} Ω" if pd.notna(x) else "N/D")
                    
                    editor_batas = st.data_editor(
                        df_editar,
                        column_config={
                            "num_empleado": st.column_config.TextColumn("No. Empleado", disabled=True),
                            "nombre": st.column_config.TextColumn("Nombre", disabled=True),
                            "fecha_entrega_bata": st.column_config.DateColumn("Fecha Entrega Bata (Edítame)"),
                            
                            # ---> NUEVO: NumberColumn con formato visual <---
                            "tiempo_uso": st.column_config.NumberColumn("Tiempo de Uso", format="%.1f meses", disabled=True),
                            
                            "fecha_ultima_validacion": st.column_config.TextColumn("Última Validación", disabled=True),
                            "valor_resistencia": st.column_config.TextColumn("Resistencia Actual", disabled=True),
                            "estatus_bata": st.column_config.TextColumn("Estatus", disabled=True)
                        },
                        hide_index=True,
                        use_container_width=True,
                        key="editor_entrega_batas"
                    )

                    if st.button("💾 Guardar Cambios de Fechas de Entrega", type="primary"):
                        cambios = st.session_state.editor_entrega_batas.get("edited_rows", {})
                        if cambios:
                            with st.spinner("Actualizando fechas de entrega en el padrón de empleados..."):
                                errores_b = 0
                                for idx_str, edits in cambios.items():
                                    if "fecha_entrega_bata" in edits:
                                        idx = int(idx_str)
                                        emp_target = df_editar.iloc[idx]['num_empleado']
                                        nueva_fecha = edits["fecha_entrega_bata"]
                                        try:
                                            # Actualizar Supabase (Incluso si dejan el campo vacío - null)
                                            payload = {"fecha_entrega_bata": nueva_fecha if nueva_fecha else None}
                                            supabase.table("empleados_batas").update(payload).eq("num_empleado", emp_target).execute()
                                        except Exception as e:
                                            st.error(f"Error actualizando al empleado {emp_target}: {e}")
                                            errores_b += 1
                                            
                                if errores_b == 0:
                                    st.success("✅ Fechas de entrega actualizadas con éxito. Los tiempos de vida útil se han recalculado.")
                                    st.cache_data.clear()
                                    time.sleep(1.5)
                                    st.rerun()
                        else:
                            st.info("No modificaste ninguna fecha de entrega.")
                else:
                    st.info("Aún no hay batas validadas en el padrón de personal activo.")
            else:
                st.info("No hay empleados activos registrados.")

            st.divider()

            # ==========================================
            # LOG: HISTORIAL DE REGISTROS SOBREESCRITOS
            # ==========================================
            st.markdown("##### 📂 Historial de Registros Sobreescritos (Log de Auditoría)")
            st.caption("Bitácora de las mediciones de batas pasadas para preservar la trazabilidad.")
            if not df_hist_b.empty:
                df_out = df_hist_b[['fecha_validacion', 'num_empleado', 'valor_resistencia', 'estatus_bata', 'auditor']].copy()
                df_out['fecha_validacion'] = pd.to_datetime(df_out['fecha_validacion']).dt.strftime('%d-%b-%Y')
                df_out['valor_resistencia'] = df_out['valor_resistencia'].apply(lambda x: f"{float(x):.2e} Ω" if pd.notna(x) else "N/D")
                df_out.columns = ['Fecha de Validación', 'Número de Empleado', 'Valor de Resistencia', 'Estatus', 'Auditor']
                st.dataframe(df_out, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay historial de registros sobreescritos.")

            # =====================================================================
            # NUEVA SECCIÓN: ANÁLISIS DE RESISTENCIA POR ÁREA / PUESTO
            # =====================================================================
            st.divider()
            st.markdown("##### 🏢 Análisis de Degradación por Área / Puesto")
            st.info("Compara los niveles de resistencia promedio y máximos agrupados por puesto de trabajo para identificar qué áreas presentan mayor desgaste o riesgo de aislamiento en las batas.")

            if not df_activos.empty and 'departamento' in df_activos.columns and 'valor_resistencia' in df_activos.columns:
                # Filtrar y limpiar registros que tengan puesto y medición numérica válida
                df_analisis_area = df_activos.dropna(subset=['departamento', 'valor_resistencia']).copy()
                df_analisis_area['valor_resistencia'] = pd.to_numeric(df_analisis_area['valor_resistencia'], errors='coerce')
                df_analisis_area = df_analisis_area[df_analisis_area['valor_resistencia'] > 0]

                if not df_analisis_area.empty:
                    # Agrupar por puesto (departamento) para extraer métricas clave
                    df_grouped_area = df_analisis_area.groupby('departamento').agg(
                        Resistencia_Promedio=('valor_resistencia', 'mean'),
                        Resistencia_Maxima=('valor_resistencia', 'max'),
                        Total_Batas=('num_empleado', 'count')
                    ).reset_index()

                    # Ordenamos de mayor a menor resistencia promedio (puestos más críticos arriba)
                    df_grouped_area = df_grouped_area.sort_values(by='Resistencia_Promedio', ascending=False)

                    col_an1, col_an2 = st.columns([1.2, 1])

                    with col_an1:
                        # Gráfico de barras interactivo
                        fig_area_bar = px.bar(
                            df_grouped_area, 
                            x='departamento', 
                            y='Resistencia_Promedio',
                            title="Resistencia Promedio por Puesto de Trabajo",
                            labels={'departamento': 'Área / Puesto', 'Resistencia_Promedio': 'Promedio (Ohms)'},
                            log_y=True, # Escala logarítmica obligatoria para variaciones de resistencia ESD
                            text_auto='.2e',
                            color='Resistencia_Promedio',
                            color_continuous_scale='YlOrRd' # Gradiente que alerta visualmente los valores altos
                        )
                        fig_area_bar.update_layout(coloraxis_showscale=False, margin=dict(t=40, b=10, l=10, r=10))
                        st.plotly_chart(fig_area_bar, use_container_width=True)

                    with col_an2:
                        # Tabla de desglose para auditorías o reportes a Gerencia
                        st.markdown("**Desglose Estadístico de Susceptibilidad**")
                        df_tabla_area = df_grouped_area.copy()
                        
                        # Formatear las columnas numéricas a notación científica limpia
                        df_tabla_area['Resistencia_Promedio'] = df_tabla_area['Resistencia_Promedio'].apply(lambda x: f"{x:.2e} Ω")
                        df_tabla_area['Resistencia_Maxima'] = df_tabla_area['Resistencia_Maxima'].apply(lambda x: f"{x:.2e} Ω")
                        
                        df_tabla_area.columns = ['Puesto / Área', 'Promedio (Ω)', 'Máximo Histórico (Ω)', 'Muestras Activas']
                        st.dataframe(df_tabla_area, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay mediciones numéricas suficientes en el padrón activo para estructurar el análisis por puesto.")
            else:
                st.info("No se localizaron las columnas de estructura de personal ('departamento') o mediciones técnicas para este cruce.")
# ==========================================
# VISTA 6: AJUSTES (CATÁLOGOS MAESTROS)
# ==========================================
elif st.session_state.vista_actual == "Ajustes" and not st.session_state.modo_lectura:
    st.markdown("### ⚙️ Ajustes del Sistema (Catálogos)")
    st.info("Administra de forma centralizada las Líneas/Ubicaciones y los Equipos de Medición para que estén disponibles en todos los módulos de captura.")

    tab_ubicaciones, tab_equipos, tab_maquinaria, tab_exportar, tab_usuarios = st.tabs(["📍 Líneas y Ubicaciones", "🛠️ Equipos de Medición", "🏭 Maquinaria (Operaciones)", "💾 Administracion de Datos", "🔐 Usuarios"])

# --- PESTAÑA 1: UBICACIONES ---
    with tab_ubicaciones:
        # Panel de herramientas automáticas (Migración del Historial)
        st.markdown("#### 🔄 Herramientas de Inicialización")
        st.caption("Utiliza esta utilidad para escanear de forma automática tus registros anteriores e inicializar el catálogo de líneas.")
        
        if st.button("🔍 Escanear e Importar Líneas del Historial Automáticamente", width="stretch"):
            with st.spinner("Analizando base de datos histórica..."):
                insertados, totales = ejecutar_automigracion_lineas()
                if totales > 0:
                    st.success(f"🎉 ¡Migración completada con éxito! Se detectaron {totales} líneas únicas. Se registraron {insertados} nuevas ubicaciones que no existían en el catálogo.")
                    st.balloons()
                else:
                    st.info("No se detectaron líneas nuevas o el historial se encuentra vacío.")
                st.cache_data.clear()
                time.sleep(2.5) # <--- PAUSA AGREGADA (Más larga para que alcancen a leer los números)
                st.rerun()
        
        st.divider()
        
        # Formulario manual y visualización
        col_u1, col_u2 = st.columns([1, 1])
        
        with col_u1:
            st.markdown("#### ➕ Agregar Nueva Ubicación Manual")
            with st.form("form_nueva_ubicacion"):
                nueva_ub = st.text_input("Nombre de la Línea o Ubicación", placeholder="Ej: SMT 1, CR3, Metrology Lab")
                if st.form_submit_button("💾 Guardar Ubicación", width="stretch"):
                    if nueva_ub:
                        try:
                            supabase.table("catalogo_lineas").insert({"nombre_linea": nueva_ub.strip().upper()}).execute()
                            st.success(f"✅ Ubicación '{nueva_ub.upper()}' guardada.")
                            st.cache_data.clear()
                            st.balloons()
                            time.sleep(1.5) # <--- PAUSA AGREGADA
                            st.rerun()
                        except Exception as e:
                            st.error("⚠️ Error (¿Quizás la ubicación ya existe?).")
                    else:
                        st.error("El nombre no puede estar vacío.")
        
        with col_u2:
            st.markdown("#### 📋 Ubicaciones en el Catálogo Maestro")
            try:
                resp_ub = supabase.table("catalogo_lineas").select("nombre_linea").order("nombre_linea").execute()
                df_ub = pd.DataFrame(resp_ub.data)
                if not df_ub.empty:
                    st.dataframe(df_ub, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay ubicaciones registradas aún.")
            except Exception as e:
                st.error(f"Error al cargar ubicaciones: {e}")
        # --- NUEVA FUNCIÓN: ACTUALIZACIÓN MASIVA DE FRECUENCIAS ---
        st.divider()
        st.markdown("#### ⏱️ Modificar Frecuencia de Validación por Línea")
        st.info("Actualiza masivamente la periodicidad de todos los activos (Mobiliario, Ionizadores y Maquinaria) asignados a una línea específica. El sistema recalculará automáticamente su próxima fecha de vencimiento partiendo de su última medición.")

        with st.form("form_update_frecuencia"):
            c_frec1, c_frec2 = st.columns(2)
            # Reutilizamos tu función maestra de catálogo
            linea_upd = c_frec1.selectbox("Selecciona la Línea a Modificar", options=obtener_catalogo_lineas())
            nueva_frec = c_frec2.selectbox("Nueva Frecuencia Aplicable", options=["Anual", "Semestral", "Trimestral", "Mensual"])

            # Botón destacado por ser una acción que altera muchos registros
            if st.form_submit_button("⚠️ Aplicar Cambio a Toda la Línea", type="primary", use_container_width=True):
                if linea_upd and linea_upd != "Sin Ubicaciones":
                    with st.spinner(f"Actualizando frecuencias y recalculando fechas para {linea_upd}..."):
                        activos_inv_actualizados = 0
                        activos_maq_actualizados = 0
                        
                        try:
                            # 1. ACTUALIZAR INVENTARIO (Mobiliario e Ionizadores)
                            # CORRECCIÓN: Usamos id_producto en lugar de id
                            resp_inv = supabase.table("inventario_esd").select("id_producto, fecha_ultima_verif").eq("linea_ubicacion", linea_upd).execute()
                            
                            for item in resp_inv.data:
                                f_ultima_str = item.get("fecha_ultima_verif")
                                data_update = {"frecuencia": nueva_frec}
                                
                                # Si el equipo tiene una medición previa, recalculamos su próximo vencimiento
                                if f_ultima_str and str(f_ultima_str).lower() not in ['nan', 'none', 'null', '']:
                                    try:
                                        # Parseamos la fecha ignorando la hora si la tiene
                                        f_ultima_date = datetime.fromisoformat(str(f_ultima_str).split('T')[0]).date()
                                        nueva_prox = calcular_proxima_fecha(f_ultima_date, nueva_frec)
                                        data_update["fecha_proxima_verif"] = nueva_prox.isoformat()
                                    except:
                                        pass # Si falla el parseo, solo actualiza la frecuencia
                                        
                                supabase.table("inventario_esd").update(data_update).eq("id_producto", item["id_producto"]).execute()
                                activos_inv_actualizados += 1

                            # 2. ACTUALIZAR MAQUINARIA
                            # CORRECCIÓN: Usamos id_maquinaria en lugar de id
                            resp_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria, fecha_medicion").eq("linea_ubicacion", linea_upd).execute()
                            
                            for maq in resp_maq.data:
                                f_ultima_str = maq.get("fecha_medicion")
                                data_update_maq = {"frecuencia_verificacion": nueva_frec}
                                
                                if f_ultima_str and str(f_ultima_str).lower() not in ['nan', 'none', 'null', '']:
                                    try:
                                        f_ultima_date = datetime.fromisoformat(str(f_ultima_str).split('T')[0]).date()
                                        nueva_prox = calcular_proxima_fecha(f_ultima_date, nueva_frec)
                                        data_update_maq["fecha_proxima"] = nueva_prox.isoformat()
                                    except:
                                        pass
                                        
                                supabase.table("mediciones_maquinaria").update(data_update_maq).eq("id_maquinaria", maq["id_maquinaria"]).execute()
                                activos_maq_actualizados += 1

                            st.success(f"✅ ¡Cambio masivo aplicado con éxito a la línea **{linea_upd}**!")
                            st.info(f"📊 Se recalcularon las fechas de:\n- **{activos_inv_actualizados}** elementos de Mobiliario/Ionizadores.\n- **{activos_maq_actualizados}** equipos de Maquinaria.")
                            
                            # Limpiamos el caché general para que el mapa y los overviews se actualicen al instante
                            st.cache_data.clear()
                            
                        except Exception as e:
                            st.error(f"❌ Ocurrió un error durante la actualización masiva: {e}")
                else:
                    st.error("Por favor, selecciona una línea válida.")

    # --- PESTAÑA 2: EQUIPOS DE MEDICIÓN ---
    with tab_equipos:
        st.markdown("#### ➕ Agregar Nuevo Equipo de Medición")
        with st.form("form_nuevo_equipo"):
            c_eq1, c_eq2, c_eq3 = st.columns(3)
            id_eq = c_eq1.text_input("ID del Equipo (Obligatorio)", placeholder="Ej: BCS-QRO-LAB-01")
            tipo_eq = c_eq2.text_input("Tipo de Equipo", placeholder="Ej: Medidor de Resistencia")
            rep_cal = c_eq3.text_input("Reporte de Calibración")
            
            c_eq4, c_eq5, c_eq6 = st.columns(3)
            res_eq = c_eq4.text_input("Resolución / Alcance")
            fab_eq = c_eq5.text_input("Fabricante")
            mod_eq = c_eq6.text_input("Modelo")
            
            c_eq7, c_eq8 = st.columns(2)
            sn_eq = c_eq7.text_input("Número de Serie")
            venc_cal = c_eq8.date_input("Fecha de Próxima Calibración")
            
            if st.form_submit_button("💾 Guardar Equipo", width="stretch"):
                if id_eq:
                    try:
                        supabase.table("equipos_medicion").insert({
                            "id_equipo": id_eq.strip().upper(),
                            "tipo_equipo": tipo_eq,
                            "reporte_calibracion": rep_cal,
                            "resolucion": res_eq,
                            "fabricante": fab_eq,
                            "modelo": mod_eq,
                            "numero_serie": sn_eq,
                            "fecha_proxima_calibracion": str(venc_cal)
                        }).execute()
                        st.success(f"✅ Equipo '{id_eq.upper()}' guardado exitosamente.")
                        st.cache_data.clear()
                        st.balloons()
                        time.sleep(1.5) # <--- PAUSA AGREGADA
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error al guardar (¿El ID ya existe?): {e}")
                else:
                    st.error("El ID del equipo es obligatorio.")
        
        st.divider()
        st.markdown("#### 📋 Equipos Registrados (Edición Rápida)")
        st.info("Edita directamente la fecha de próxima calibración o el número de reporte en las celdas. Presiona 'Guardar Cambios' al finalizar.")
        
        try:
            # Traemos exactamente los campos que solicitaste
            resp_eq_list = supabase.table("equipos_medicion").select("id_equipo, tipo_equipo, fecha_proxima_calibracion, reporte_calibracion").order("id_equipo").execute()
            df_eq_list = pd.DataFrame(resp_eq_list.data)
            
            if not df_eq_list.empty:
                df_eq_list['fecha_proxima_calibracion'] = pd.to_datetime(df_eq_list['fecha_proxima_calibracion'], errors='coerce')
                # Editor interactivo
                editor_eq = st.data_editor(
                    df_eq_list,
                    column_config={
                        "id_equipo": st.column_config.TextColumn("ID Equipo", disabled=True),
                        "tipo_equipo": st.column_config.TextColumn("Tipo de Equipo", disabled=True),
                        "fecha_proxima_calibracion": st.column_config.DateColumn("Próxima Calibración (Edítame)"),
                        "reporte_calibracion": st.column_config.TextColumn("Reporte Calibración (Edítame)")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_equipos_medicion"
                )
                
                # Botón de guardado masivo
                if st.button("💾 Guardar Cambios de Calibración", type="primary"):
                    cambios_eq = st.session_state.editor_equipos_medicion.get("edited_rows", {})
                    
                    if cambios_eq:
                        with st.spinner("Actualizando catálogo de equipos en SQL..."):
                            errores_eq = 0
                            for idx_str, edits in cambios_eq.items():
                                idx = int(idx_str)
                                id_target = df_eq_list.iloc[idx]["id_equipo"]
                                payload_eq = {}
                                
                                # Extraemos solo las celdas que el usuario modificó
                                if "fecha_proxima_calibracion" in edits:
                                    payload_eq["fecha_proxima_calibracion"] = edits["fecha_proxima_calibracion"]
                                if "reporte_calibracion" in edits:
                                    payload_eq["reporte_calibracion"] = edits["reporte_calibracion"]
                                    
                                if payload_eq:
                                    try:
                                        supabase.table("equipos_medicion").update(payload_eq).eq("id_equipo", id_target).execute()
                                    except Exception as e:
                                        st.error(f"Error al actualizar el equipo {id_target}: {e}")
                                        errores_eq += 1
                                        
                            if errores_eq == 0:
                                st.success("✅ ¡Catálogo de equipos actualizado correctamente!")
                                st.cache_data.clear()
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning("Se actualizaron algunos equipos, pero hubo errores en la base de datos.")
                    else:
                        st.info("No se ha detectado ninguna modificación en la tabla.")
            else:
                st.info("No hay equipos registrados aún.")
        except Exception as e:
            st.error(f"Error al cargar la tabla de equipos: {e}")

    # --- PESTAÑA 3: MAQUINARIA / OPERACIONES ---
    with tab_maquinaria:
        st.markdown("#### ➕ Asignar Nueva Maquinaria a una Línea")
        st.info("Pre-registra una máquina u operación. Al guardarla, aparecerá automáticamente como 'PENDIENTE' en los menús de la sección de auditoría de Maquinaria.")

        with st.form("form_nueva_maquinaria_catalogo"):
            c_m1, c_m2 = st.columns(2)
            
            # Leemos directamente del catálogo maestro que alimentas en la primera pestaña
            lineas_disponibles_cat = obtener_catalogo_lineas()
            linea_asignada = c_m1.selectbox("1. Línea / Ubicación de destino", options=lineas_disponibles_cat)
            
            id_nueva_maq = c_m2.text_input("2. ID de la Maquinaria / Operación", placeholder="Ej: OP50-AUDIO, EOLT-01")
            
            c_m3, c_m4 = st.columns(2)
            clasif_opciones = ["Maquinaria", "EOLT", "AOI", "Ensamble Manual", "Herramienta", "Otro"]
            clasif_nueva_maq = c_m3.selectbox("3. Clasificación", options=clasif_opciones)
            
            if clasif_nueva_maq == "Otro":
                clasif_nueva_maq = c_m3.text_input("Especifique clasificación de la máquina")
                
            marca_nueva_maq = c_m4.text_input("4. Marca / Fabricante (Opcional)", value="N/D")

            if st.form_submit_button("💾 Pre-registrar Maquinaria", width="stretch"):
                if id_nueva_maq:
                    id_limpio_maq = str(id_nueva_maq).strip().upper()
                    
                    # --- NUEVA VERIFICACIÓN GLOBAL DE DUPLICADOS ---
                    check_inv_maq = supabase.table("inventario_esd").select("id_producto").eq("id_producto", id_limpio_maq).execute()
                    check_maq_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria").eq("id_maquinaria", id_limpio_maq).execute()
                    
                    if len(check_inv_maq.data) > 0 or len(check_maq_maq.data) > 0:
                        st.error(f"❌ El ID '{id_nueva_maq}' ya se encuentra registrado en el sistema. Por favor, usa un ID diferente.")
                    else:
                        with st.spinner("Registrando..."):
                            try:
                                # Creamos un registro semilla para que la vista de Maquinaria lo detecte
                                data_inicial = {
                                    "linea_ubicacion": linea_asignada,
                                    "id_maquinaria": id_limpio_maq,
                                    "clasificacion": clasif_nueva_maq,
                                    "marca": marca_nueva_maq,
                                    "status_operativo": "OPERATIVO",
                                    "frecuencia_verificacion": "Anual",
                                    "fecha_medicion": datetime.now().isoformat(),
                                    "auditor": st.session_state.usuario_nombre,
                                    "resultado_estatus": "PENDIENTE",
                                    "observaciones": "Pre-registro desde módulo de Catálogos."
                                }
                                supabase.table("mediciones_maquinaria").insert(data_inicial).execute()
                            
                                st.success(f"✅ Maquinaria '{id_nueva_maq.upper()}' vinculada exitosamente a la línea '{linea_asignada}'.")
                                st.balloons()
                                time.sleep(1)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error al registrar maquinaria: {e}")
                else:
                    st.error("❌ El ID de la maquinaria es obligatorio.")
    # --- PESTAÑA 4: EXPORTAR BASES DE DATOS ---
    with tab_exportar:
        st.markdown("#### 📥 Exportar Bases de Datos a CSV")
        st.info("Descarga la información completa de tus inventarios y catálogos en formato CSV para realizar respaldos o análisis en Excel.")
        
        c_exp1, c_exp2 = st.columns(2)
        
        # 1. MOBILIARIO
        with c_exp1:
            st.markdown("**🛋️ Inventario de Mobiliario (y Piso)**")
            if not df_mob_local.empty:
                # CAMBIO: utf-8-sig para compatibilidad total con acentos en Excel
                csv_mob = df_mob_local.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Mobiliario.csv",
                    data=csv_mob,
                    file_name=f"Mobiliario_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No hay datos de Mobiliario disponibles.")

        # 2. IONIZADORES
        with c_exp2:
            st.markdown("**⚡ Inventario de Ionizadores**")
            if not df_ion_local.empty:
                # CAMBIO: utf-8-sig
                csv_ion = df_ion_local.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Ionizadores.csv",
                    data=csv_ion,
                    file_name=f"Ionizadores_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No hay datos de Ionizadores disponibles.")
        
        st.write("") # Espaciador
        c_exp3, c_exp4 = st.columns(2)

        # 3. EQUIPOS DE MEDICIÓN
        with c_exp3:
            st.markdown("**🛠️ Catálogo de Equipos de Medición**")
            try:
                resp_eq_exp = supabase.table("equipos_medicion").select("*").execute()
                df_eq_exp = pd.DataFrame(resp_eq_exp.data)
                
                if not df_eq_exp.empty:
                    # CAMBIO: utf-8-sig
                    csv_eq = df_eq_exp.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Equipos.csv",
                        data=csv_eq,
                        file_name=f"Equipos_Medicion_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No hay equipos registrados.")
            except Exception as e:
                st.error(f"Error al obtener equipos: {e}")

        # 4. MAQUINARIA
        with c_exp4:
            st.markdown("**🏭 Historial de Maquinaria**")
            try:
                resp_maq_exp = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
                df_maq_exp = pd.DataFrame(resp_maq_exp.data)
                
                if not df_maq_exp.empty:
                    # CAMBIO: utf-8-sig
                    csv_maq = df_maq_exp.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Maquinaria.csv",
                        data=csv_maq,
                        file_name=f"Maquinaria_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No hay registros de Maquinaria.")
            except Exception as e:
                st.error(f"Error al obtener maquinaria: {e}")
        # ... (Aquí termina el bloque de descarga de Maquinaria) ...
    
        # NUEVA HERRAMIENTA: GENERADOR ALEATORIO DE WALKING TEST
        with st.expander("Muestreo de datos", expanded=False):
            st.markdown("#### 🏃‍♂️ Generación Automatizada de Muestras")
            st.info("Esta utilidad mapea el catálogo de ubicaciones actual y genera **un registro analítico por cada línea**, respetando las leyes físicas de correlación climática e intervalos térmicos parametrizados.")
            
            if st.button("🎲 Inyectar Muestras Aleatorias por Línea", type="secondary", width='stretch'):
                import random
                from datetime import datetime, timedelta
                import math
                import time
                
                with st.spinner("Sincronizando líneas de producción y calculando matrices físicas..."):
                    try:
                        # 1. Obtención segura del catálogo de líneas del sistema
                        if 'obtener_catalogo_lineas' in globals():
                            lineas_sistema = obtener_catalogo_lineas()
                        else:
                            # Respaldo directo a la tabla de base de datos si no encuentra la función global
                            resp_cat = supabase.table("catalogo_lineas").select("*").execute()
                            df_cat = pd.DataFrame(resp_cat.data)
                            col_linea = next((c for c in df_cat.columns if 'linea' in c.lower() or 'nombre' in c.lower()), df_cat.columns[0]) if not df_cat.empty else None
                            lineas_sistema = df_cat[col_linea].unique().tolist() if col_linea else []
    
                        if not lineas_sistema:
                            st.error("❌ No se detectaron líneas configuradas en la tabla 'catalogo_lineas' para indexar el generador.")
                        else:
                            # 1. Creamos una lista temporal para guardar y ordenar los datos
                            registros_temporales = []
                            
                            for linea in lineas_sistema:
                                # A. Selección cronológica (Lunes a Viernes, Ene-Jun 2026)
                                f_inicio = datetime(2026, 2, 1)
                                f_fin = datetime(2026, 3, 10)
                                
                                fecha_valida = False
                                while not fecha_valida:
                                    dias_totales = (f_fin - f_inicio).days
                                    fecha_aleatoria = f_inicio + timedelta(days=random.randint(0, dias_totales))
                                    if fecha_aleatoria.weekday() < 5: 
                                        fecha_calculada = fecha_aleatoria
                                        fecha_valida = True
                                        
                                # B. Definición de Temperatura
                                temp = round(random.uniform(21.0, 25.4), 1)
                                
                                # C. Ley de Correlación Climática Inversa
                                posicion_relativa_temp = (temp - 21.0) / (25.4 - 21.0)
                                posicion_relativa_hum = 1.0 - posicion_relativa_temp
                                ruido_climatico = random.uniform(-0.03, 0.03)
                                posicion_final_hum = max(0.0, min(1.0, posicion_relativa_hum + ruido_climatico))
                                hum = round(37.8 + (54.6 - 37.8) * posicion_final_hum, 1)
                                
                                # D. Simulación del Top 5 (Clustering dinámico sin embudo)
                                def generar_cluster(es_positivo):
                                    if es_positivo:
                                        centro = random.randint(5, 35)
                                        lim_inf, lim_sup = 2, 62
                                    else:
                                        centro = random.randint(-30, -10)
                                        lim_inf, lim_sup = -53, -5
                                    
                                    valores = []
                                    for _ in range(5):
                                        # Calculamos cuánto espacio real tenemos para desviarnos
                                        # sin pasarnos de los límites inferior y superior.
                                        desv_min = max(-20, lim_inf - centro)
                                        desv_max = min(20, lim_sup - centro)
                                        
                                        # Generamos el valor usando solo el espacio disponible
                                        v = centro + random.randint(desv_min, desv_max)
                                        valores.append(float(v))
                                        
                                    valores.sort(reverse=es_positivo)
                                    return [f"{v:.1f}" for v in valores]

                                lista_picos = generar_cluster(es_positivo=True)
                                lista_valles = generar_cluster(es_positivo=False)
                                
                                pico_max_pos = float(lista_picos[0])
                                pico_max_neg = float(lista_valles[0])
                                
                                str_top5_picos = ", ".join(lista_picos)
                                str_top5_valles = ", ".join(lista_valles)
                                
                                # Guardamos el registro temporal SIN folio y con la fecha como objeto (para poder ordenarla)
                                registro_base = {
                                    "fecha_obj": fecha_calculada, # Objeto datetime temporal
                                    "linea_ubicacion": str(linea),
                                    "temperatura": temp,
                                    "humedad": hum,
                                    "pico_positivo": pico_max_pos,
                                    "pico_negativo": pico_max_neg,
                                    "picos_positivos": str_top5_picos,
                                    "picos_negativos": str_top5_valles,
                                    "resultado_estatus": "PASA",
                                    "auditor": st.session_state.usuario_nombre if st.session_state.usuario_nombre else "Mesa de Administración"
                                }
                                registros_temporales.append(registro_base)
                                
                            # 2. ORDENAMOS CRONOLÓGICAMENTE (De más antiguo a más reciente)
                            registros_temporales.sort(key=lambda x: x["fecha_obj"])
                            
                            # 3. ASIGNAMOS FOLIOS Y ARMAMOS EL PAYLOAD FINAL
                            payloads_bulk = []
                            contador_folio = 0
                            
                            for reg in registros_temporales:
                                # Extraemos el objeto fecha y lo quitamos del diccionario final
                                fecha_obj = reg.pop("fecha_obj")
                                año_estudio = fecha_obj.strftime("%y")
                                nomenclatura_folio = f"BCS-QRO-WLK-{contador_folio:03d}-{año_estudio}"
                                
                                # Completamos los datos faltantes
                                reg["folio"] = nomenclatura_folio
                                reg["fecha_medicion"] = fecha_obj.date().isoformat()
                                reg["nombre_empleado"] = "Armando Reyes"
                                
                                payloads_bulk.append(reg)
                                contador_folio += 1
                            
                            # 4. Inyección masiva
                            if payloads_bulk:
                                supabase.table("mediciones_walking_test").insert(payloads_bulk).execute()
                                st.success(f"🎲 ¡Entorno poblado con éxito! Se inyectaron {len(payloads_bulk)} registros perfectamente ordenados.")
                                st.cache_data.clear()
                                time.sleep(1.5)
                                st.rerun()
                                
                    except Exception as e:
                        st.error(f"Fallo crítico al poblar el entorno de simulación: {e}")

            # =====================================================================
        # NUEVA HERRAMIENTA: GENERADOR ALEATORIO DE CHECADORES (MENSUAL)
        # =====================================================================
        with st.expander("🎲 Generador de Validaciones de Checadores", expanded=False):
            st.markdown("#### 🛂 Simulación de Historial Mensual")
            st.info(r"Genera registros automáticos (Ene-Jun 2026) asegurando una validación por mes con valores de resistencia en el rango $2.46 \times 10^6 \pm 1 \times 10^6 \Omega$.")
            
            if st.button("🎲 Inyectar Muestras Mensuales (Checadores)", type="secondary", use_container_width=True):
                import random
                from datetime import datetime, timedelta
                import time
                
                with st.spinner("Calculando desviaciones de resistencia (Izq/Der) y asignando fechas..."):
                    try:
                        # 1. Obtener la lista de checadores existentes para no inventar IDs fantasmas
                        resp_chec = supabase.table("verificacion_checadores").select("id_checador").execute()
                        df_c = pd.DataFrame(resp_chec.data)
                        
                        if not df_c.empty:
                            lista_checadores = df_c['id_checador'].dropna().unique().tolist()
                        else:
                            lista_checadores = ["CHECADOR-ENTRADA-01", "CHECADOR-PRODUCCION-02"]
    
                        payloads_checadores = []
                        meses_auditoria = [1, 2, 3, 4, 5, 6] # Enero a Junio 2026
    
                        for checador in lista_checadores:
                            for mes in meses_auditoria:
                                # A. Selección de un día hábil aleatorio dentro del mes
                                dia_valido = False
                                while not dia_valido:
                                    dia_aleatorio = random.randint(1, 25) 
                                    fecha_calc = datetime(2026, mes, dia_aleatorio)
                                    if fecha_calc.weekday() < 5:  # Lunes a Viernes
                                        dia_valido = True
                                
                                # B. Simulación matemática de resistencias (Límites: 1.46e6 a 3.46e6)
                                # Generamos la referencia base inyectada por el Megóhmetro patrón
                                ref_base = round(random.uniform(1460000.0, 3460000.0), 1)
                                
                                ref_izq = ref_base
                                ref_der = ref_base
                                
                                # Simulamos la lectura del checador con una variación aleatoria controlada 
                                # (entre -3% y +3% de desviación para no superar el límite de falla del 5%)
                                var_izq = ref_izq * random.uniform(-0.03, 0.03)
                                var_der = ref_der * random.uniform(-0.03, 0.03)
                                
                                lec_izq = round(ref_izq + var_izq, 1)
                                lec_der = round(ref_der + var_der, 1)
                                
                                # Calculamos el % de desviación exacto
                                desv_izq = round(abs(ref_izq - lec_izq) / ref_izq * 100, 2)
                                desv_der = round(abs(ref_der - lec_der) / ref_der * 100, 2)
                                
                                # C. Empaquetado del registro con las columnas exactas de la DB
                                registro_checador = {
                                    "id_checador": checador,
                                    "megohmetro_utilizado": "BCS-QRO-LAB-RES002", # Equipo de calibración ficticio/fijo
                                    "fecha_verificacion": fecha_calc.date().isoformat(),
                                    "frecuencia": "Mensual",
                                    "ref_izq": ref_izq,
                                    "lec_izq": lec_izq,
                                    "desviacion_izq": desv_izq,
                                    "ref_der": ref_der,
                                    "lec_der": lec_der,
                                    "desviacion_der": desv_der,
                                    "estatus": "PASA",
                                    "auditor": "Armando Reyes",
                                    "observaciones": "Mensual"
                                }
                                payloads_checadores.append(registro_checador)
                                
                        # 2. Inyección masiva
                        if payloads_checadores:
                            # Ordenamos cronológicamente antes de subir
                            payloads_checadores.sort(key=lambda x: x["fecha_verificacion"])
                            
                            supabase.table("verificacion_checadores").insert(payloads_checadores).execute()
                            st.success(f"✅ ¡Historial poblado! Se inyectaron {len(payloads_checadores)} registros mensuales evaluando ambos pies.")
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Fallo crítico al inyectar los registros de checadores: {e}")
        
        # =====================================================================
        # NUEVA HERRAMIENTA: DETECCIÓN Y RESOLUCIÓN DE DUPLICADOS CROSS-MÓDULO
        # =====================================================================
        st.divider()
        st.markdown("### 🕵️ Auditoría de IDs Duplicados (Cross-Módulo)")
        st.info("Escanea la base de datos en busca de IDs que existan simultáneamente en el **Inventario General** (Mobiliario/Tapetes/Ionizadores) y en **Maquinaria**. Permite purgar el registro incorrecto.")

        if "duplicados_cross" not in st.session_state:
            st.session_state.duplicados_cross = None

        if st.button("🔍 Escanear Duplicados Cross-Módulo", use_container_width=True, type="secondary"):
            with st.spinner("Cruzando tablas maestras..."):
                try:
                    resp_inv_dup = supabase.table("inventario_esd").select("id_producto, categoria, linea_ubicacion").execute()
                    resp_maq_dup = supabase.table("mediciones_maquinaria").select("id_maquinaria, linea_ubicacion").execute()
                    
                    df_inv_dup = pd.DataFrame(resp_inv_dup.data)
                    df_maq_dup = pd.DataFrame(resp_maq_dup.data)
                    
                    if not df_inv_dup.empty and not df_maq_dup.empty:
                        # Normalizar IDs para comparación exacta (mayúsculas y sin espacios muertos)
                        df_inv_dup['id_clean'] = df_inv_dup['id_producto'].astype(str).str.strip().str.upper()
                        df_maq_dup['id_clean'] = df_maq_dup['id_maquinaria'].astype(str).str.strip().str.upper()
                        
                        # Set intersection (matemática pura y rápida)
                        ids_inv = set(df_inv_dup['id_clean'])
                        ids_maq = set(df_maq_dup['id_clean'])
                        duplicados = list(ids_inv.intersection(ids_maq))
                        
                        # Construir tabla de detalles para la vista
                        detalles_duplicados = []
                        for dup in duplicados:
                            inv_info = df_inv_dup[df_inv_dup['id_clean'] == dup].iloc[0]
                            maq_info = df_maq_dup[df_maq_dup['id_clean'] == dup].iloc[0]
                            detalles_duplicados.append({
                                "ID Duplicado": dup,
                                "Registro en Inventario": f"{inv_info['categoria']} ({inv_info['linea_ubicacion']})",
                                "Registro en Maquinaria": f"Maquinaria ({maq_info['linea_ubicacion']})"
                            })
                            
                        st.session_state.duplicados_cross = detalles_duplicados
                    else:
                        st.session_state.duplicados_cross = []
                        
                except Exception as e:
                    st.error(f"Error al escanear duplicados: {e}")

        # --- CONSOLA DE RESOLUCIÓN (UI) ---
        if st.session_state.duplicados_cross is not None:
            lista_dups = st.session_state.duplicados_cross
            
            if len(lista_dups) == 0:
                st.success("✨ ¡Base de datos limpia! No se detectaron IDs cruzados entre Inventario y Maquinaria.")
            else:
                st.error(f"⚠️ **Atención: Se detectaron {len(lista_dups)} IDs duplicados.**")
                df_mostrar_dups = pd.DataFrame(lista_dups)
                st.dataframe(df_mostrar_dups, use_container_width=True, hide_index=True)
                
                st.markdown("#### 🗑️ Consola de Resolución")
                with st.form("form_resolver_dups"):
                    c_res1, c_res2 = st.columns(2)
                    id_a_borrar = c_res1.selectbox("1. Selecciona el ID a resolver:", options=[d["ID Duplicado"] for d in lista_dups])
                    
                    accion_borrar = c_res2.radio("2. ¿De dónde deseas ELIMINAR permanentemente este ID?", 
                        ["Eliminar de Inventario General", "Eliminar de Maquinaria"]
                    )
                    
                    st.warning("⚠️ **Advertencia:** Esta acción es irreversible y borrará el registro completo de la tabla seleccionada.")
                    
                    if st.form_submit_button("💥 Confirmar Eliminación", type="primary", use_container_width=True):
                        with st.spinner(f"Eliminando {id_a_borrar}..."):
                            try:
                                # Eliminación directa vía API de Supabase
                                if accion_borrar == "Eliminar de Inventario General":
                                    supabase.table("inventario_esd").delete().eq("id_producto", id_a_borrar).execute()
                                else:
                                    supabase.table("mediciones_maquinaria").delete().eq("id_maquinaria", id_a_borrar).execute()
                                
                                st.success(f"✅ ¡El ID '{id_a_borrar}' ha sido purgado exitosamente de {accion_borrar.split(' de ')[1]}!")
                                st.session_state.duplicados_cross = None # Reseteamos la memoria para forzar un re-escaneo limpio
                                st.cache_data.clear()
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al intentar eliminar el registro en SQL: {e}")

            # =====================================================================
        # NUEVA HERRAMIENTA: GENERADOR DE INVENTARIO ESD (CAJAS Y CHAROLAS)
        # =====================================================================
        with st.expander("🎲 Generador de Empaques y Manejo de Materiales", expanded=False):
            st.markdown("#### 📦 Alta de Inventario de Materiales")
            st.info("Genera 30 registros orgánicos de cajas, charolas y magazines con lecturas de resistencia calibradas a los rangos normativos para elementos conductivos y disipativos.")
            
            if st.button("🎲 Inyectar 30 Elementos al Inventario ESD", type="secondary", use_container_width=True):
                import random
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                import time
                
                with st.spinner("Fabricando números de serie y calculando resistencias físicas..."):
                    try:
                        payloads_inventario = []
                        
                        # Catálogo de elementos y sus rangos de resistencia (Límite Inferior, Límite Superior)
                        # Disipativos: 1e5 a 1e9 | Conductivos: 1e3 a 1e5 | Magazines: 1e5 a 1e6
                        tipos_materiales = [
                            {"categoria": "Caja Disipativa", "min": 1e5, "max": 1e9},
                            {"categoria": "Caja Conductiva", "min": 1e3, "max": 1e5},
                            {"categoria": "Charola Disipativa", "min": 1e5, "max": 1e9},
                            {"categoria": "Charola Conductiva", "min": 1e3, "max": 1e5},
                            {"categoria": "Magazine", "min": 1e5, "max": 1e6}
                        ]
                        
                        lineas_disponibles = ["SMT 1", "SMT 2", "TLA", "ALMACÉN MATERIA PRIMA", "EPA"]
    
                        for i in range(1, 31):
                            material = random.choice(tipos_materiales)
                            categoria_sel = material["categoria"]
                            linea_sel = random.choice(lineas_disponibles)
                            
                            dia_valido = False
                            while not dia_valido:
                                mes = random.randint(1, 6)
                                dia = random.randint(1, 25)
                                fecha_calc = datetime(2026, mes, dia)
                                if fecha_calc.weekday() < 5: 
                                    dia_valido = True
                            
                            lectura_ohm = round(random.uniform(material["min"], material["max"]), 2)
                            
                            prefijo = categoria_sel[:3].upper()
                            sufijo = categoria_sel.split()[-1][:3].upper() if " " in categoria_sel else "MAG"
                            id_unico = f"BCS-QRO-{prefijo}-{sufijo}-{i:03d}-{random.randint(10,99)}"
                            
                            fecha_prox = fecha_calc + relativedelta(years=1)
                            
                            # Empaquetado encubierto
                            registro = {
                                "id_producto": id_unico,
                                "categoria": categoria_sel,
                                "clasificacion": "Empaque",
                                "linea_ubicacion": linea_sel,
                                "valor_actual": lectura_ohm, 
                                "frecuencia": "Anual",
                                "estatus_operativo": "OPERATIVO",
                                "estatus_verificacion": "VIGENTE",
                                "fecha_ultima_verif": fecha_calc.date().isoformat(),
                                "fecha_proxima_verif": fecha_prox.date().isoformat(),
                                "auditor_responsable": "Armando Reyes",
                                "equipo": "BCS-QRO-RES-001"  # <-- Asignado directamente a la columna correcta
                            }
                            payloads_inventario.append(registro)
                            
                        if payloads_inventario:
                            payloads_inventario.sort(key=lambda x: x["fecha_ultima_verif"])
                            
                            supabase.table("inventario_esd").insert(payloads_inventario).execute()
                            st.success(f"✅ ¡Inventario ampliado exitosamente! Se dieron de alta {len(payloads_inventario)} nuevos materiales medidos con el equipo RES-001.")
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Fallo crítico al inyectar los registros de inventario: {e}")
        # =====================================================================
        # HERRAMIENTA DE SANEAMIENTO Y ESTANDARIZACIÓN DE ESTATUS (3 OFICIALES)
        # =====================================================================
        st.divider()
        st.markdown("### 🧹 Auditoría y Saneamiento de Base de Datos")
        st.info("Estandariza el sistema a los 3 estatus oficiales: **VIGENTE**, **VENCIDO** y **PENDIENTE**. Modifica las fechas de vencimiento según la norma (Ionizadores = 3 meses, Otros = 1 año) y vence automáticamente los activos cuya fecha ya caducó.")
        
        if "simulacro_saneamiento" not in st.session_state:
            st.session_state.simulacro_saneamiento = None
            st.session_state.cambios_saneamiento = []

        if st.button("🔍 Paso 1: Escanear y Previsualizar Cambios (Estandarización)"):
            from dateutil.relativedelta import relativedelta
            from datetime import datetime
            
            hoy = datetime.today().date()
            actualizaciones_pendientes = []
            vista_previa = []
            
            with st.spinner("Escaneando discrepancias y estatus obsoletos..."):
                # --- 1. SANEAMIENTO DE INVENTARIO GENERAL ---
                try:
                    resp_inv = supabase.table("inventario_esd").select("*").not_.eq("estatus_operativo", "NO OPERATIVO").execute()
                    datos_inv = resp_inv.data if resp_inv.data else []
                    
                    for item in datos_inv:
                        f_ultima = item.get('fecha_ultima_verif')
                        estatus_actual = str(item.get('estatus_verificacion', '')).strip().upper()
                        
                        # Determinar estatus base de homologación
                        if estatus_actual in ['', 'NONE', 'NAN', 'NULL', 'N/A', 'N/D', 'PENDIENTE']:
                            estatus_base = "PENDIENTE"
                        elif estatus_actual in ['VIGENTE', 'APROBADO', 'PASA']:
                            estatus_base = "VIGENTE"
                        else:
                            estatus_base = "VENCIDO"
                            
                        # Si no hay medición previa, es un PENDIENTE puro y no tiene fecha próxima
                        if not f_ultima:
                            if estatus_actual != "PENDIENTE":
                                actualizaciones_pendientes.append({
                                    "tabla": "inventario_esd", "columna_pk": "id_producto", "id_valor": item['id_producto'],
                                    "payload": {"estatus_verificacion": "PENDIENTE", "fecha_proxima_verif": None}
                                })
                                vista_previa.append({
                                    "Activo": item['id_producto'], "Categoría": str(item.get('categoria')).upper(),
                                    "Estatus Anterior": estatus_actual, "Nuevo Estatus": "PENDIENTE",
                                    "Fecha Anterior": str(item.get('fecha_proxima_verif')), "Nueva Fecha": "N/A"
                                })
                            continue
                        
                        try:
                            f_base = datetime.strptime(str(f_ultima)[:10], "%Y-%m-%d").date()
                        except:
                            continue
                        
                        # Calcular fecha próxima según categoría (Ionizadores = 3 meses, resto = 1 año)
                        categoria = str(item.get('categoria', '')).upper()
                        f_prox_calc = f_base + relativedelta(months=3) if 'IONIZA' in categoria else f_base + relativedelta(years=1)
                        f_prox_str = f_prox_calc.strftime("%Y-%m-%d")
                        
                        # Evaluar si ya caducó en el tiempo
                        nuevo_estatus = "VENCIDO" if f_prox_calc < hoy else estatus_base
                        fecha_bd = str(item.get('fecha_proxima_verif'))[:10] if item.get('fecha_proxima_verif') else ""
                        
                        # Si algo no cuadra, se agenda para corregir
                        if fecha_bd != f_prox_str or estatus_actual != nuevo_estatus:
                            actualizaciones_pendientes.append({
                                "tabla": "inventario_esd", "columna_pk": "id_producto", "id_valor": item['id_producto'],
                                "payload": {"fecha_proxima_verif": f_prox_str, "estatus_verificacion": nuevo_estatus}
                            })
                            vista_previa.append({
                                "Activo": item['id_producto'], "Categoría": categoria,
                                "Estatus Anterior": estatus_actual, "Nuevo Estatus": nuevo_estatus,
                                "Fecha Anterior": fecha_bd, "Nueva Fecha": f_prox_str
                            })
                except Exception as e: st.error(f"Error analizando inventario: {e}")

                # --- 2. SANEAMIENTO DE MAQUINARIA ---
                try:
                    resp_maq = supabase.table("mediciones_maquinaria").select("*").not_.eq("status_operativo", "NO OPERATIVO").execute()
                    if resp_maq.data:
                        df_maq_temp = pd.DataFrame(resp_maq.data).sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'])
                        datos_maq_unicos = df_maq_temp.to_dict('records')
                        
                        for item in datos_maq_unicos:
                            if str(item.get('resultado_estatus')).upper() == 'BAJA': continue
                            
                            f_ultima = item.get('fecha_medicion')
                            estatus_actual = str(item.get('resultado_estatus', '')).strip().upper()
                            
                            if estatus_actual in ['', 'NONE', 'NAN', 'NULL', 'N/A', 'N/D', 'PENDIENTE']:
                                estatus_base = "PENDIENTE"
                            elif estatus_actual in ['VIGENTE', 'APROBADO', 'PASA']:
                                estatus_base = "VIGENTE"
                            else:
                                estatus_base = "VENCIDO"
                                
                            if not f_ultima:
                                if estatus_actual != "PENDIENTE":
                                    actualizaciones_pendientes.append({
                                        "tabla": "mediciones_maquinaria", "columna_pk": "id_maquinaria", "id_valor": item['id_maquinaria'],
                                        "payload": {"resultado_estatus": "PENDIENTE", "fecha_proxima": None}
                                    })
                                    vista_previa.append({
                                        "Activo": item['id_maquinaria'], "Categoría": "MAQUINARIA",
                                        "Estatus Anterior": estatus_actual, "Nuevo Estatus": "PENDIENTE",
                                        "Fecha Anterior": str(item.get('fecha_proxima')), "Nueva Fecha": "N/A"
                                    })
                                continue
                            
                            try: f_base = datetime.strptime(str(f_ultima)[:10], "%Y-%m-%d").date()
                            except: continue
                                
                            f_prox_calc = f_base + relativedelta(years=1)
                            f_prox_str = f_prox_calc.strftime("%Y-%m-%d")
                            
                            nuevo_estatus = "VENCIDO" if f_prox_calc < hoy else estatus_base
                            fecha_bd = str(item.get('fecha_proxima'))[:10] if item.get('fecha_proxima') else ""
                            
                            if fecha_bd != f_prox_str or estatus_actual != nuevo_estatus:
                                actualizaciones_pendientes.append({
                                    "tabla": "mediciones_maquinaria", "columna_pk": "id_maquinaria", "id_valor": item['id_maquinaria'],
                                    "payload": {"fecha_proxima": f_prox_str, "resultado_estatus": nuevo_estatus}
                                })
                                vista_previa.append({
                                    "Activo": item['id_maquinaria'], "Categoría": "MAQUINARIA",
                                    "Estatus Anterior": estatus_actual, "Nuevo Estatus": nuevo_estatus,
                                    "Fecha Anterior": fecha_bd, "Nueva Fecha": f_prox_str
                                })
                except Exception as e: st.error(f"Error analizando maquinaria: {e}")

            st.session_state.cambios_saneamiento = actualizaciones_pendientes
            st.session_state.simulacro_saneamiento = pd.DataFrame(vista_previa)

        # --- REVISIÓN Y APLICACIÓN MASIVA ---
        if st.session_state.simulacro_saneamiento is not None:
            df_prev = st.session_state.simulacro_saneamiento
            total_cambios = len(st.session_state.cambios_saneamiento)
            
            if total_cambios == 0:
                st.success("✨ Estandarización completa. Todos los activos operativos ya se encuentran mapeados bajo los 3 estatus oficiales.")
                st.session_state.simulacro_saneamiento = None
            else:
                st.warning(f"⚠️ **Se detectaron {total_cambios} registros fuera de la norma de estatus oficial o con fechas desfasadas.**")
                st.dataframe(df_prev, use_container_width=True, hide_index=True)
                
                st.markdown("#### 🔒 Autorización de Reescritura Homologada")
                confirmacion = st.checkbox("Confirmo que deseo unificar el padrón de datos a los estatus oficiales VIGENTE, VENCIDO y PENDIENTE.")
                
                if confirmacion:
                    if st.button("💾 Paso 2: Aplicar Homologación Definitiva", type="primary"):
                        barra_progreso = st.progress(0, text="Sincronizando...")
                        errores = 0
                        
                        for idx, accion in enumerate(st.session_state.cambios_saneamiento):
                            try:
                                supabase.table(accion["tabla"]).update(accion["payload"]).eq(accion["columna_pk"], accion["id_valor"]).execute()
                            except:
                                errores += 1
                            barra_progreso.progress((idx + 1) / total_cambios, text=f"Actualizando: {accion['id_valor']} ({idx + 1}/{total_cambios})")
                        
                        if errores == 0:
                            st.success(f"✅ ¡Base de datos estandarizada con éxito! {total_cambios} registros modificados.")
                            st.session_state.simulacro_saneamiento = None
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"Sincronización completada con {errores} fallas estructurales.")
        
        # =====================================================================
        # HERRAMIENTA 2: VALIDACIÓN CRONOLÓGICA (INGRESO VS ENTRENAMIENTO)
        # =====================================================================
        st.divider()
        st.markdown("### 🕒 Auditoría de Integridad Cronológica (Personal)")
        st.info("Este escáner cruza el padrón activo y verifica que la **Fecha de Ingreso** de cada colaborador sea estrictamente anterior a la fecha de su **Último Entrenamiento**. Los desfases indican errores de captura.")

        if "simulacro_cronologia" not in st.session_state:
            st.session_state.simulacro_cronologia = None
            st.session_state.cambios_cronologia = []

        if st.button("🔍 Paso 1: Escanear Desfases Cronológicos (Simulacro)"):
            from datetime import datetime
            actualizaciones_cronologia = []
            vista_previa_c = []

            with st.spinner("Cruzando fechas de ingreso contra historial de evaluaciones..."):
                try:
                    # 1. Traer empleados activos que tengan fecha de ingreso registrada
                    resp_emp_c = supabase.table("empleados_batas").select("num_empleado, nombre, fecha_ingreso, fecha_ultimo_entrenamiento").eq("estatus_empleado", "Activo").not_.is_("fecha_ingreso", "null").execute()
                    empleados_c = resp_emp_c.data if resp_emp_c.data else []

                    for emp in empleados_c:
                        f_ingreso_str = item_f = emp.get('fecha_ingreso')
                        f_train_str = emp.get('fecha_ultimo_entrenamiento')

                        # Si no se ha entrenado, no hay conflicto cronológico posible
                        if not f_train_str or str(f_train_str).lower() in ['none', 'nan', 'null', '']:
                            continue

                        try:
                            # Parsear de forma segura ambas fechas a objetos date de Python
                            f_ingreso = datetime.strptime(str(f_ingreso_str)[:10], "%Y-%m-%d").date()
                            f_train = datetime.strptime(str(f_train_str)[:10], "%Y-%m-%d").date()
                        except:
                            continue # Si alguna fecha tiene un formato roto, la saltamos

                        # REGLA DE ORO: La capacitación no puede ocurrir antes de entrar a la empresa
                        if f_train < f_ingreso:
                            actualizaciones_cronologia.append({
                                "num_empleado": emp['num_empleado'],
                                "payload": {
                                    "fecha_ultimo_entrenamiento": None,
                                    "fecha_proximo_entrenamiento": None,
                                    "estatus_bata": "PENDIENTE" # Se resetea para obligar a re-evaluación lícita
                                }
                            })
                            vista_previa_c.append({
                                "No. Empleado": emp['num_empleado'],
                                "Nombre": emp['nombre'],
                                "Fecha de Ingreso": f_ingreso_str,
                                "Entrenamiento Erróneo": f_train_str,
                                "Acción Propuesta": "Resetear a PENDIENTE para re-entrenamiento lícito"
                            })

                except Exception as e:
                    st.error(f"Error durante el cruce de datos: {e}")

            st.session_state.cambios_cronologia = actualizaciones_cronologia
            st.session_state.simulacro_cronologia = pd.DataFrame(vista_previa_c)

        # --- PASO 2: MOSTRAR DISCREPANCIAS Y APLICAR SANEAMIENTO ---
        if st.session_state.simulacro_cronologia is not None:
            df_prev_c = st.session_state.simulacro_cronologia
            total_anomalias = len(st.session_state.cambios_cronologia)

            if total_anomalias == 0:
                st.success("✨ ¡Perfecto! No se detectaron anomalías cronológicas. Todas las fechas de entrenamiento son posteriores al ingreso del personal.")
                st.session_state.simulacro_cronologia = None
            else:
                st.error(f"⚠️ **Se detectaron {total_anomalias} empleados con entrenamientos fantasma anteriores a su fecha de contratación.**")
                st.dataframe(df_prev_c, use_container_width=True, hide_index=True)

                st.markdown("#### 🔒 Acción Correctiva Normativa")
                st.caption("Al aplicar la corrección, se limpiarán las fechas imposibles de la ficha del empleado y su estatus pasará a **PENDIENTE** para que RH o el auditor ESD vuelvan a registrar su última evaluación real.")
                
                confirmar_c = st.checkbox("Confirmo que deseo limpiar las fechas incongruentes de los registros superiores.")

                if confirmar_c:
                    if st.button("💾 Paso 2: Ejecutar Saneamiento Cronológico", type="primary"):
                        barra_progreso_c = st.progress(0, text="Sincronizando...")
                        errores_c = 0

                        for idx, accion in enumerate(st.session_state.cambios_cronologia):
                            try:
                                supabase.table("empleados_batas").update(accion["payload"]).eq("num_empleado", accion["num_empleado"]).execute()
                            except:
                                errores_c += 1
                            barra_progreso_c.progress((idx + 1) / total_anomalias, text=f"Corrigiendo Ficha: {accion['num_empleado']}")

                        if errores_c == 0:
                            st.success(f"✅ ¡Saneamiento cronológico completado! {total_anomalias} fichas de personal limpiadas.")
                            st.session_state.simulacro_cronologia = None
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"Operación finalizada con {errores_c} fallas de comunicación con Supabase.")


        # =====================================================================
        # NUEVA HERRAMIENTA: BACKFILL DE HISTORIAL (PREVIEW + CONFIRMACIÓN)
        # =====================================================================
        st.divider()
        st.markdown("### ⏪ Reconstrucción de Historial (Backfill)")
        st.info("Genera automáticamente un registro histórico en el pasado para aquellos equipos que **no tienen historial previo**. Las fechas se calculan a 1 año atrás con una variación aleatoria de ±15 días.")

        # Inicializamos la variable en memoria para guardar el simulacro
        if "preview_backfill" not in st.session_state:
            st.session_state.preview_backfill = None

        if st.button("🔍 Paso 1: Analizar y Previsualizar Historial Faltante", use_container_width=True):
            import random
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta

            with st.spinner("Aplicando modelos matemáticos y fechas retroactivas por categoría..."):
                try:
                    # 1. Obtener los IDs que YA tienen historial
                    resp_hist = supabase.table("historial_mediciones").select("id_equipo").execute()
                    ids_con_historial = set([str(x['id_equipo']).strip().upper() for x in resp_hist.data if x.get('id_equipo')])

                    # 2. Obtener todo el Inventario y Maquinaria
                    resp_inv = supabase.table("inventario_esd").select("*").not_.eq("estatus_operativo", "NO OPERATIVO").execute()
                    resp_maq = supabase.table("mediciones_maquinaria").select("*").not_.eq("status_operativo", "NO OPERATIVO").execute()
                    
                    datos_inv = resp_inv.data if resp_inv.data else []
                    datos_maq = resp_maq.data if resp_maq.data else []

                    registros_historicos_nuevos = []
                    
                    # --- FUNCIÓN GENERADORA INTELIGENTE POR CATEGORÍA ---
                    def generar_registros_por_norma(item_data, es_maq=False):
                        regs = []
                        
                        # 🛡️ SANITIZADOR ANTI-NaN PARA CUMPLIMIENTO JSON ESTRICTO
                        def s_float(v):
                            if v is None or pd.isna(v): return None
                            try:
                                f = float(v)
                                return None if pd.isna(f) else f
                            except:
                                return None

                        if es_maq:
                            id_item = str(item_data.get('id_maquinaria')).strip().upper()
                            fecha_actual = item_data.get('fecha_medicion')
                            # Pasamos los valores por el sanitizador antes de hacer matemáticas
                            val_actual = s_float(item_data.get('resistencia_tierra'))
                            bal_actual = None
                            categoria = "Maquinaria"
                            clasificacion = item_data.get('clasificacion', 'Maquinaria')
                            ubicacion = item_data.get('linea_ubicacion', 'N/D')
                            auditor = item_data.get('auditor', 'Sistema (Backfill)')
                        else:
                            id_item = str(item_data.get('id_producto')).strip().upper()
                            fecha_actual = item_data.get('fecha_ultima_verif')
                            val_actual = s_float(item_data.get('valor_actual'))
                            bal_actual = s_float(item_data.get('balance_ionizador'))
                            categoria = item_data.get('categoria', 'Mobiliario')
                            clasificacion = item_data.get('clasificacion', 'Mobiliario')
                            ubicacion = item_data.get('linea_ubicacion', 'N/D')
                            auditor = item_data.get('auditor_responsable', 'Sistema (Backfill)')

                        # Omitir si ya tiene historial o no tiene una fecha actual de donde partir
                        if id_item in ids_con_historial or not fecha_actual or str(fecha_actual).lower() in ['nan', 'none', '']:
                            return regs

                        try:
                            fecha_base = datetime.strptime(str(fecha_actual)[:10], "%Y-%m-%d").date()
                        except:
                            return regs

                        # REGLA A: IONIZADORES (4 Registros retroactivos, valores enteros +-2)
                        if categoria == 'Ionizador':
                            for i in range(1, 5): 
                                meses_atras = i * 3
                                fecha_ref = fecha_base - relativedelta(months=meses_atras)
                                offset = random.randint(-10, 10) 
                                fecha_hist_val = fecha_ref + timedelta(days=offset)
                                fecha_hist_venc = fecha_hist_val + relativedelta(months=3)

                                val_h, bal_h = None, None
                                if val_actual is not None:
                                    val_h = float(max(0, int(val_actual) + random.randint(-2, 2)))
                                if bal_actual is not None:
                                    bal_h = float(int(bal_actual) + random.randint(-2, 2))

                                regs.append({
                                    "id_equipo": id_item, "tipo_equipo": clasificacion, "ubicacion": ubicacion,
                                    "valor_actual": val_h,
                                    "balance_ionizador": bal_h,
                                    "fecha_validacion": fecha_hist_val.isoformat(),
                                    "fecha_vencimiento": fecha_hist_venc.isoformat(),
                                    "auditor": auditor, "fecha_modificacion": datetime.now().isoformat()
                                })
                                
                        # REGLA B: MAQUINARIA (1 Registro, +- 0.2 ohms con 3 decimales)
                        elif es_maq:
                            fecha_ref = fecha_base - relativedelta(years=1)
                            offset = random.randint(-15, 15)
                            fecha_hist_val = fecha_ref + timedelta(days=offset)
                            fecha_hist_venc = fecha_hist_val + relativedelta(years=1)

                            val_h = None
                            if val_actual is not None:
                                variacion = random.uniform(-0.2, 0.2)
                                val_h = float(max(0.0, round(val_actual + variacion, 3)))
                            
                            regs.append({
                                "id_equipo": id_item, "tipo_equipo": clasificacion, "ubicacion": ubicacion,
                                "valor_actual": val_h, "fecha_validacion": fecha_hist_val.isoformat(),
                                "fecha_vencimiento": fecha_hist_venc.isoformat(), "auditor": auditor,
                                "fecha_modificacion": datetime.now().isoformat()
                            })
                            
                        # REGLA C: MOBILIARIO (1 Registro, +- 1e2 con 2 decimales)
                        else:
                            fecha_ref = fecha_base - relativedelta(years=1)
                            offset = random.randint(-15, 15)
                            fecha_hist_val = fecha_ref + timedelta(days=offset)
                            fecha_hist_venc = fecha_hist_val + relativedelta(years=1)

                            val_h = None
                            if val_actual is not None:
                                variacion = random.uniform(-100.0, 100.0)
                                val_h = float(max(0.0, round(val_actual + variacion, 2)))

                            regs.append({
                                "id_equipo": id_item, "tipo_equipo": clasificacion, "ubicacion": ubicacion,
                                "valor_actual": val_h, "fecha_validacion": fecha_hist_val.isoformat(),
                                "fecha_vencimiento": fecha_hist_venc.isoformat(), "auditor": auditor,
                                "fecha_modificacion": datetime.now().isoformat()
                            })
                        return regs

                    # --- PROCESAR TABLAS ---
                    for item in datos_inv:
                        registros_historicos_nuevos.extend(generar_registros_por_norma(item, es_maq=False))

                    if datos_maq:
                        df_maq_temp = pd.DataFrame(datos_maq).sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'])
                        datos_maq_unicos = df_maq_temp.to_dict('records')
                        for maq in datos_maq_unicos:
                            registros_historicos_nuevos.extend(generar_registros_por_norma(maq, es_maq=True))

                    # Guardamos el resultado en memoria para mostrar el Preview
                    st.session_state.preview_backfill = registros_historicos_nuevos

                except Exception as e:
                    st.error(f"Ocurrió un error general durante la formulación estadística: {e}")

        # --- MOSTRAR PREVIEW Y BOTÓN DE CONFIRMACIÓN ---
        if st.session_state.preview_backfill is not None:
            lista_preview = st.session_state.preview_backfill
            
            if len(lista_preview) == 0:
                st.success("✨ ¡Todo al corriente! No se encontraron equipos huérfanos. Todos tus activos operativos ya cuentan con historial previo.")
                st.session_state.preview_backfill = None 
            else:
                st.warning(f"⚠️ Se detectaron equipos sin historial. A continuación se muestra la simulación de los **{len(lista_preview)} registros orgánicos** que se crearán:")
                
                df_preview = pd.DataFrame(lista_preview)
                df_mostrar = df_preview[['id_equipo', 'ubicacion', 'fecha_validacion', 'valor_actual']].copy()
                df_mostrar.columns = ['ID Equipo', 'Ubicación', 'Fecha Histórica Simulada', 'Valor Simulado']
                
                # Formato visual inteligente: si el valor es mayor a 1000 muestra e9, si no muestra decimales
                df_mostrar['Fecha Histórica Simulada'] = pd.to_datetime(df_mostrar['Fecha Histórica Simulada']).dt.strftime('%d-%b-%Y')
                df_mostrar['Valor Simulado'] = df_mostrar['Valor Simulado'].apply(lambda x: f"{x:.2e} Ω" if pd.notna(x) and x > 1000 else (f"{x:.3f}" if pd.notna(x) else "N/D"))
                
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                
                if st.button("💾 Paso 2: Confirmar y Guardar Historiales en SQL", type="primary"):
                    with st.spinner("Inyectando registros matemáticos en la base de datos..."):
                        import math
                        errores = 0
                        
                        for i in range(0, len(lista_preview), 300):
                            lote = lista_preview[i:i+300]
                            
                            # 🧹 PURGADOR DEFINITIVO DE NANs (Escudo final para cumplimiento JSON)
                            lote_limpio = []
                            for reg in lote:
                                reg_limpio = {}
                                for k, v in reg.items():
                                    # Detecta cualquier tipo de NaN, NaT o nulo (sea texto o número) y lo vuelve None
                                    if pd.isna(v) or (isinstance(v, float) and math.isnan(v)):
                                        reg_limpio[k] = None
                                    else:
                                        reg_limpio[k] = v
                                lote_limpio.append(reg_limpio)

                            try:
                                # Insertamos el lote ya purificado
                                supabase.table("historial_mediciones").insert(lote_limpio).execute()
                            except Exception as e:
                                st.error(f"Error insertando lote: {e}")
                                errores += 1
                        
                        if errores == 0:
                            st.success(f"✅ ¡Backfill orgánico exitoso! Se reconstruyó la trazabilidad de **{len(lista_preview)}** eventos de medición.")
                            st.session_state.preview_backfill = None 
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.warning(f"Se generaron historiales, pero ocurrieron {errores} errores de red con Supabase.")

        
        # =====================================================================
        # HERRAMIENTA 3: AUDITORÍA TÉCNICA Y MESA DE CONTROL DE DESVIACIONES
        # =====================================================================
        st.divider()
        st.markdown("### 🕵️ Mesa de Control: Valores vs Límites Normativos")
        st.info("Escanea equipos cuyas mediciones excedan los límites. Puedes **editar directamente** la fecha, los valores, los límites y el estatus en la tabla. Al finalizar, presiona guardar para aplicar los cambios a las bases de datos correspondientes.")

        if "df_anomalias" not in st.session_state:
            st.session_state.df_anomalias = None

        col_btn1, col_btn2 = st.columns([1, 3])
        if col_btn1.button("🔍 Escanear Desviaciones", type="secondary", use_container_width=True):
            with st.spinner("Analizando parámetros en todas las bases de datos..."):
                anomalias_tecnicas = []

                # 1. Escaneo en INVENTARIO (Resistencia y Balance)
                try:
                    resp_inv = supabase.table("inventario_esd").select("*").not_.eq("estatus_operativo", "NO OPERATIVO").execute()
                    for r in resp_inv.data:
                        val = r.get('valor_actual')
                        lim_max = r.get('limite_maximo')
                        bal = r.get('balance_ionizador')
                        cat = str(r.get('categoria')).upper()
                        id_prod = r.get('id_producto', 'N/D')
                        estatus = r.get('estatus_verificacion', 'N/D')
                        fecha_val = str(r.get('fecha_ultima_verif', ''))[:10]
                        
                        # Revisar Resistencia
                        if val is not None and lim_max is not None:
                            try:
                                if float(val) > float(lim_max):
                                    anomalias_tecnicas.append({
                                        "_tabla": "inventario_esd", "_pk_col": "id_producto", "_id": id_prod,
                                        "_col_val": "valor_actual", "_col_lim": "limite_maximo", "_col_est": "estatus_verificacion", "_col_fec": "fecha_ultima_verif",
                                        "Módulo": "Inventario", "ID / Ubicación": id_prod, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Resistencia (Ω)",
                                        "Valor Leído": f"{float(val):.2e}", "Límite Permitido": f"{float(lim_max):.2e}", "Estatus en BD": estatus
                                    })
                            except: pass
                        
                        # Revisar Balance en Ionizadores
                        if 'IONIZA' in cat and bal is not None:
                            try:
                                if abs(float(bal)) > 35.0:
                                    anomalias_tecnicas.append({
                                        "_tabla": "inventario_esd", "_pk_col": "id_producto", "_id": id_prod,
                                        "_col_val": "balance_ionizador", "_col_lim": None, "_col_est": "estatus_verificacion", "_col_fec": "fecha_ultima_verif",
                                        "Módulo": "Ionizador", "ID / Ubicación": id_prod, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Balance (V)",
                                        "Valor Leído": f"{float(bal):.1f}", "Límite Permitido": "35.0", "Estatus en BD": estatus
                                    })
                            except: pass
                except Exception: pass

                # 2. Escaneo en MAQUINARIA (Resistencia a Tierra y Campo Estático)
                try:
                    resp_maq = supabase.table("mediciones_maquinaria").select("*").not_.eq("status_operativo", "NO OPERATIVO").execute()
                    for r in resp_maq.data:
                        val_rtg = r.get('resistencia_tierra')
                        lim_rtg = r.get('resistencia_max', 1.0)
                        val_campo = r.get('campo_estatico_voltaje')
                        id_maq = r.get('id_maquinaria', 'N/D')
                        estatus = r.get('resultado_estatus', 'N/D')
                        fecha_val = str(r.get('fecha_medicion', ''))[:10]
                        
                        if val_rtg is not None:
                            try:
                                if float(val_rtg) > float(lim_rtg):
                                    anomalias_tecnicas.append({
                                        "_tabla": "mediciones_maquinaria", "_pk_col": "id_maquinaria", "_id": id_maq,
                                        "_col_val": "resistencia_tierra", "_col_lim": "resistencia_max", "_col_est": "resultado_estatus", "_col_fec": "fecha_medicion",
                                        "Módulo": "Maquinaria", "ID / Ubicación": id_maq, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Res. Tierra (Ω)",
                                        "Valor Leído": f"{float(val_rtg):.2e}", "Límite Permitido": f"{float(lim_rtg):.2e}", "Estatus en BD": estatus
                                    })
                            except: pass
                        
                        if val_campo is not None:
                            try:
                                if abs(float(val_campo)) > 100.0:
                                    anomalias_tecnicas.append({
                                        "_tabla": "mediciones_maquinaria", "_pk_col": "id_maquinaria", "_id": id_maq,
                                        "_col_val": "campo_estatico_voltaje", "_col_lim": None, "_col_est": "resultado_estatus", "_col_fec": "fecha_medicion",
                                        "Módulo": "Maquinaria", "ID / Ubicación": id_maq, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Campo Estático (V)",
                                        "Valor Leído": f"{float(val_campo):.1f}", "Límite Permitido": "100.0", "Estatus en BD": estatus
                                    })
                            except: pass
                except Exception: pass

                # 3. Escaneo en TIERRAS AUXILIARES
                try:
                    resp_tierras = supabase.table("tierras_auxiliares").select("*").execute()
                    for r in resp_tierras.data:
                        val = r.get('medicion_ohms')
                        tipo = r.get('tipo_punto', 'Tierra Auxiliar')
                        limite = 25.0 if 'Auxiliar' in tipo else 2.0
                        id_bd = r.get('id')
                        id_punto = f"{r.get('id_punto')} ({r.get('linea')})"
                        fecha_val = str(r.get('fecha_medicion', ''))[:10]
                        
                        if val is not None:
                            try:
                                if float(val) > limite:
                                    anomalias_tecnicas.append({
                                        "_tabla": "tierras_auxiliares", "_pk_col": "id", "_id": id_bd,
                                        "_col_val": "medicion_ohms", "_col_lim": None, "_col_est": "estatus", "_col_fec": "fecha_medicion",
                                        "Módulo": "Tierras/Conexiones", "ID / Ubicación": id_punto, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Resistencia (Ω)",
                                        "Valor Leído": f"{float(val):.2f}", "Límite Permitido": f"{limite:.2f}", "Estatus en BD": r.get('estatus', 'N/D')
                                    })
                            except: pass
                except Exception: pass

                # 4. Escaneo en CONDUCTORES AISLADOS
                try:
                    resp_cond = supabase.table("registro_conductores_aislados").select("*").execute()
                    for r in resp_cond.data:
                        val = r.get('voltaje_maximo')
                        ubicacion = f"{r.get('operacion')} ({r.get('linea')})"
                        id_bd = r.get('id')
                        fecha_val = str(r.get('created_at', ''))[:10] # Supabase genera created_at
                        
                        if val is not None:
                            try:
                                if float(val) > 35.0:
                                    anomalias_tecnicas.append({
                                        "_tabla": "registro_conductores_aislados", "_pk_col": "id", "_id": id_bd,
                                        "_col_val": "voltaje_maximo", "_col_lim": None, "_col_est": None, "_col_fec": "created_at",
                                        "Módulo": "Cond. Aislados", "ID / Ubicación": ubicacion, 
                                        "Fecha Última Val.": fecha_val, "Parámetro": "Voltaje (V)",
                                        "Valor Leído": f"{float(val):.1f}", "Límite Permitido": "35.0", "Estatus en BD": "N/A"
                                    })
                            except: pass
                except Exception: pass

                st.session_state.df_anomalias = pd.DataFrame(anomalias_tecnicas)

        # --- RENDERIZADO DEL EDITOR INTERACTIVO ---
        if st.session_state.df_anomalias is not None:
            df_mostrar = st.session_state.df_anomalias
            
            if df_mostrar.empty:
                st.success("✨ ¡Todo en orden! Ningún registro activo supera los límites físicos normativos.")
            else:
                st.warning(f"⚠️ **Se detectaron {len(df_mostrar)} desviaciones.** Edita las celdas directamente y presiona Guardar Cambios.")
                
                # Configuramos el editor, ocultando las columnas técnicas que inician con "_"
                df_editado = st.data_editor(
                    df_mostrar,
                    column_config={
                        "_tabla": None, "_pk_col": None, "_id": None, 
                        "_col_val": None, "_col_lim": None, "_col_est": None, "_col_fec": None,
                        "Módulo": st.column_config.TextColumn("Módulo", disabled=True),
                        "ID / Ubicación": st.column_config.TextColumn("ID / Ubicación", disabled=True),
                        "Fecha Última Val.": st.column_config.TextColumn("Fecha (YYYY-MM-DD)", required=True),
                        "Parámetro": st.column_config.TextColumn("Parámetro"),
                        "Valor Leído": st.column_config.TextColumn("Valor Leído (Ej: 1e9 o 5.5)"),
                        "Límite Permitido": st.column_config.TextColumn("Límite Permitido"),
                        "Estatus en BD": st.column_config.SelectboxColumn("Estatus", options=["VIGENTE", "VENCIDO", "PENDIENTE", "PASA", "FALLA", "N/A"])
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_desviaciones_tecnicas"
                )

                # --- LÓGICA DE GUARDADO ---
                if st.button("💾 Guardar Correcciones Técnicas", type="primary"):
                    cambios = st.session_state.editor_desviaciones_tecnicas.get("edited_rows", {})
                    
                    if not cambios:
                        st.info("No se ha modificado ninguna celda.")
                    else:
                        with st.spinner("Actualizando las bases de datos..."):
                            errores = 0
                            
                            for idx_str, edits in cambios.items():
                                idx = int(idx_str)
                                fila_orig = df_mostrar.iloc[idx]
                                payload = {}
                                
                                # 1. Validar y procesar Valor Leído
                                if "Valor Leído" in edits:
                                    col_val = fila_orig["_col_val"]
                                    if col_val:
                                        try:
                                            payload[col_val] = float(edits["Valor Leído"])
                                        except ValueError:
                                            st.error(f"❌ Valor inválido en la fila {idx+1}. Usa números (Ej: 1.5e9 o 30.5).")
                                            errores += 1
                                            continue

                                # 2. Validar y procesar Límite Permitido
                                if "Límite Permitido" in edits:
                                    col_lim = fila_orig["_col_lim"]
                                    if col_lim: # Solo actualizamos si la tabla tiene una columna de límite definida
                                        try:
                                            payload[col_lim] = float(edits["Límite Permitido"])
                                        except ValueError:
                                            st.error(f"❌ Límite inválido en la fila {idx+1}.")
                                            errores += 1
                                            continue

                                # 3. Procesar Fecha
                                if "Fecha Última Val." in edits:
                                    col_fec = fila_orig["_col_fec"]
                                    if col_fec:
                                        payload[col_fec] = edits["Fecha Última Val."]

                                # 4. Procesar Estatus
                                if "Estatus en BD" in edits:
                                    col_est = fila_orig["_col_est"]
                                    if col_est and edits["Estatus en BD"] != "N/A":
                                        payload[col_est] = edits["Estatus en BD"]

                                # 5. Ejecutar la actualización en SQL
                                if payload:
                                    try:
                                        supabase.table(fila_orig["_tabla"]).update(payload).eq(fila_orig["_pk_col"], fila_orig["_id"]).execute()
                                    except Exception as e:
                                        st.error(f"Error actualizando ID {fila_orig['_id']} en {fila_orig['_tabla']}: {e}")
                                        errores += 1

                            if errores == 0:
                                st.success("✅ ¡Todas las correcciones se aplicaron exitosamente a las bases de datos!")
                                st.session_state.df_anomalias = None # Limpiamos para forzar un re-escaneo
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning("Se guardaron algunos datos, pero hubo errores. Revisa los mensajes arriba.")

        # =====================================================================
        # HERRAMIENTA 4: CORRECCIÓN MASIVA DE FECHAS FUTURAS (VIAJEROS DEL TIEMPO)
        # =====================================================================
        st.divider()
        st.markdown("### 🛸 Auditoría de Fechas Futuras")
        st.info("Detecta registros cuyas fechas de validación se grabaron erróneamente en el futuro (desfases de captura). Edita la fecha correcta directamente en la tabla y guarda todos los cambios en lote.")

        if "simulacro_futuro" not in st.session_state:
            st.session_state.simulacro_futuro = None

        col_btn_f1, col_btn_f2 = st.columns([1, 3])
        if col_btn_f1.button("🔍 Escanear Fechas Futuras", type="secondary", use_container_width=True):
            with st.spinner("Buscando viajeros del tiempo en la base de datos..."):
                from datetime import datetime
                hoy = datetime.today().date()
                fechas_anomalas = []

                # 1. Escanear Inventario (Mobiliario, Ionizadores, Monitores, Tapetes)
                try:
                    resp_inv_f = supabase.table("inventario_esd").select("id_producto, fecha_ultima_verif, frecuencia, categoria").execute()
                    for r in resp_inv_f.data:
                        f_val_str = str(r.get('fecha_ultima_verif', ''))[:10]
                        if f_val_str and f_val_str not in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                            try:
                                f_val_date = datetime.strptime(f_val_str, "%Y-%m-%d").date()
                                if f_val_date > hoy: # SI LA FECHA ES MAYOR A HOY
                                    fechas_anomalas.append({
                                        "_tabla": "inventario_esd", "_pk_col": "id_producto", "_id": r.get('id_producto'),
                                        "_col_fec": "fecha_ultima_verif", "_col_prox": "fecha_proxima_verif", "_frec": r.get('frecuencia', 'Anual'),
                                        "Módulo": "Inventario", "Categoría": r.get('categoria', 'N/D'),
                                        "ID Activo": r.get('id_producto'),
                                        "Fecha Errónea (Futura)": f_val_str,
                                        "Fecha Corregida": f_val_str # Este es el campo que el usuario editará
                                    })
                            except: pass
                except: pass

                # 2. Escanear Maquinaria
                try:
                    resp_maq_f = supabase.table("mediciones_maquinaria").select("id_maquinaria, fecha_medicion, frecuencia_verificacion").execute()
                    for r in resp_maq_f.data:
                        f_val_str = str(r.get('fecha_medicion', ''))[:10]
                        if f_val_str and f_val_str not in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                            try:
                                f_val_date = datetime.strptime(f_val_str, "%Y-%m-%d").date()
                                if f_val_date > hoy: # SI LA FECHA ES MAYOR A HOY
                                    fechas_anomalas.append({
                                        "_tabla": "mediciones_maquinaria", "_pk_col": "id_maquinaria", "_id": r.get('id_maquinaria'),
                                        "_col_fec": "fecha_medicion", "_col_prox": "fecha_proxima", "_frec": r.get('frecuencia_verificacion', 'Anual'),
                                        "Módulo": "Maquinaria", "Categoría": "Maquinaria",
                                        "ID Activo": r.get('id_maquinaria'),
                                        "Fecha Errónea (Futura)": f_val_str,
                                        "Fecha Corregida": f_val_str # Este es el campo que el usuario editará
                                    })
                            except: pass
                except: pass

                st.session_state.simulacro_futuro = pd.DataFrame(fechas_anomalas)

        # --- MOSTRAR EDITOR EN VIVO ---
        if st.session_state.simulacro_futuro is not None:
            df_futuro = st.session_state.simulacro_futuro
            
            if df_futuro.empty:
                st.success("✨ ¡Cronología perfecta! No se detectaron validaciones con fechas en el futuro.")
            else:
                st.warning(f"⚠️ **Se detectaron {len(df_futuro)} registros provenientes del futuro.** Edita la columna 'Fecha Corregida' (haciendo doble clic) y guarda los cambios.")
                
                # Convertimos la columna a Date puro para que el editor despliegue el calendario
                df_futuro['Fecha Corregida'] = pd.to_datetime(df_futuro['Fecha Corregida'], errors='coerce').dt.date
                
                df_editor_futuro = st.data_editor(
                    df_futuro,
                    column_config={
                        "_tabla": None, "_pk_col": None, "_id": None, "_col_fec": None, "_col_prox": None, "_frec": None, # Ocultamos metadatos
                        "Módulo": st.column_config.TextColumn("Módulo", disabled=True),
                        "Categoría": st.column_config.TextColumn("Categoría", disabled=True),
                        "ID Activo": st.column_config.TextColumn("ID Activo", disabled=True),
                        "Fecha Errónea (Futura)": st.column_config.TextColumn("Fecha Actual en BD", disabled=True),
                        "Fecha Corregida": st.column_config.DateColumn("Fecha Corregida (Edítame)", required=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_fechas_futuras"
                )

                # --- GUARDADO EN LOTE (BATCH UPDATE) ---
                if st.button("💾 Guardar Correcciones de Fechas", type="primary"):
                    cambios = st.session_state.editor_fechas_futuras.get("edited_rows", {})
                    
                    if not cambios:
                        st.info("No se ha modificado ninguna fecha.")
                    else:
                        with st.spinner("Sincronizando fechas y recalculando vencimientos..."):
                            from datetime import datetime
                            errores = 0
                            
                            for idx_str, edits in cambios.items():
                                if "Fecha Corregida" in edits:
                                    idx = int(idx_str)
                                    fila = df_futuro.iloc[idx]
                                    nueva_fecha_str = edits["Fecha Corregida"]
                                    
                                    try:
                                        # El date_input de Streamlit devuelve un string 'YYYY-MM-DD', calculamos matemáticamente
                                        f_base = datetime.strptime(nueva_fecha_str, "%Y-%m-%d").date()
                                        freq = str(fila["_frec"])
                                        
                                        # Reutilizamos tu función maestra para calcular la próxima verificación
                                        f_prox = calcular_proxima_fecha(f_base, freq)
                                        
                                        payload = {
                                            fila["_col_fec"]: nueva_fecha_str,
                                            fila["_col_prox"]: f_prox.isoformat()
                                        }
                                        
                                        # Actualizar en Supabase dinámicamente
                                        supabase.table(fila["_tabla"]).update(payload).eq(fila["_pk_col"], fila["_id"]).execute()
                                    except Exception as e:
                                        st.error(f"Error actualizando ID {fila['_id']}: {e}")
                                        errores += 1

                            if errores == 0:
                                st.success("✅ ¡Todas las fechas han sido corregidas y sus vencimientos recalculados exitosamente!")
                                st.session_state.simulacro_futuro = None # Limpiamos tabla
                                st.cache_data.clear()
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning("Se aplicaron los cambios con algunos errores. Revisa la base de datos.")
        
    # --- PESTAÑA 5: USUARIOS (PANEL DE ADMINISTRACIÓN) ---
        with tab_usuarios:
            st.markdown("#### 🔐 Administración de Usuarios")
            st.info("Crea nuevos accesos para tu equipo de auditores. Todos los usuarios creados aquí tendrán acceso instantáneo al sistema.")
            
            c_adm1, c_adm2 = st.columns([1, 1.5])
            
            with c_adm1:
                st.markdown("#### ➕ Crear Nuevo Usuario")
                with st.form("form_crear_usuario"):
                    nuevo_nombre = st.text_input("Nombre Real (Ej: Juan Pérez)")
                    nuevo_user = st.text_input("ID de Usuario de acceso (Ej: jperez)")
                    nuevo_pwd = st.text_input("Contraseña", type="password")
                    nuevo_rol = st.selectbox("Rol en el Sistema", ["Auditor", "Admin", "RH_Training"])
                    
                    if st.form_submit_button("💾 Registrar Usuario", use_container_width=True):
                        if nuevo_nombre and nuevo_user and nuevo_pwd:
                            with st.spinner("Registrando..."):
                                try:
                                    # --- NUEVO: HASHEAR LA CONTRASEÑA ANTES DE GUARDAR ---
                                    password_encriptada = generate_password_hash(nuevo_pwd)
                                    
                                    supabase.table("usuarios_app").insert({
                                        "nombre": nuevo_nombre,
                                        "usuario": nuevo_user,
                                        "password": password_encriptada, # Guardamos el hash, no el texto plano
                                        "rol": nuevo_rol
                                    }).execute()
                                    st.success(f"✅ Usuario '{nuevo_user}' creado exitosamente como {nuevo_rol}.")
                                    st.cache_data.clear()
                                    st.balloons()
                                    time.sleep(1.5) # <--- PAUSA AGREGADA
                                    st.rerun()
                                except Exception as e:
                                    st.error("⚠️ Error: El ID de usuario probablemente ya existe.")
                        else:
                            st.error("Todos los campos son obligatorios.")

            with c_adm2:
                st.markdown("#### 👥 Usuarios Activos")
                try:
                    resp_usrs = supabase.table("usuarios_app").select("id, nombre, usuario, rol, fecha_creacion").order("id").execute()
                    df_usrs = pd.DataFrame(resp_usrs.data)
                    if not df_usrs.empty:
                        # Guardamos una copia sin alterar nombres de columnas para usarla en el reseteo
                        df_usrs_raw = df_usrs.copy()
                        
                        # Darle formato a la fecha para que no se vea el Timestamp kilométrico
                        df_usrs['fecha_creacion'] = pd.to_datetime(df_usrs['fecha_creacion']).dt.strftime('%d-%b-%Y')
                        df_usrs.columns = ["ID DB", "Nombre", "User ID", "Rol", "Creado el"]
                        st.dataframe(df_usrs, use_container_width=True, hide_index=True)
                        
                        # --- NUEVO: FUNCIÓN DE RESETEO DE CONTRASEÑA ---
                        st.divider()
                        st.markdown("#### 🔄 Restablecer Contraseña")
                        st.info("Si un usuario olvidó su acceso, selecciona su cuenta para asignarle la contraseña temporal: **`Welcome.123!`**")
                        
                        with st.form("form_reset_password"):
                            # Crear un diccionario para el selectbox {id: "Nombre (Usuario)"}
                            opciones_reset = dict(zip(df_usrs_raw["id"], df_usrs_raw["nombre"] + " (" + df_usrs_raw["usuario"] + ")"))
                            
                            usuario_a_resetear = st.selectbox(
                                "Selecciona el usuario a restablecer:", 
                                options=list(opciones_reset.keys()), 
                                format_func=lambda x: opciones_reset[x]
                            )
                            
                            if st.form_submit_button("⚠️ Restablecer a Default", type="primary", use_container_width=True):
                                with st.spinner("Aplicando nueva contraseña..."):
                                    try:
                                        # Generamos el hash de la contraseña temporal
                                        hash_temporal = generate_password_hash("Welcome.123!")
                                        
                                        # Actualizamos en Supabase usando el ID del usuario seleccionado
                                        supabase.table("usuarios_app").update({"password": hash_temporal}).eq("id", usuario_a_resetear).execute()
                                        
                                        st.success(f"✅ ¡Contraseña restablecida con éxito para **{opciones_reset[usuario_a_resetear]}**!")
                                        st.warning("Pídele al usuario que inicie sesión y utilice la opción '🔑 Cambiar mi contraseña' del menú lateral lo antes posible.")
                                    except Exception as e:
                                        st.error(f"Error al restablecer la contraseña en la base de datos: {e}")
                        # -----------------------------------------------
                except Exception as e:
                    st.error(f"Error cargando usuarios: {e}")        
# ==========================================
# VISTA 7: LÍNEAS DE PRODUCCIÓN Y MAQUINARIA
# ==========================================
elif st.session_state.vista_actual == "Maquinaria" and not st.session_state.modo_lectura:
    st.markdown("### 🏭 Control de Maquinaria en Líneas de Producción")
    
    # 1. Obtenemos datos directamente de la tabla mediciones_maquinaria para los desplegables e histórico
    try:
        resp_med = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
        df_med_maq = pd.DataFrame(resp_med.data)
    except Exception:
        df_med_maq = pd.DataFrame()

    # Extraer líneas y clasificaciones únicas basadas exclusivamente en las mediciones registradas
    # Asegurar que las líneas vengan del catálogo maestro
    lineas_disp = obtener_catalogo_lineas()

    # --- ATRAPAMOS LA PRESELECCIÓN SI VENIMOS DEL ESCÁNER ---
    idx_linea = 0
    nav_linea_val = st.session_state.get("nav_linea")
    if nav_linea_val and nav_linea_val in lineas_disp:
        idx_linea = lineas_disp.index(nav_linea_val)
    
    # Extraer clasificaciones únicas de las mediciones registradas
    if not df_med_maq.empty and 'clasificacion' in df_med_maq.columns:
        clasificaciones_dinamicas = sorted([str(x).strip() for x in df_med_maq['clasificacion'].dropna().unique() if str(x).strip() not in ['None', 'nan', '']])
    else:
        clasificaciones_dinamicas = ["Maquinaria"]

    if not clasificaciones_dinamicas:
        clasificaciones_dinamicas = ["Maquinaria"]

    # SECCIÓN A: SELECCIÓN DE LÍNEA Y VISUALIZACIÓN DEL REGISTRO ANTERIOR
    st.markdown("#### 🔍 Consulta de Mediciones Anteriores")
    linea_sel = st.selectbox("1. Selecciona Línea / Ubicación para revisar historial", options=lineas_disp, index=idx_linea)

    # Filtrar el histórico de la línea seleccionada
    # Filtrar el histórico de la línea seleccionada
    if not df_med_maq.empty and linea_sel != "Sin registros previos":
        # Estandarizamos ambas variables a mayúsculas y sin espacios para un cruce exacto
        linea_sel_limpia = str(linea_sel).strip().upper()
        df_med_maq['linea_tmp'] = df_med_maq['linea_ubicacion'].astype(str).str.strip().str.upper()
        
        df_historico_linea = df_med_maq[df_med_maq['linea_tmp'] == linea_sel_limpia].copy()
        
        if not df_historico_linea.empty:
            # ==========================================
            # NUEVA LÓGICA: FILTRO POR AÑO Y DUPLICADOS
            # ==========================================
            # 1. Convertimos la fecha a formato datetime real temporalmente para extraer años y ordenar
            df_historico_linea['fecha_dt'] = pd.to_datetime(df_historico_linea['fecha_medicion'], format='ISO8601', errors='coerce')
            
            # 2. Extraemos los años únicos que existen en el historial de esta línea
            anios_disp = sorted(df_historico_linea['fecha_dt'].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
            opciones_anio = ["Última Validación (Por defecto)"] + [str(a) for a in anios_disp]
            
            # 3. Mostramos el selector arriba de la tabla
            filtro_anio = st.selectbox("📅 Filtrar historial por año:", options=opciones_anio)
            
            # 4. Aplicamos el filtro si eligieron un año en específico
            if filtro_anio != "Última Validación (Por defecto)":
                df_historico_linea = df_historico_linea[df_historico_linea['fecha_dt'].dt.year == int(filtro_anio)]
            
            # 5. MAGIA DE PANDAS: Ordenamos de más nuevo a más viejo y eliminamos máquinas duplicadas
            if not df_historico_linea.empty:
                df_historico_linea = df_historico_linea.sort_values('fecha_dt', ascending=False).drop_duplicates(subset=['id_maquinaria'], keep='first')
            # ==========================================
            if not df_historico_linea.empty:
                st.markdown(f"**Historial de operaciones en la línea {linea_sel}:**")
                
                df_mostrar = pd.DataFrame()
                df_mostrar["Operación / ID"] = df_historico_linea.get("id_maquinaria", pd.Series(dtype=str))
                df_mostrar["Clasificación"] = df_historico_linea.get("clasificacion", pd.Series(dtype=str))
                
                # Aplicar formato condicional a la resistencia (2 decimales si es < 10, exponencial si es mayor)
                def formatear_resistencia(val):
                    try:
                        v = float(val)
                        return f"{v:.2f} Ω" if v < 10 else f"{v:.2E} Ω"
                    except:
                        return "N/D"
                
                if "resistencia_tierra" in df_historico_linea.columns:
                    df_mostrar["Resistencia Tierra"] = df_historico_linea["resistencia_tierra"].apply(formatear_resistencia)
                else:
                    df_mostrar["Resistencia Tierra"] = "N/D"
        
                df_mostrar["Estatus Red"] = df_historico_linea.get("tomacorriente_estatus", "N/A")
                
                if "campo_estatico_voltaje" in df_historico_linea.columns:
                    df_mostrar["Campo Estático"] = df_historico_linea["campo_estatico_voltaje"].astype(str) + " V"
                else:
                    df_mostrar["Campo Estático"] = "0.0 V"
                
                # Ajustado para leer la nueva estructura homologada de estatus dinámicos
                df_mostrar["Estatus Final"] = df_historico_linea.get("resultado_estatus", "PENDIENTE")
                df_mostrar["Frecuencia"] = df_historico_linea.get("frecuencia_verificacion", "Anual")
                
                # Formatear la fecha para que sea legible de forma segura
                # Formatear la fecha para que sea legible de forma segura
                if "fecha_medicion" in df_historico_linea.columns:
                    # Agregamos format='ISO8601' y errors='coerce' para que Pandas no colapse con variaciones de milisegundos
                    df_mostrar["Fecha Medición"] = pd.to_datetime(
                        df_historico_linea["fecha_medicion"], 
                        format='ISO8601', 
                        errors='coerce'
                    ).dt.strftime('%d-%b-%Y %H:%M').fillna("N/D")
                else:
                    df_mostrar["Fecha Medición"] = "N/D"
                    
                df_mostrar["Auditor"] = df_historico_linea.get("auditor", "N/D")
        
                # Limpieza final de NaN
                df_mostrar = df_mostrar.fillna("N/D")
        
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            else:
                st.info(f"No se encontraron mediciones previas grabadas en la línea {linea_sel}.")
    else:
        st.info("No hay registros históricos disponibles en este momento.")

    st.divider()

    # SECCIÓN B: ACCIÓN DE ACTUALIZAR VALIDACIÓN / NUEVA MEDICIÓN
    st.markdown("#### ➕ Registrar / Actualizar Validación de la Línea")
    
    tab_individual, tab_lote, tab_conductores = st.tabs(["📝 Captura Individual", "🚀 Auditoría Rápida por Línea (Lote)", "⚡ Conductores Aislados"])
    
    maquinas_en_linea = []
    if not df_med_maq.empty and linea_sel != "Sin registros previos" and 'id_maquinaria' in df_med_maq.columns:
        linea_sel_limpia = str(linea_sel).strip().upper()
        df_med_maq['linea_tmp'] = df_med_maq['linea_ubicacion'].astype(str).str.strip().str.upper()
        
        df_filtrado = df_med_maq[df_med_maq['linea_tmp'] == linea_sel_limpia]
        maquinas_en_linea = sorted([str(x).strip() for x in df_filtrado['id_maquinaria'].dropna().unique() if str(x).strip() != ''])

    with tab_individual:
        if not maquinas_en_linea:
            maquina_sel = st.text_input("Ingresa el ID de la maquinaria manualmente para iniciar registro:")
        else:
            # --- ATRAPAMOS LA MÁQUINA EXACTA ---
            idx_maq = 0
            nav_maq_val = st.session_state.get("nav_maq")
            if nav_maq_val and nav_maq_val in maquinas_en_linea:
                idx_maq = maquinas_en_linea.index(nav_maq_val)
                # Limpiamos las variables de sesión para que no se queden ancladas para siempre
                del st.session_state["nav_maq"]
                if "nav_linea" in st.session_state:
                    del st.session_state["nav_linea"]
                    
            maquina_sel = st.selectbox("Selecciona la Maquinaria específica", options=maquinas_en_linea, index=idx_maq)

        if maquina_sel:
        # Consultamos el Inventario Maestro solo para traer los límites técnicos fijos
            info_maq = {}
            limite_fijo = 1.0e9
            marca_defecto = ""
            clasif_defecto = clasificaciones_dinamicas[0]

            if 'df_inv_full' in locals() and not df_inv_full.empty:
                df_inv_filtrado = df_inv_full[df_inv_full['Id de producto'] == maquina_sel]
                if not df_inv_filtrado.empty:
                    info_maq = df_inv_filtrado.iloc[0]
                    limite_fijo = float(info_maq.get('Maximo', 1.0e9))
                    marca_defecto = str(info_maq.get('Marca', ''))
                
                    val_clasif = str(info_maq.get('Clasificación', ''))
                    if val_clasif in clasificaciones_dinamicas:
                        clasif_defecto = val_clasif

            try:
                idx_clasif = clasificaciones_dinamicas.index(clasif_defecto)
            except ValueError:
                idx_clasif = 0

            st.markdown(f"##### 📝 Nueva captura para la estación: `{maquina_sel}`")
        
            with st.form("form_medicion_maquinaria"):
                c_eq1, c_eq2, c_eq3 = st.columns(3)
                clasificacion_maq = c_eq1.selectbox("Clasificación", options=clasificaciones_dinamicas, index=idx_clasif)
                marca_maq = c_eq2.text_input("Marca / Fabricante", value=marca_defecto)
                status_maq = c_eq3.selectbox("Estatus Operativo Actual", ["OPERATIVO", "NO OPERATIVO", "MANTENIMIENTO"])
                
                # --- NUEVA LÓGICA DE LÍMITE DINÁMICO ---
                limite_fijo = 1e9 if str(clasificacion_maq).strip().upper() == "MOBILIARIO" else 1.0
            
                c_amb1, c_amb2, c_amb3 = st.columns(3)
                temperatura_maq = c_amb1.number_input("Temperatura (°C)", value=23.5, step=0.1)
                humedad_maq = c_amb2.number_input("Humedad Relativa (%)", value=45, step=1)
                frecuencia_maq = c_amb3.selectbox("Frecuencia de Verificación", ["Anual", "Semestral", "Trimestral", "Mensual"], index=0)

                st.markdown("---")
                st.markdown("##### ⚡ 1. Resistencia a Tierra")
                col_r1, col_r2 = st.columns(2)
            
                if "resistencia_maq_val" not in st.session_state:
                    st.session_state.resistencia_maq_val = None

                val_tmp = st.session_state.resistencia_maq_val
                formato_dinamico = "%.2f" if (val_tmp is None or val_tmp < 10.0) else "%.2e"
                step_dinamico = 0.01 if (val_tmp is None or val_tmp < 10.0) else 1.0

                resistencia = col_r1.number_input(
                    "Valor de Resistencia (Ohms)", 
                    min_value=0.0, 
                    max_value=1e12, 
                    value=st.session_state.resistencia_maq_val,
                    step=step_dinamico,
                    format=formato_dinamico,
                    placeholder="0.0"
                )
                st.session_state.resistencia_maq_val = resistencia
                
                # Formato visual adaptable: Muestra 1.00 para maquinaria y 1.00e+09 para mobiliario
                limite_str = f"{limite_fijo:.2e} Ω" if limite_fijo > 10 else f"{limite_fijo:.2f} Ω"
                col_r2.text_input("Límite Máximo Permitido (Referencia Fija)", value=limite_str, disabled=True)
            
                # Evaluación visual segura (evita el TypeError cuando resistencia es None)
                if resistencia is None:
                    st.info("⏳ Esperando captura de resistencia...")
                else:
                    resultado_auto = "PASA" if resistencia <= limite_fijo else "FALLA"
                    if resultado_auto == "FALLA":
                        st.error(f"❌ RESULTADO EVALUACIÓN: FALLA (Resistencia {resistencia:.2e} excede el límite de {limite_fijo:.2e})")
                    else:
                        st.success("✅ RESULTADO EVALUACIÓN: PASA")

                st.markdown("##### 🔌 2. Tomacorriente (Opcional)")
                col_t1, col_t2 = st.columns(2)
                aplica_toma = col_t1.checkbox("Aplica medición a la red", value=True)
                estado_toma = "N/A"
                comentario_toma = ""
                if aplica_toma:
                    estado_toma = col_t1.radio("Estatus de Conexión", ["PASA", "FALLA"], horizontal=True)
                    if estado_toma == "FALLA":
                        comentario_toma = col_t2.text_input("Comentario de Falla (Requerido)", placeholder="Ej: Polaridad invertida...")

                st.markdown("##### 🧲 3. Medición de Campo Electrostático")
                c_campo1, c_campo2 = st.columns(2)
                voltaje_campo = c_campo1.number_input("Voltaje Detectado (V)", min_value=0.0, format="%.2f", step=1.0)
                comentario_campo = ""
                if voltaje_campo > 0:
                    comentario_campo = c_campo2.text_input("Ubicación de la carga (Requerido)", placeholder="Ej: En la banda...")
            
                obs_maq = st.text_area("Notas / Observaciones Generales")
            
                submit_maq = st.form_submit_button("💾 Guardar Nueva Validación en Historial", use_container_width=True)
            
                if submit_maq:
                    if aplica_toma and estado_toma == "FALLA" and not comentario_toma.strip():
                        st.error("⚠️ Debes escribir un comentario justificando la falla del tomacorriente.")
                    elif voltaje_campo > 0 and not comentario_campo.strip():
                        st.error("⚠️ Como detectaste voltaje, debes indicar dónde se encontró la carga electrostática.")
                    else:
                        with st.spinner("Actualizando registro transaccional en SQL..."):
                            try:
                                fecha_hoy = datetime.today().date()
                                proxima_fecha = calcular_proxima_fecha(fecha_hoy, frecuencia_maq)

                                # Implementación de la nueva lógica de negocio
                                if resistencia is None or resistencia == 0.0: 
                                # Si dejas la resistencia vacía o en 0 en el number_input
                                    estatus_calculado = "PENDIENTE"
                                elif proxima_fecha < fecha_hoy:
                                    estatus_calculado = "VENCIDO"
                                else:
                                    estatus_calculado = "VIGENTE"
                            
                                data_insert = {
                                    "linea_ubicacion": linea_sel,
                                    "id_maquinaria": maquina_sel,
                                    "clasificacion": clasificacion_maq,
                                    "marca": marca_maq,
                                    "status_operativo": status_maq,
                                    "temperatura": temperatura_maq,
                                    "humedad":  humedad_maq,
                                    "frecuencia_verificacion": "Anual",              # Forzado a "Anual" como solicitaste
                                    "fecha_proxima": proxima_fecha.isoformat(),
                                    "resistencia_tierra": float(resistencia) if resistencia > 0 else None,
                                    "resistencia_max": limite_fijo, 
                                    "tomacorriente_aplica": aplica_toma,
                                    "tomacorriente_estatus": estado_toma,
                                    "tomacorriente_comentario": comentario_toma,
                                    "campo_estatico_voltaje": float(voltaje_campo),
                                    "campo_estatico_comentario": comentario_campo,
                                    "observaciones": obs_maq,
                                    "fecha_medicion": datetime.now().isoformat(),
                                    "auditor": st.session_state.usuario_nombre,
                                    "resultado_estatus": estatus_calculado           # Tu nueva lógica automatizada
                                }
                            
                                supabase.table("mediciones_maquinaria").insert(data_insert).execute()
                            
                                st.success(f"✅ ¡Medición guardada! Próxima verificación calculada para: {proxima_fecha.strftime('%d-%b-%Y')}")
                                st.balloons()
                                time.sleep(1)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

    # ==========================================
    # MODO 2: CAPTURA EN LOTE (RESPONSIVA PARA TABLET/MÓVIL)
    # ==========================================
    with tab_lote:
        st.info("💡 **Modo Rápido Móvil/Tablet:** Despliega cada estación para registrar sus datos. Las columnas se adaptarán a tu pantalla. Al finalizar, presiona el botón al fondo para guardar toda la línea.")
        
        if not maquinas_en_linea:
            st.warning("Selecciona una línea con máquinas registradas previamente para usar el modo en lote.")
        else:
            with st.form("form_lote_movil"):
                st.markdown("##### 🌡️ Condiciones Ambientales Globales de la Línea")
                c_amb_lote1, c_amb_lote2 = st.columns(2)
                temp_lote = c_amb_lote1.number_input("Temperatura (°C)", value=23.5, step=0.1)
                hum_lote = c_amb_lote2.number_input("Humedad Relativa (%)", value=45, step=1)
                st.divider()
                
                # Diccionario para almacenar los inputs temporales de cada máquina
                resultados_lote = {}
                
                for i, maq in enumerate(maquinas_en_linea):
                    # Extraer clasificación histórica si existe
                    clasif = "Maquinaria"
                    if not df_filtrado[df_filtrado['id_maquinaria'] == maq].empty:
                        clasif = df_filtrado[df_filtrado['id_maquinaria'] == maq].iloc[0].get('clasificacion', 'Maquinaria')
                    
                    # Expandir solo el primer elemento por defecto para no abrumar la pantalla
                    with st.expander(f"⚙️ {maq} ({clasif})", expanded=(i == 0)):
                        # En tablet se ven en fila, en teléfono se apilan en columna
                        col_t, col_r, col_c = st.columns(3)
                        
                        toma_val = col_t.selectbox(
                            "1. Tomacorriente", 
                            ["PASA", "FALLA", "N/A"], 
                            key=f"toma_{maq}"
                        )
                        
                        res_val = col_r.number_input(
                            "2. Res. Tierra (Ω)", 
                            min_value=0.0, step=0.1, format="%.2e", 
                            key=f"res_{maq}", value=None, placeholder="0.0"
                        )
                        
                        campo_val = col_c.number_input(
                            "3. Campo Est. (V)", 
                            min_value=0.0, step=1.0, format="%.1f", 
                            key=f"camp_{maq}", value=None, placeholder="0"
                        )
                        
                        notas_val = st.text_input(f"Observaciones para {maq} (opcional)", key=f"not_{maq}")
                        
                        # Guardamos en el diccionario usando el ID de la máquina como llave
                        resultados_lote[maq] = {
                            "clasificacion": clasif,
                            "tomacorriente": toma_val,
                            "resistencia": res_val,
                            "campo": campo_val,
                            "notas": notas_val
                        }

                st.divider()
                # Botón grande y fácil de presionar en móviles
                submit_lote = st.form_submit_button("💾 Procesar y Guardar Línea Completa", use_container_width=True)
                
                if submit_lote:
                    # Validar si faltó alguna máquina por llenar
                    faltantes = [m for m, d in resultados_lote.items() if d["resistencia"] is None or d["campo"] is None]
                    
                    if faltantes:
                        st.error(f"⚠️ Faltan valores numéricos en las siguientes operaciones: {', '.join(faltantes)}")
                    else:
                            with st.spinner("Registrando auditoría masiva en SQL..."):
                                errores = 0
                                fecha_hoy = datetime.today().isoformat()
                                proxima_fecha = (datetime.today().date() + relativedelta(years=1)).isoformat()
                                
                                # 1. CREAMOS UNA LISTA PARA ALMACENAR TODOS LOS REGISTROS
                                lista_datos_insertar = []
                                
                                for maq_id, datos in resultados_lote.items():
                                    res = float(datos["resistencia"])
                                    
                                    # --- ASIGNACIÓN DE LÍMITE DINÁMICO EN LOTE ---
                                    limite_fijo = 1e9 if str(datos["clasificacion"]).strip().upper() == "MOBILIARIO" else 1.0
                                    
                                    # Calcular estatus basado en su propio límite normativo
                                    if res <= limite_fijo and datos["tomacorriente"] != "FALLA":
                                        estatus_calculado = "VIGENTE"
                                    else:
                                        estatus_calculado = "FALLA"

                                    data_insert = {
                                        "linea_ubicacion": linea_sel,
                                        "id_maquinaria": maq_id.strip().upper(),
                                        "clasificacion": datos["clasificacion"],
                                        "marca": "N/D",
                                        "status_operativo": "OPERATIVO",
                                        "temperatura": float(temp_lote), 
                                        "humedad": int(hum_lote),
                                        "frecuencia_verificacion": "Anual",
                                        "fecha_proxima": proxima_fecha,
                                        "resistencia_tierra": res if res > 0 else None,
                                        "resistencia_max": limite_fijo, 
                                        "tomacorriente_aplica": datos["tomacorriente"] != "N/A",
                                        "tomacorriente_estatus": datos["tomacorriente"] if datos["tomacorriente"] != "N/A" else None,
                                        "campo_estatico_voltaje": float(datos["campo"]),
                                        "observaciones": datos["notas"],
                                        "fecha_medicion": fecha_hoy,
                                        "auditor": st.session_state.usuario_nombre,
                                        "resultado_estatus": estatus_calculado
                                    }
                                    
                                    # 2. AGREGAMOS CADA DICCIONARIO A LA LISTA DENTRO DEL CICLO
                                    lista_datos_insertar.append(data_insert)
                                
                                # 3. EJECUTAMOS EL INSERT FUERA DEL CICLO (UNA SOLA PETICIÓN MASIVA)
                                try:
                                    supabase.table("mediciones_maquinaria").insert(lista_datos_insertar).execute()
                                except Exception as e:
                                    errores += 1
                                    st.error(f"Error de base de datos al guardar el lote: {e}")
                        
                            if errores == 0:
                                st.success(f"✅ ¡Auditoría masiva completada para {len(resultados_lote)} estaciones en {linea_sel}!")
                                st.balloons()
                                time.sleep(1.5)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.warning("Ocurrió un error en la inserción masiva. Revisa los detalles.")
    # ==========================================
    # MODO 3: CONDUCTORES AISLADOS
    # ==========================================
    with tab_conductores:
        st.markdown("#### ⚡ Registro de Conductores Aislados")
        st.info("De acuerdo con ANSI/ESD S20.20-2021, los conductores aislados no pueden exceder los 35V. Si se supera el límite, el sistema generará una solicitud para instalar ionización.")

        # Obtener lista de equipos de medición desde la BD
        try:
            resp_eq_cond = supabase.table("equipos_medicion").select("id_equipo").execute()
            equipos_cond = sorted([str(x['id_equipo']).strip() for x in resp_eq_cond.data if x.get('id_equipo')])
        except:
            equipos_cond = ["Error al cargar equipos"]

        if not equipos_cond:
            equipos_cond = ["Sin equipos registrados"]

        # Filtros dinámicos
        c_cond1, c_cond2 = st.columns(2)
        linea_cond_sel = c_cond1.selectbox("1. Línea / Ubicación:", options=lineas_disp, key="linea_cond")
        
        # Actualizar operaciones según la línea elegida
        ops_cond_disp = []
        if not df_med_maq.empty and linea_cond_sel != "Sin registros previos":
            # Estandarizamos para el cruce exacto
            linea_cond_sel_limpia = str(linea_cond_sel).strip().upper()
            df_med_maq['linea_tmp'] = df_med_maq['linea_ubicacion'].astype(str).str.strip().str.upper()
            
            ops_filtradas = df_med_maq[df_med_maq['linea_tmp'] == linea_cond_sel_limpia]
            ops_cond_disp = sorted([str(x).strip() for x in ops_filtradas['id_maquinaria'].dropna().unique() if str(x).strip() != ''])
            
        if not ops_cond_disp:
            ops_cond_disp = ["Sin operaciones registradas"]

        op_cond_sel = c_cond2.selectbox("2. Operación / Estación:", options=ops_cond_disp, key="op_cond")

        # Formulario de captura
        with st.form("form_conductores_aislados"):
            c_cond3, c_cond4 = st.columns(2)
            # Buscar el índice del equipo default literal; si no existe, usar 0
            equipo_default = "BCS-QRO-LAB-VOL001"
            idx_eq = equipos_cond.index(equipo_default) if equipo_default in equipos_cond else 0
            
            equipo_cond_sel = c_cond3.selectbox("3. Equipo de Medición Utilizado:", options=equipos_cond, index=idx_eq)
            
            # Input numérico para el voltaje
            voltaje_max_cond = c_cond4.number_input(
                "4. Voltaje Máximo Registrado (V):", 
                min_value=0.0, 
                max_value=99999.0, 
                step=1.0, 
                format="%.1f",
                value=None,
                placeholder="0.0"
            )
            
            # Nuevo campo de comentarios
            comentarios_cond = st.text_input("5. Ubicación específica / Comentarios:", placeholder="Ej: En la guía del transportador, carcasa del motor...")

            # Botón de guardado
            submit_cond = st.form_submit_button("💾 Guardar Registro de Conductor Aislado", use_container_width=True)

            if submit_cond:
                if op_cond_sel == "Sin operaciones registradas":
                    st.error("⚠️ Debes seleccionar una operación válida.")
                elif voltaje_max_cond is None:
                    st.error("⚠️ Debes capturar el voltaje máximo registrado.")    
                elif voltaje_max_cond > 35.0 and not comentarios_cond.strip():
                    st.error("⚠️ Al superar los 35V, es obligatorio especificar la ubicación exacta en los comentarios para el reporte a Ingeniería.")
                else:
                    with st.spinner("Guardando registro..."):
                        try:
                            # Inserción en la tabla
                            supabase.table("registro_conductores_aislados").insert({
                                "linea": linea_cond_sel,
                                "operacion": op_cond_sel,
                                "equipo_medicion": equipo_cond_sel,
                                "voltaje_maximo": float(voltaje_max_cond),
                                "comentarios": comentarios_cond.strip(),
                                "auditor": st.session_state.usuario_nombre
                            }).execute()

                            st.success(f"✅ Registro guardado para la operación {op_cond_sel}.")
                            
                            # Lógica de Validación S20.20 (> 35V)
                            if voltaje_max_cond > 35.0:
                                st.error(f"🚨 ¡ATENCIÓN! Se registraron {voltaje_max_cond}V, superando el límite permitido de 35V para conductores aislados.")
                                st.markdown("##### 📧 Acción Requerida: Solicitud a Ingeniería")
                                st.write("Copia el siguiente texto y envíalo al departamento de Ingeniería para solicitar la instalación de un ionizador:")
                                
                                ubicacion_texto = f"específicamente en la siguiente ubicación: {comentarios_cond.strip()}" if comentarios_cond.strip() else "en esta estación"
                                
                                # Borrador del correo generado dinámicamente
                                borrador_correo = f"""Asunto: Acción Requerida: Instalación de Ionizador en {op_cond_sel} ({linea_cond_sel}) - Límite ESD Excedido

Estimado equipo de Ingeniería,

Durante la auditoría de control ESD realizada el día de hoy, se detectó un conductor aislado en la operación {op_cond_sel} de la línea {linea_cond_sel}, {ubicacion_texto}, que supera el límite normativo de 35V establecido en el estándar ANSI/ESD S20.20-2021.

El equipo registró un voltaje máximo de {voltaje_max_cond}V. Esta carga es generada principalmente por la separación de materiales y el efecto triboeléctrico intrínseco al proceso. Al tratarse de un conductor aislado, no es posible drenar esta carga a tierra de forma convencional.

Para neutralizar la carga y proteger los ensambles electrónicos, se solicita su apoyo para evaluar e instalar un ionizador focalizado en este punto a la brevedad posible.

Quedo a su disposición para revisar la estación en conjunto.

Saludos cordiales,
{st.session_state.usuario_nombre}
Departamento de Calidad / Control ESD"""

                                st.code(borrador_correo, language="text")
                            else:
                                st.info("El voltaje se encuentra dentro de la especificación permitida (<= 35V). No se requieren acciones adicionales.")
                                time.sleep(2)
                                st.rerun()

                        except Exception as e:
                            st.error(f"Error al guardar el registro en SQL: {e}")
        # ==========================================
        # VISOR DE HISTORIAL DE CONDUCTORES AISLADOS
        # ==========================================
        st.divider()
        col_hc1, col_hc2 = st.columns([0.8, 0.2])
        col_hc1.markdown("#### 📂 Historial de Conductores Aislados")
        if col_hc2.button("🔄 Actualizar", key="btn_refresh_cond"):
            st.cache_data.clear()
            st.rerun()

        # Filtro de Línea para el historial
        lineas_historial = ["Todas las líneas"] + lineas_disp
        linea_filtro = st.selectbox("🔍 Filtrar historial por Línea:", options=lineas_historial, key="filtro_linea_historial_cond")

        try:
            # Consultamos la tabla completa ordenada por los más recientes
            resp_hist_cond = supabase.table("registro_conductores_aislados").select("*").order("fecha_registro", desc=True).execute()
            df_hist_cond = pd.DataFrame(resp_hist_cond.data)
            
            if not df_hist_cond.empty:
                # 1. Aplicamos el filtro si el usuario seleccionó una línea específica
                if linea_filtro != "Todas las líneas":
                    linea_filtro_limpia = str(linea_filtro).strip().upper()
                    df_hist_cond['linea_tmp'] = df_hist_cond['linea'].astype(str).str.strip().str.upper()
                    df_hist_cond = df_hist_cond[df_hist_cond['linea_tmp'] == linea_filtro_limpia]
                
                if not df_hist_cond.empty:
                    # 2. Función para evaluar el estatus normativo
                    def estatus_conductor(v):
                        try:
                            val = float(v)
                            return "🟢 Aprobado" if val <= 35.0 else "🔴 Fuera de límite / Ionizado"
                        except:
                            return "N/D"
                            
                    # 3. Formateamos las columnas para la tabla
                    df_hist_cond['Estatus'] = df_hist_cond['voltaje_maximo'].apply(estatus_conductor)
                    df_hist_cond['Fecha'] = pd.to_datetime(df_hist_cond['fecha_registro']).dt.strftime('%d-%b-%Y %H:%M')
                    df_hist_cond['Voltaje Máx'] = df_hist_cond['voltaje_maximo'].astype(str) + " V"
                    
                    # Extraer solo las columnas relevantes (incluyendo los comentarios para saber la ubicación exacta)
                    df_mostrar_cond = df_hist_cond[['Fecha', 'linea', 'operacion', 'Voltaje Máx', 'Estatus', 'equipo_medicion', 'comentarios', 'auditor']].copy()
                    df_mostrar_cond.columns = ['Fecha', 'Línea', 'Operación', 'Voltaje Máximo', 'Estatus', 'Equipo', 'Ubicación / Notas', 'Auditor']
                    
                    st.dataframe(df_mostrar_cond.fillna("N/D"), use_container_width=True, hide_index=True)
                else:
                    st.info(f"No hay registros de conductores aislados guardados para la línea {linea_filtro}.")
            else:
                st.info("Aún no hay registros de conductores aislados en el sistema.")
                
        except Exception as e:
            st.error(f"Error al cargar el historial de conductores aislados: {e}")
# ==========================================
# VISTA 8: PROGRAMACIÓN (CRONOGRAMA Y ACCIONES URGENTES)
# ==========================================
elif st.session_state.vista_actual == "Schedule" and not st.session_state.modo_lectura:
    st.markdown("### 📅 Cronograma de Verificaciones ESD")
    
    tab_cronograma, tab_urgentes = st.tabs(["📅 Cronograma General", "🚨 Pendientes y Vencidos (Edición Directa)"])

    # --- SUB-PESTAÑA 1: CRONOGRAMA GENERAL (CÓDIGO EXISTENTE OPTIMIZADO) ---
    with tab_cronograma:
        st.info("Visualiza las fechas de medición y vencimiento de Equipos, Mobiliarios e Ionizadores combinados en la planta.")
        
        # Obtener datos frescos de maquinaria para consolidar (AHORA INCLUYE status_operativo)
        try:
            resp_maq = supabase.table("mediciones_maquinaria").select("linea_ubicacion, id_maquinaria, clasificacion, fecha_medicion, fecha_proxima, resultado_estatus, status_operativo").execute()
            df_maq_sched = pd.DataFrame(resp_maq.data)
        except Exception as e:
            df_maq_sched = pd.DataFrame()
            st.warning(f"Error al cargar maquinaria: {e}")

        lista_registros = []
        
        if df_inv_full is not None and not df_inv_full.empty:
            for _, row in df_inv_full.iterrows():
                if str(row.get('Estatus operativo', '')).strip().upper() == 'NO OPERATIVO':
                    continue
                lista_registros.append({
                    "Línea": str(row.get('Línea', 'N/D')),
                    "Categoría": str(row.get('categoria', 'N/D')),
                    "ID / Nombre": str(row.get('Id de producto', 'N/D')),
                    "Clasificación": str(row.get('Clasificación', 'N/D')),
                    "Última Medición": str(row.get('Fecha de verificación', 'N/D'))[:10],
                    "Próximo Vencimiento": str(row.get('Fecha de próxima verificación', 'N/D'))[:10],
                    "Estatus": str(row.get('Estatus de verificación', 'N/D'))
                })
                
        if not df_maq_sched.empty:
            df_maq_sched = df_maq_sched.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'])
            for _, row in df_maq_sched.iterrows():
                if str(row.get('status_operativo', '')).strip().upper() == 'NO OPERATIVO' or str(row.get('resultado_estatus', '')).strip().upper() == 'BAJA':
                    continue
                f_med = str(row.get('fecha_medicion', 'N/D'))[:10] if pd.notna(row.get('fecha_medicion')) else 'N/D'
                f_prox = str(row.get('fecha_proxima', 'N/D'))[:10] if pd.notna(row.get('fecha_proxima')) else 'N/D'
                
                lista_registros.append({
                    "Línea": str(row.get('linea_ubicacion', 'N/D')),
                    "Categoría": "Maquinaria / Equipo",
                    "ID / Nombre": str(row.get('id_maquinaria', 'N/D')),
                    "Clasificación": str(row.get('clasificacion', 'N/D')),
                    "Última Medición": f_med,
                    "Próximo Vencimiento": f_prox,
                    "Estatus": str(row.get('resultado_estatus', 'PENDIENTE'))
                })

        try:
            resp_tierras = supabase.table("tierras_auxiliares").select("*").execute()
            df_tierras = pd.DataFrame(resp_tierras.data)
            if not df_tierras.empty:
                df_tierras = df_tierras.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_punto'])
                for _, row in df_tierras.iterrows():
                    f_med = str(row.get('fecha_medicion', 'N/D'))[:10]
                    try:
                        f_med_date = datetime.strptime(f_med, "%Y-%m-%d").date()
                        f_prox = (f_med_date + relativedelta(months=6)).strftime("%Y-%m-%d")
                    except:
                        f_prox = "N/D"

                    lista_registros.append({
                        "Línea": str(row.get('linea', 'N/D')),
                        "Categoría": "Infraestructura (EPA)",
                        "ID / Nombre": str(row.get('id_punto', 'N/D')),
                        "Clasificación": str(row.get('tipo_punto', 'N/D')),
                        "Última Medición": f_med,
                        "Próximo Vencimiento": f_prox,
                        "Estatus": str(row.get('estatus', 'PENDIENTE'))
                    })
        except:
            pass
            
        df_schedule_full = pd.DataFrame(lista_registros)

        if not df_schedule_full.empty:
            df_schedule_full['Línea'] = df_schedule_full['Línea'].astype(str).str.strip().str.upper()
            lineas_disponibles = sorted([x for x in df_schedule_full['Línea'].unique() if x not in ['N/D', 'NAN', 'NONE', '']])
            
            c_filtro1, c_filtro2 = st.columns(2)
            linea_sel = c_filtro1.selectbox("📍 Selecciona la Línea / Ubicación:", ["Todas las Líneas"] + lineas_disponibles)
            categoria_sel = c_filtro2.selectbox("🏷️ Filtrar por Categoría:", ["Todas", "Maquinaria / Equipo", "Mobiliario", "Ionizador", "Piso"])
            
            df_filtrado = df_schedule_full.copy()
            if linea_sel != "Todas las Líneas":
                df_filtrado = df_filtrado[df_filtrado['Línea'] == linea_sel]
            if categoria_sel != "Todas":
                df_filtrado = df_filtrado[df_filtrado['Categoría'] == categoria_sel]
            
            df_filtrado['Fecha Orden'] = df_filtrado['Próximo Vencimiento'].replace('N/D', None)
            df_filtrado['Fecha Orden'] = pd.to_datetime(df_filtrado['Fecha Orden'], errors='coerce')
            df_filtrado = df_filtrado.sort_values(by=['Fecha Orden', 'Línea'], ascending=[True, True], na_position='last').drop(columns=['Fecha Orden'])
            
            def add_emoji(val):
                val_str = str(val).upper()
                if 'VIGENTE' in val_str or 'PASA' in val_str: return f"🟢 {val}"
                if 'VENCIDO' in val_str or 'FALLA' in val_str or 'RECHAZADO' in val_str: return f"🔴 {val}"
                if 'PENDIENTE' in val_str: return f"🟡 {val}"
                return val
                
            df_filtrado['Estatus'] = df_filtrado['Estatus'].apply(add_emoji)
            st.markdown(f"**Mostrando {len(df_filtrado)} registros:**")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            
            if linea_sel != "Todas las Líneas" and not df_filtrado.empty:
                st.divider()
                st.markdown(f"#### 📄 Generar Reporte de Validación: `{linea_sel}`")
                with st.form("form_rep_linea"):
                    col_r1, col_r2 = st.columns([1, 2])
                    auditor_rep = col_r1.text_input("Auditor / Coordinador", value=st.session_state.usuario_nombre)
                    comentarios_rep = col_r2.text_area("Observaciones Generales", placeholder="Ej: La línea cumple satisfactoriamente...")
                    
                    if st.form_submit_button("Generar Reporte Oficial", use_container_width=True):
                        with st.spinner("Generando documento..."):
                            try:
                                resp_log = supabase.table("log_reportes_linea").insert({"linea_ubicacion": linea_sel, "auditor": auditor_rep, "comentarios": comentarios_rep}).execute()
                                db_id_linea = resp_log.data[0]['id']
                                html_rep_linea, año_rep = generar_html_reporte_linea(linea_sel, df_filtrado, auditor_rep, comentarios_rep, db_id_linea)
                                b64_html = base64.b64encode(html_rep_linea.encode('utf-8')).decode('utf-8')
                                nombre_oficial = f"BCS-LV-{db_id_linea:03d}-{año_rep}"
                                href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_oficial}.html" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte de Línea ({nombre_oficial})</a>'
                                st.markdown(href, unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error generando el reporte: {e}")
        else:
            st.warning("No hay registros disponibles para mostrar en el cronograma.")

    # --- SUB-PESTAÑA 2: ACCIONES URGENTES Y PREVENTIVAS (TABLA INTEGRAL EDITABLE EN VIVO) ---
    with tab_urgentes:
        st.markdown("#### 🚨 Mesa de Control y Actualización")
        
        # --- NUEVO: SELECTOR DE VISUALIZACIÓN ---
        filtro_urgentes = st.radio(
            "Selecciona el modo de visualización:", 
            ["🚨 Solo Vencidos y Pendientes (Acción Inmediata)", "⚠️ Próximos a Vencer (7 días + Equipos de Medición)"],
            horizontal=True
        )
        st.caption("Escribe el nuevo valor de resistencia (ej: **1e9**) o la nueva fecha. Al guardar, el sistema evaluará el límite, cambiará el estatus y actualizará las fechas automáticamente.")

        with st.spinner("Evaluando fechas de vencimiento y compilando activos..."):
            from datetime import datetime, timedelta
            hoy = datetime.today().date()
            
            # --- NUEVA LÓGICA DE TIEMPO Y TABLAS ---
            if "Próximos" in filtro_urgentes:
                limite_alerta = hoy + timedelta(days=7)
                incluir_equipos = True
            else:
                limite_alerta = hoy
                incluir_equipos = False

            # 1. Extraer Inventario Completo Operativo
            try:
                resp_inv_u = supabase.table("inventario_esd").select("*").not_.eq("estatus_operativo", "NO OPERATIVO").execute()
                df_inv_u = pd.DataFrame(resp_inv_u.data) if resp_inv_u.data else pd.DataFrame()
            except:
                df_inv_u = pd.DataFrame()

            # 2. Extraer Maquinaria Completa Operativa
            try:
                resp_maq_u = supabase.table("mediciones_maquinaria").select("*").not_.eq("status_operativo", "NO OPERATIVO").not_.eq("resultado_estatus", "BAJA").execute()
                df_maq_u = pd.DataFrame(resp_maq_u.data) if resp_maq_u.data else pd.DataFrame()
                if not df_maq_u.empty:
                    df_maq_u = df_maq_u.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'], keep='first')
            except:
                df_maq_u = pd.DataFrame()

            # 3. Extraer Equipos de Medición (Solo si el filtro lo demanda)
            if incluir_equipos:
                try:
                    resp_eq_u = supabase.table("equipos_medicion").select("*").execute()
                    df_eq_u = pd.DataFrame(resp_eq_u.data) if resp_eq_u.data else pd.DataFrame()
                except:
                    df_eq_u = pd.DataFrame()
            else:
                df_eq_u = pd.DataFrame()

            # 4. Consolidar registros que requieren atención
            lista_urgentes = []

            # --- MAPEO DESDE INVENTARIO ---
            if not df_inv_u.empty:
                for _, r in df_inv_u.iterrows():
                    valor_original = r.get('estatus_verificacion')
                    est = str(valor_original).strip().upper()
                    es_nulo = pd.isna(valor_original) or est in ['', 'NONE', 'NAN', 'NULL', 'N/A', 'N/D']

                    f_prox_str = str(r.get('fecha_proxima_verif', ''))[:10]
                    vencido_por_fecha = False
                    f_prox_date = None
                    
                    if f_prox_str and f_prox_str not in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                        try:
                            f_prox_date = datetime.strptime(f_prox_str, "%Y-%m-%d").date()
                            if f_prox_date <= limite_alerta: # Evaluación expansiva a 7 días
                                vencido_por_fecha = True
                        except:
                            pass

                    # REGLA DE ORO
                    if 'VENCIDO' in est or 'PENDIENTE' in est or es_nulo or vencido_por_fecha:
                        val_previo = r.get('valor_actual')
                        val_str = f"{val_previo:.2e}" if pd.notna(val_previo) else ""
                        
                        if f_prox_date and f_prox_date < hoy:
                            estatus_mostrar = "VENCIDO"
                        elif f_prox_date and f_prox_date <= limite_alerta:
                            estatus_mostrar = "POR VENCER" if est == "VIGENTE" else est
                        else:
                            estatus_mostrar = "PENDIENTE" if es_nulo else est
                        
                        lista_urgentes.append({
                            "Tabla Origen": "inventario_esd",
                            "Columna_Llave": "id_producto",
                            "ID Activo": r.get('id_producto'),
                            "Categoría": r.get('categoria', 'Inventario'),
                            "Clasificación": r.get('clasificacion', 'N/D'),
                            "Ubicación / Línea": r.get('linea_ubicacion', 'N/D'),
                            "Vencimiento": f_prox_str if f_prox_str else "Sin Fecha",
                            "_fecha_sort": f_prox_date if f_prox_date else datetime.min.date(),
                            "Estatus": estatus_mostrar,
                            "Fecha Medición": str(r.get('fecha_ultima_verif', ''))[:10] if r.get('fecha_ultima_verif') else "",
                            "Resistencia / Descarga (Ω/s)": val_str,
                            "Balance (V)": r.get('balance_ionizador'),
                            "Campo Estático (V)": None,
                            "Tomacorriente": None,
                            "Temp (°C)": r.get('temperatura', '23.5'),
                            "Humedad (%)": r.get('humedad', '45'),
                            "Notas / Observaciones": r.get('comentarios', '')
                        })

            # --- MAPEO DESDE MAQUINARIA ---
            if not df_maq_u.empty:
                for _, r in df_maq_u.iterrows():
                    valor_original = r.get('resultado_estatus')
                    est = str(valor_original).strip().upper()
                    es_nulo = pd.isna(valor_original) or est in ['', 'NONE', 'NAN', 'NULL', 'N/A', 'N/D']
                    
                    f_prox_str = str(r.get('fecha_proxima', ''))[:10]
                    vencido_por_fecha = False
                    f_prox_date = None
                    
                    if f_prox_str and f_prox_str not in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                        try:
                            f_prox_date = datetime.strptime(f_prox_str, "%Y-%m-%d").date()
                            if f_prox_date <= limite_alerta: # Evaluación expansiva a 7 días
                                vencido_por_fecha = True
                        except:
                            pass
                    
                    if 'VENCIDO' in est or 'PENDIENTE' in est or es_nulo or vencido_por_fecha:
                        val_previo = r.get('resistencia_tierra')
                        val_str = f"{val_previo:.2e}" if pd.notna(val_previo) else ""
                        
                        if f_prox_date and f_prox_date < hoy:
                            estatus_mostrar = "VENCIDO"
                        elif f_prox_date and f_prox_date <= limite_alerta:
                            estatus_mostrar = "POR VENCER" if est == "VIGENTE" else est
                        else:
                            estatus_mostrar = "PENDIENTE" if es_nulo else est
                        
                        lista_urgentes.append({
                            "Tabla Origen": "mediciones_maquinaria",
                            "Columna_Llave": "id_maquinaria",
                            "ID Activo": r.get('id_maquinaria'),
                            "Categoría": "Maquinaria",
                            "Clasificación": r.get('clasificacion', 'Maquinaria'),
                            "Ubicación / Línea": r.get('linea_ubicacion', 'N/D'),
                            "Vencimiento": f_prox_str if f_prox_str else "Sin Fecha",
                            "_fecha_sort": f_prox_date if f_prox_date else datetime.min.date(),
                            "Estatus": estatus_mostrar,
                            "Fecha Medición": str(r.get('fecha_medicion', ''))[:10] if r.get('fecha_medicion') else "",
                            "Resistencia / Descarga (Ω/s)": val_str,
                            "Balance (V)": None,
                            "Campo Estático (V)": r.get('campo_estatico_voltaje'),
                            "Tomacorriente": r.get('tomacorriente_estatus', 'N/A'),
                            "Temp (°C)": r.get('temperatura', '23.5'),
                            "Humedad (%)": r.get('humedad', '45'),
                            "Notas / Observaciones": r.get('observaciones', '')
                        })

            # --- MAPEO DESDE EQUIPOS DE MEDICIÓN ---
            if incluir_equipos and not df_eq_u.empty:
                for _, r in df_eq_u.iterrows():
                    f_prox_str = str(r.get('fecha_proxima_calibracion', ''))[:10]
                    vencido_por_fecha = False
                    f_prox_date = None
                    
                    if f_prox_str and f_prox_str not in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                        try:
                            f_prox_date = datetime.strptime(f_prox_str, "%Y-%m-%d").date()
                            if f_prox_date <= limite_alerta:
                                vencido_por_fecha = True
                        except:
                            pass
                    
                    if vencido_por_fecha or f_prox_str in ['NONE', 'NAN', 'N/D', 'NULL', '']:
                        if f_prox_date and f_prox_date < hoy:
                            estatus_mostrar = "VENCIDO"
                        elif f_prox_date and f_prox_date <= limite_alerta:
                            estatus_mostrar = "POR VENCER"
                        else:
                            estatus_mostrar = "PENDIENTE"

                        lista_urgentes.append({
                            "Tabla Origen": "equipos_medicion",
                            "Columna_Llave": "id_equipo",
                            "ID Activo": r.get('id_equipo'),
                            "Categoría": "Equipo de Medición",
                            "Clasificación": r.get('tipo_equipo', 'N/D'),
                            "Ubicación / Línea": "Laboratorio / Calidad",
                            "Vencimiento": f_prox_str if f_prox_str else "Sin Fecha",
                            "_fecha_sort": f_prox_date if f_prox_date else datetime.min.date(),
                            "Estatus": estatus_mostrar,
                            "Fecha Medición": "", # Se usa para capturar nueva fecha
                            "Resistencia / Descarga (Ω/s)": None,
                            "Balance (V)": None,
                            "Campo Estático (V)": None,
                            "Tomacorriente": None,
                            "Temp (°C)": None,
                            "Humedad (%)": None,
                            "Notas / Observaciones": r.get('reporte_calibracion', '') # Se usa para reporte nuevo
                        })

            df_urg_source = pd.DataFrame(lista_urgentes)

            if df_urg_source.empty:
                st.success("🎉 ¡Excelente! No se encontraron activos pendientes ni con fechas caducadas.")
            else:
                # ORDENAMIENTO CRONOLÓGICO: Los más antiguos y pendientes hasta arriba
                df_urg_source = df_urg_source.sort_values(by=['_fecha_sort', 'Ubicación / Línea'], ascending=[True, True])

                # 4. RENDERIZACIÓN DEL EDITOR INTERACTIVO EN PISO
                df_editor = st.data_editor(
                    df_urg_source,
                    column_config={
                        "Tabla Origen": None,
                        "Columna_Llave": None,
                        "_fecha_sort": None,
                        "ID Activo": st.column_config.TextColumn("ID Activo", disabled=True),
                        "Categoría": st.column_config.TextColumn("Categoría", disabled=True),
                        "Clasificación": st.column_config.TextColumn("Clasificación", disabled=True),
                        "Ubicación / Línea": st.column_config.TextColumn("Ubicación", disabled=True),
                        "Vencimiento": st.column_config.TextColumn("Vencimiento", disabled=True),
                        "Estatus": st.column_config.SelectboxColumn("Estatus", options=["PENDIENTE", "VENCIDO", "POR VENCER", "VIGENTE"], required=True),
                        "Tomacorriente": st.column_config.SelectboxColumn("Tomacorriente", options=["PASA", "FALLA", "N/A"]),
                        "Resistencia / Descarga (Ω/s)": st.column_config.TextColumn("Resistencia (Ω)", help="Admite notación científica. Ej: 1e9 o 5.5e8"),
                        "Campo Estático (V)": st.column_config.NumberColumn("Campo Estático (V)", format="%.1f"),
                        "Balance (V)": st.column_config.NumberColumn("Balance (V)", format="%.1f"),
                        "Fecha Medición": st.column_config.TextColumn("Fecha (YYYY-MM-DD)", help="Para Equipos de Medición, ingresa aquí la fecha en que se calibró.")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="live_editor_urgentes"
                )

                st.divider()
                
                # 5. BOTÓN DE GUARDADO MASIVO (BATCH UPDATE)
                c_btn_vacio, c_btn_guardar = st.columns([3, 1])
                btn_guardar_urgentes = c_btn_guardar.button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if btn_guardar_urgentes:
                    cambios_detectados = st.session_state.live_editor_urgentes.get("edited_rows", {})
                    
                    if not cambios_detectados:
                        st.info("No se ha modificado ninguna celda. No hay cambios por guardar.")
                    else:
                        with st.spinner("Evaluando normativas y sincronizando con la base de datos..."):
                            errores = 0
                            activos_actualizados = []
                            
                            for idx_str, c_celdas in cambios_detectados.items():
                                idx = int(idx_str)
                                fila_original = df_urg_source.iloc[idx]
                                
                                tabla_destino = fila_original["Tabla Origen"]
                                columna_pk = fila_original["Columna_Llave"]
                                id_activo_txt = fila_original["ID Activo"]
                                
                                payload_update = {}
                                
                                # --- LÓGICA ESPECIAL PARA EQUIPOS DE MEDICIÓN ---
                                if tabla_destino == "equipos_medicion":
                                    if "Fecha Medición" in c_celdas and c_celdas["Fecha Medición"]:
                                        try:
                                            f_base = datetime.strptime(c_celdas["Fecha Medición"], "%Y-%m-%d").date()
                                            payload_update["fecha_proxima_calibracion"] = (f_base + relativedelta(years=1)).isoformat()
                                        except: pass
                                    if "Notas / Observaciones" in c_celdas:
                                        payload_update["reporte_calibracion"] = c_celdas["Notas / Observaciones"]
                                else:
                                    # --- AUTO-EVALUACIÓN PARA INVENTARIO Y MAQUINARIA ---
                                    if "Resistencia / Descarga (Ω/s)" in c_celdas:
                                        val_r_raw = c_celdas["Resistencia / Descarga (Ω/s)"]
                                        if val_r_raw is not None and str(val_r_raw).strip() != "":
                                            try:
                                                val_r_float = float(val_r_raw)
                                                payload_update["valor_actual" if tabla_destino == "inventario_esd" else "resistencia_tierra"] = val_r_float
                                                
                                                if tabla_destino == "mediciones_maquinaria":
                                                    estatus_calc = "VIGENTE" if val_r_float <= 1.0 else "VENCIDO"
                                                else:
                                                    estatus_calc = "VIGENTE" if val_r_float < 1.0e9 else "VENCIDO"
                                                
                                                c_celdas["Estatus"] = estatus_calc
                                                if "Fecha Medición" not in c_celdas:
                                                    c_celdas["Fecha Medición"] = datetime.today().strftime("%Y-%m-%d")
                                                    
                                            except ValueError:
                                                st.error(f"❌ Valor inválido en {id_activo_txt}: '{val_r_raw}'. Usa formato numérico.")
                                                errores += 1
                                                continue

                                    if "Estatus" in c_celdas:
                                        nuevo_est = c_celdas["Estatus"]
                                        if tabla_destino == "inventario_esd":
                                            payload_update["estatus_verificacion"] = nuevo_est
                                        else:
                                            payload_update["resultado_estatus"] = nuevo_est
                                            
                                        if nuevo_est in ["VIGENTE", "APROBADO"]:
                                            fecha_str = c_celdas.get("Fecha Medición", datetime.today().strftime("%Y-%m-%d"))
                                            try:
                                                f_base = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                                            except:
                                                f_base = datetime.today().date()
                                                
                                            payload_update["fecha_proxima" if tabla_destino == "mediciones_maquinaria" else "fecha_proxima_verif"] = (f_base + relativedelta(years=1)).isoformat()
                                    
                                    if "Fecha Medición" in c_celdas:
                                        payload_update["fecha_ultima_verif" if tabla_destino == "inventario_esd" else "fecha_medicion"] = c_celdas["Fecha Medición"]
                                        
                                    if "Balance (V)" in c_celdas and tabla_destino == "inventario_esd":
                                        val_b = c_celdas["Balance (V)"]
                                        payload_update["balance_ionizador"] = float(val_b) if val_b else None
                                        
                                    if "Campo Estático (V)" in c_celdas and tabla_destino == "mediciones_maquinaria":
                                        val_c = c_celdas["Campo Estático (V)"]
                                        payload_update["campo_estatico_voltaje"] = float(val_c) if val_c else None
                                        
                                    if "Tomacorriente" in c_celdas and tabla_destino == "mediciones_maquinaria":
                                        payload_update["tomacorriente_estatus"] = c_celdas["Tomacorriente"]
                                        
                                    if "Ubicación / Línea" in c_celdas:
                                        payload_update["linea_ubicacion"] = str(c_celdas["Ubicación / Línea"]).strip().upper()
                                        
                                    if "Temp (°C)" in c_celdas:
                                        payload_update["temperatura"] = str(c_celdas["Temp (°C)"])
                                        
                                    if "Humedad (%)" in c_celdas:
                                        payload_update["humedad"] = str(c_celdas["Humedad (%)"])
                                            
                                    if "Notas / Observaciones" in c_celdas:
                                        payload_update["comentarios" if tabla_destino == "inventario_esd" else "observaciones"] = c_celdas["Notas / Observaciones"]

                                # Inyección en la BD
                                if payload_update:
                                    try:
                                        supabase.table(tabla_destino).update(payload_update).eq(columna_pk, id_activo_txt).execute()
                                        activos_actualizados.append(id_activo_txt)
                                    except Exception as sql_err:
                                        st.error(f"Error actualizando {id_activo_txt}: {sql_err}")
                                        errores += 1
                                        
                            if errores == 0 and activos_actualizados:
                                st.success(f"✅ ¡Se han validado y actualizado exitosamente {len(activos_actualizados)} registros!")
                                st.balloons()
                                st.cache_data.clear()
                                time.sleep(1.5)
                                st.rerun()
                            elif errores > 0:
                                st.warning("Se guardaron algunos cambios, pero hubo errores. Revisa los mensajes arriba.")

# ==========================================
# VISTA 9: SENSIBILIDAD DE COMPONENTES (ESDS)
# ==========================================
elif st.session_state.vista_actual == "Sensibilidad" and not st.session_state.modo_lectura:
    st.markdown("### 🔌 Análisis de Sensibilidad de Componentes (HBM / CDM)")
    st.info("Consulta y gestiona los límites de susceptibilidad de los ensambles. Esencial para justificar los límites de control en la EPA.")

    tab_overview_sen, tab_consulta, tab_importar = st.tabs(["📈 Overview Global", "📊 Consulta de Reportes", "📥 Importar Histórico"])

    # --- PESTAÑA: OVERVIEW GLOBAL ---
    with tab_overview_sen:
        st.markdown("#### 🌍 Resumen Global de Sensibilidad en Planta")
        
        try:
            # Extraer ambas tablas
            resp_cat_ov = supabase.table("catalogo_sensibilidad").select("id, nombre_producto, numero_parte, cliente, nivel_sensibilidad").execute()
            df_cat_ov = pd.DataFrame(resp_cat_ov.data)
            
            resp_comp_ov = supabase.table("componentes_sensibilidad").select("id_producto, esd_hbm, esd_cdm").execute()
            df_comp_ov = pd.DataFrame(resp_comp_ov.data)
            
            if not df_cat_ov.empty and not df_comp_ov.empty:
                # Convertir a numérico para poder calcular mínimos
                df_comp_ov['esd_hbm_num'] = pd.to_numeric(df_comp_ov['esd_hbm'].replace('-', pd.NA), errors='coerce')
                df_comp_ov['esd_cdm_num'] = pd.to_numeric(df_comp_ov['esd_cdm'].replace('-', pd.NA), errors='coerce')
                
                # Obtener el mínimo HBM y CDM por cada ID de producto
                minimos_por_producto = df_comp_ov.groupby('id_producto').agg({
                    'esd_hbm_num': 'min', 
                    'esd_cdm_num': 'min'
                }).reset_index()
                
                # Unir el catálogo de productos con sus voltajes mínimos
                df_consolidado = pd.merge(df_cat_ov, minimos_por_producto, left_on='id', right_on='id_producto', how='inner')
                
                if not df_consolidado.empty:
                    # Cálculos Globales
                    min_hbm_global = df_consolidado['esd_hbm_num'].min()
                    min_cdm_global = df_consolidado['esd_cdm_num'].min()
                    
                    # Identificar el proyecto más sensible evaluando el mínimo absoluto entre HBM y CDM
                    df_consolidado['min_absoluto'] = df_consolidado[['esd_hbm_num', 'esd_cdm_num']].min(axis=1)
                    idx_mas_sensible = df_consolidado['min_absoluto'].idxmin()
                    proyecto_critico = df_consolidado.loc[idx_mas_sensible]
                    
                    # 1. TARJETAS DE MÉTRICAS GLOBALES
                    st.markdown("##### 🚨 Proyecto Más Crítico (Mayor Riesgo ESD)")
                    c_crit1, c_crit2, c_crit3 = st.columns(3)
                    
                    nombre_critico = f"{proyecto_critico['nombre_producto']} ({proyecto_critico['cliente']})"
                    voltaje_critico = f"{proyecto_critico['min_absoluto']:g} V" if pd.notna(proyecto_critico['min_absoluto']) else "N/D"
                    
                    c_crit1.metric("Proyecto Más Sensible", nombre_critico, delta="Requiere máxima atención", delta_color="inverse")
                    c_crit2.metric("Mínimo Global HBM", f"{min_hbm_global:g} V" if pd.notna(min_hbm_global) else "N/D")
                    c_crit3.metric("Mínimo Global CDM", f"{min_cdm_global:g} V" if pd.notna(min_cdm_global) else "N/D")
                    
                    st.divider()
                    
                    # 2. TABLA DE RESUMEN POR CLIENTE
                    st.markdown("##### 🏢 Sensibilidad Mínima por Cliente")
                    
                    # Filtrar productos que tengan al menos un valor de voltaje válido
                    df_validos = df_consolidado.dropna(subset=['min_absoluto'])
                    
                    if not df_validos.empty:
                        # 1. Encontrar el índice (la fila) del registro con el voltaje más bajo para cada cliente
                        idx_min_por_cliente = df_validos.groupby('cliente')['min_absoluto'].idxmin()
                        
                        # 2. Extraer solo esas filas usando los índices localizados y seleccionar las columnas deseadas
                        resumen_cliente = df_validos.loc[idx_min_por_cliente, ['cliente', 'nombre_producto', 'esd_hbm_num', 'esd_cdm_num']].copy()
                        
                        # 3. Limpiar y formatear para la visualización en pantalla
                        resumen_cliente.columns = ['Cliente', 'Producto Más Crítico', 'Mínimo HBM (V)', 'Mínimo CDM (V)']
                        resumen_cliente['Mínimo HBM (V)'] = resumen_cliente['Mínimo HBM (V)'].apply(lambda x: f"{x:g}" if pd.notna(x) else "N/D")
                        resumen_cliente['Mínimo CDM (V)'] = resumen_cliente['Mínimo CDM (V)'].apply(lambda x: f"{x:g}" if pd.notna(x) else "N/D")
                        
                        st.dataframe(resumen_cliente, use_container_width=True, hide_index=True)
                    else:
                        st.info("No hay datos suficientes para generar el resumen por cliente.")
                    
                    # 3. GRÁFICA VISUAL RÁPIDA
                    st.markdown("##### 📊 Comparativa Visual de Riesgo (Voltaje Mínimo Absoluto por Producto)")
                    
                    # Preparamos los datos para la gráfica
                    df_grafica = df_consolidado.dropna(subset=['min_absoluto']).copy()
                    if not df_grafica.empty:
                        df_grafica = df_grafica.sort_values('min_absoluto')
                        
                        import plotly.express as px
                        fig = px.bar(
                            df_grafica, 
                            x='nombre_producto', 
                            y='min_absoluto', 
                            color='cliente',
                            labels={'nombre_producto': 'Producto', 'min_absoluto': 'Límite de Soporte (Volts)', 'cliente': 'Cliente'},
                            text_auto='.0f'
                        )
                        fig.update_traces(textposition='outside')
                        fig.update_layout(yaxis_title="Volts (Menor = Más Crítico)", xaxis_title="")
                        st.plotly_chart(fig, use_container_width=True)

                else:
                    st.info("No se pudieron consolidar los datos de catálogo y componentes.")
            else:
                st.info("Aún no hay suficientes datos procesados para generar el Overview.")
        except Exception as e:
            st.error(f"Error generando el Overview: {e}")

    # --- PESTAÑA: CONSULTA Y EXPORTACIÓN ---
    with tab_consulta:
        # Extraer clientes y productos de la base de datos
        try:
            resp_cat = supabase.table("catalogo_sensibilidad").select("*").execute()
            df_cat = pd.DataFrame(resp_cat.data)
        except Exception as e:
            df_cat = pd.DataFrame()
            st.error(f"Error conectando a la base de datos: {e}")

        if not df_cat.empty:
            c_filtro1, c_filtro2 = st.columns(2)
            clientes_disp = sorted(df_cat['cliente'].dropna().unique())
            cliente_sel = c_filtro1.selectbox("🏢 Selecciona el Cliente:", ["Todos"] + list(clientes_disp))
            
            df_filtrado_cli = df_cat if cliente_sel == "Todos" else df_cat[df_cat['cliente'] == cliente_sel]
            
            # Crear un diccionario para mostrar Nombre + Número de parte bonito en el selector
            opciones_prod = {row['id']: f"{row['nombre_producto']} (PN: {row['numero_parte']})" for _, row in df_filtrado_cli.iterrows()}
            
            if opciones_prod:
                prod_id_sel = c_filtro2.selectbox("📦 Selecciona el Producto:", options=list(opciones_prod.keys()), format_func=lambda x: opciones_prod[x])
                
                # Obtener detalles del producto seleccionado
                prod_info = df_filtrado_cli[df_filtrado_cli['id'] == prod_id_sel].iloc[0]
                numero_parte = str(prod_info['numero_parte']).strip()
                nombre_prod = str(prod_info['nombre_producto']).strip()
                
                # ID ÚNICO DEL REPORTE
                id_reporte_unico = f"BCS-SEN-{numero_parte.replace(' ', '')}-{nombre_prod.replace(' ', '_')}".upper()
                
                # Obtener componentes del producto
                resp_comp = supabase.table("componentes_sensibilidad").select("*").eq("id_producto", prod_id_sel).execute()
                df_comp = pd.DataFrame(resp_comp.data)
                
                if not df_comp.empty:
                    # Limpiar y convertir datos a numéricos para cálculos
                    df_comp['esd_hbm_num'] = pd.to_numeric(df_comp['esd_hbm'].replace('-', pd.NA), errors='coerce')
                    df_comp['esd_cdm_num'] = pd.to_numeric(df_comp['esd_cdm'].replace('-', pd.NA), errors='coerce')
                    
                    min_hbm = df_comp['esd_hbm_num'].min()
                    min_cdm = df_comp['esd_cdm_num'].min()
                    
                    comp_hbm = df_comp.loc[df_comp['esd_hbm_num'] == min_hbm, 'part_number'].iloc[0] if pd.notna(min_hbm) else "N/D"
                    comp_cdm = df_comp.loc[df_comp['esd_cdm_num'] == min_cdm, 'part_number'].iloc[0] if pd.notna(min_cdm) else "N/D"

                    st.markdown(f"#### 📄 ID Reporte: `{id_reporte_unico}`")
                    
                    # Tarjetas de resumen
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Cliente", prod_info['cliente'])
                    m2.metric("Nivel Sensibilidad", prod_info['nivel_sensibilidad'])
                    m3.metric("Voltaje Mín. HBM", f"{min_hbm:g} V" if pd.notna(min_hbm) else "N/D", comp_hbm, delta_color="off")
                    m4.metric("Voltaje Mín. CDM", f"{min_cdm:g} V" if pd.notna(min_cdm) else "N/D", comp_cdm, delta_color="off")
                    
                    st.markdown("##### 🧩 Desglose de Componentes")
                    df_mostrar = df_comp[['part_number', 'descripcion', 'ref_designator', 'qty', 'esd_cdm', 'esd_hbm', 'comentarios']].copy()
                    df_mostrar.columns = ['Part Number', 'Descripción', 'Ref Designator', 'Qty', 'CDM (V)', 'HBM (V)', 'Comentarios']
                    st.dataframe(df_mostrar.fillna("-"), use_container_width=True, hide_index=True)

                    # Exportar a CSV usando el ID único
                    csv_sen = df_mostrar.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Análisis en CSV",
                        data=csv_sen,
                        file_name=f"{id_reporte_unico}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.warning("No hay componentes registrados para este producto.")
            else:
                st.warning("No hay productos para este cliente.")
        else:
            st.info("Aún no hay reportes de sensibilidad en el sistema. Utiliza la pestaña 'Importar Histórico'.")

    # --- PESTAÑA: IMPORTACIÓN ---
    with tab_importar:
        st.markdown("#### 📂 Cargar Archivos de Sensibilidad")
        st.write("Sube uno o varios archivos CSV o Excel. El sistema buscará la tabla automáticamente a partir de la cabecera 'Part Number'.")
        
        # Agregamos accept_multiple_files=True
        archivos_sen = st.file_uploader("Selecciona los archivos", type=["csv", "xlsx"], accept_multiple_files=True)
        
        if archivos_sen:
            # Iteramos sobre todos los archivos subidos
            for idx, archivo_sen in enumerate(archivos_sen):
                with st.expander(f"📄 Procesando: {archivo_sen.name}", expanded=True):
                    try:
                        # Leer archivo crudo
                        if archivo_sen.name.endswith('.csv'):
                            df_raw = pd.read_csv(archivo_sen, header=None)
                        else:
                            df_raw = pd.read_excel(archivo_sen, header=None)
                        
                        # Intentar localizar el inicio de la tabla
                        fila_inicio = None
                        for i in range(min(20, len(df_raw))):
                            if df_raw.iloc[i].astype(str).str.contains("Part Number", case=False, na=False).any():
                                fila_inicio = i
                                break
                        
                        if fila_inicio is not None:
                            # Aislar la tabla y forzar TODAS las cabeceras a ser texto
                            df_tabla = df_raw.iloc[fila_inicio+1:].copy()
                            columnas_texto = [str(c) for c in df_raw.iloc[fila_inicio].tolist()]
                            df_tabla.columns = columnas_texto
                            
                            # Encontrar la columna real de "Part Number"
                            col_pn_real = next((c for c in df_tabla.columns if 'part number' in c.lower()), df_tabla.columns[1])
                            
                            # Quitar filas donde el Part Number esté vacío o sea NaN
                            df_tabla = df_tabla.dropna(subset=[col_pn_real])
                            df_tabla = df_tabla[df_tabla[col_pn_real].astype(str).str.strip() != '']
                            df_tabla = df_tabla[df_tabla[col_pn_real].astype(str).str.strip().str.lower() != 'nan']
                            
                            st.success(f"✅ Tabla detectada ({len(df_tabla)} componentes encontrados).")
                            
                            # Asignamos un key único al form usando el índice del archivo
                            with st.form(f"form_guardar_sensibilidad_{idx}"):
                                st.markdown("##### 📝 Confirma los Datos Generales del Producto")
                                # Pre-llenado inteligente
                                sug_pn = df_raw.iloc[4, 4] if len(df_raw) > 4 and len(df_raw.columns) > 4 else ""
                                sug_cliente = df_raw.iloc[5, 8] if len(df_raw) > 5 and len(df_raw.columns) > 8 else ""
                                sug_prod = df_raw.iloc[7, 4] if len(df_raw) > 7 and len(df_raw.columns) > 4 else "" 
                                sug_lvl = df_raw.iloc[7, 8] if len(df_raw) > 7 and len(df_raw.columns) > 8 else ""

                                col_f1, col_f2 = st.columns(2)
                                num_parte_imp = col_f1.text_input("Número de Parte", value=str(sug_pn).replace('nan','').strip())
                                nom_prod_imp = col_f2.text_input("Nombre del Producto", value=str(sug_prod).replace('nan','').strip())
                                
                                col_f3, col_f4 = st.columns(2)
                                cliente_imp = col_f3.text_input("Cliente", value=str(sug_cliente).replace('nan','').strip())
                                nivel_imp = col_f4.text_input("Nivel de Sensibilidad", value=str(sug_lvl).replace('nan','').strip())

                                if st.form_submit_button("💾 Guardar Reporte en Base de Datos", use_container_width=True):
                                    if num_parte_imp and nom_prod_imp and cliente_imp:
                                        with st.spinner("Registrando producto y componentes..."):
                                            # 1. Insertar el producto en el catálogo
                                            resp_ins_prod = supabase.table("catalogo_sensibilidad").insert({
                                                "numero_parte": num_parte_imp.upper(),
                                                "nombre_producto": nom_prod_imp.upper(),
                                                "cliente": cliente_imp.upper(),
                                                "nivel_sensibilidad": nivel_imp
                                            }).execute()
                                            
                                            id_nuevo_prod = resp_ins_prod.data[0]['id']
                                            
                                            # 2. Preparar e insertar componentes mapeando a las columnas de texto
                                            componentes_a_insertar = []
                                            cols = df_tabla.columns.tolist()
                                            pn_col = next((c for c in cols if 'part number' in c.lower()), cols[0])
                                            desc_col = next((c for c in cols if 'description' in c.lower()), cols[1])
                                            ref_col = next((c for c in cols if 'ref' in c.lower()), cols[3] if len(cols)>3 else None)
                                            qty_col = next((c for c in cols if 'qty' in c.lower()), cols[4] if len(cols)>4 else None)
                                            cdm_col = next((c for c in cols if 'cdm' in c.lower()), cols[5] if len(cols)>5 else None)
                                            hbm_col = next((c for c in cols if 'hbm' in c.lower()), cols[6] if len(cols)>6 else None)
                                            com_col = next((c for c in cols if 'comentario' in c.lower()), cols[7] if len(cols)>7 else None)

                                            for _, fila in df_tabla.iterrows():
                                                val_cdm = str(fila[cdm_col]) if cdm_col and pd.notna(fila[cdm_col]) else "-"
                                                val_hbm = str(fila[hbm_col]) if hbm_col and pd.notna(fila[hbm_col]) else "-"
                                                
                                                componentes_a_insertar.append({
                                                    "id_producto": id_nuevo_prod,
                                                    "part_number": str(fila[pn_col]) if pd.notna(fila[pn_col]) else "N/D",
                                                    "descripcion": str(fila[desc_col]) if pd.notna(fila[desc_col]) else "N/D",
                                                    "ref_designator": str(fila[ref_col]) if ref_col and pd.notna(fila[ref_col]) else "",
                                                    "qty": int(fila[qty_col]) if qty_col and pd.notna(fila[qty_col]) and str(fila[qty_col]).isnumeric() else 1,
                                                    "esd_cdm": val_cdm,
                                                    "esd_hbm": val_hbm,
                                                    "comentarios": str(fila[com_col]) if com_col and pd.notna(fila[com_col]) else ""
                                                })
                                            
                                            supabase.table("componentes_sensibilidad").insert(componentes_a_insertar).execute()
                                            
                                            st.success(f"✅ ¡Producto {nom_prod_imp} guardado con éxito! (Puedes continuar con los demás o limpiar los archivos).")
                                    else:
                                        st.error("Por favor completa Número de Parte, Nombre y Cliente.")
                        else:
                            st.error("❌ No se encontró la cabecera 'Part Number' en este archivo. Verifica el formato.")
                    except Exception as e:
                        st.error(f"Error procesando el archivo: {e}")
# ==========================================
# VISTA 10: TIERRAS, CONEXIONES Y PISO EPA
# ==========================================
elif st.session_state.vista_actual == "Tierras" and not st.session_state.modo_lectura:
    st.markdown("### 🌍 Control de Infraestructura a Tierra (EPA)")
    st.info("Monitoreo de Tierras Auxiliares (< 25 Ω), Conexiones de Pulsera (< 2.0 Ω) y Validación de Piso ESD (< 1.0x10^9 Ω).")

    tab_registro_t, tab_historial_t, tab_piso, tab_checadores = st.tabs([
        "📝 Tierras y Conexiones", 
        "📂 Historial", 
        "🗺️ Validación de Piso (EPA)", 
        "🛂 Checadores de Ingreso"
    ])

    # --- PESTAÑA 1: NUEVA MEDICIÓN (TIERRAS Y CONEXIONES) ---
    with tab_registro_t:
        st.markdown("#### ➕ Registrar Nueva Medición (Puntos Fijos)")
        
        try:
            resp_eq_t = supabase.table("equipos_medicion").select("id_equipo").execute()
            equipos_t = sorted([str(x['id_equipo']).strip() for x in resp_eq_t.data if x.get('id_equipo')])
        except:
            equipos_t = ["Error al cargar equipos"]

        if not equipos_t:
            equipos_t = ["Sin equipos registrados"]

        eq_default_t = "BCS-QRO-LAB-EMI001"
        idx_eq_t = equipos_t.index(eq_default_t) if eq_default_t in equipos_t else 0

        with st.form("form_tierras_aux"):
            c_tipo1, c_tipo2 = st.columns(2)
            tipo_punto_sel = c_tipo1.selectbox("1. Tipo de Punto a Medir:", ["Tierra Auxiliar", "Punto de Conexión de Pulsera"])
            linea_t_sel = c_tipo2.selectbox("2. Línea / Ubicación:", options=obtener_catalogo_lineas())
            
            c_det1, c_det2 = st.columns(2)
            id_punto_val = c_det1.text_input("3. ID del Punto (Opcional para Tierra Auxiliar):", placeholder="Ej: CP-01, Tierra-General...")
            equipo_t_sel = c_det2.selectbox("4. Equipo de Medición:", options=equipos_t, index=idx_eq_t)

            c_val1, c_val2 = st.columns(2)
            ohms_t = c_val1.number_input("5. Medición Registrada (Ohms):", min_value=0.0, max_value=9999.0, step=0.1, format="%.2f", value=None, placeholder="0.0")
            fecha_t = c_val2.date_input("6. Fecha de Verificación", datetime.today().date())

            if st.form_submit_button("💾 Guardar Medición", use_container_width=True):
                limite_aprobacion = 25.0 if tipo_punto_sel == "Tierra Auxiliar" else 2.0
                estatus_t = "PASA" if ohms_t < limite_aprobacion else "FALLA"
                id_final = id_punto_val.strip() if id_punto_val.strip() else "N/A"
                
                with st.spinner("Registrando..."):
                    try:
                        supabase.table("tierras_auxiliares").insert({
                            "tipo_punto": tipo_punto_sel,
                            "id_punto": id_final,
                            "linea": linea_t_sel,
                            "equipo_medicion": equipo_t_sel,
                            "medicion_ohms": float(ohms_t),
                            "fecha_medicion": fecha_t.isoformat(),
                            "estatus": estatus_t,
                            "auditor": st.session_state.usuario_nombre
                        }).execute()
                        
                        if estatus_t == "PASA":
                            st.success(f"✅ ¡Medición guardada! El punto {id_final} en {linea_t_sel} cumple con la especificación de < {limite_aprobacion} Ω.")
                        else:
                            st.error(f"🚨 ¡Atención! El punto registró {ohms_t} Ω, superando el límite permitido de {limite_aprobacion} Ω.")
                            
                        st.balloons()
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en SQL: {e}")

    # --- PESTAÑA 2: HISTORIAL INTERACTIVO ---
    with tab_historial_t:
        st.markdown("#### 🔄 Historial y Edición de Registros")
        
        try:
            resp_hist_t = supabase.table("tierras_auxiliares").select("*").order("fecha_medicion", desc=True).execute()
            df_hist_t = pd.DataFrame(resp_hist_t.data)
            
            if not df_hist_t.empty:
                df_edit = df_hist_t[['id', 'fecha_medicion', 'tipo_punto', 'linea', 'id_punto', 'medicion_ohms', 'estatus', 'equipo_medicion', 'auditor']].copy()
                df_edit['fecha_medicion'] = pd.to_datetime(df_edit['fecha_medicion']).dt.date
                
                edited_df = st.data_editor(
                    df_edit,
                    column_config={
                        "id": None, 
                        "fecha_medicion": st.column_config.DateColumn("Fecha", required=True),
                        "tipo_punto": st.column_config.TextColumn("Tipo", disabled=True),
                        "linea": st.column_config.TextColumn("Línea", disabled=True),
                        "id_punto": st.column_config.TextColumn("ID Punto", disabled=True),
                        "medicion_ohms": st.column_config.NumberColumn("Medición (Ω)", min_value=0.0, format="%.2f", required=True),
                        "estatus": st.column_config.TextColumn("Estatus (Auto)", disabled=True),
                        "equipo_medicion": st.column_config.TextColumn("Equipo", disabled=True),
                        "auditor": st.column_config.TextColumn("Auditor", disabled=True),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_tierras_conexiones"
                )
                
                if st.button("💾 Guardar Cambios Editados", type="primary"):
                    cambios_realizados = 0
                    with st.spinner("Actualizando registros en la base de datos..."):
                        for i, row in edited_df.iterrows():
                            orig_row = df_edit.iloc[i]
                            
                            if row['medicion_ohms'] != orig_row['medicion_ohms'] or row['fecha_medicion'] != orig_row['fecha_medicion']:
                                lim_calc = 25.0 if row.get('tipo_punto', 'Tierra Auxiliar') == 'Tierra Auxiliar' else 2.0
                                nuevo_estatus = "PASA" if row['medicion_ohms'] < lim_calc else "FALLA"
                                
                                try:
                                    supabase.table("tierras_auxiliares").update({
                                        "medicion_ohms": float(row['medicion_ohms']),
                                        "fecha_medicion": row['fecha_medicion'].isoformat(),
                                        "estatus": nuevo_estatus
                                    }).eq("id", row['id']).execute()
                                    cambios_realizados += 1
                                except Exception as e:
                                    st.error(f"Error al actualizar la línea {row['linea']}: {e}")
                                    
                    if cambios_realizados > 0:
                        st.success(f"✅ Se actualizaron correctamente {cambios_realizados} registros.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("Aún no hay mediciones registradas.")
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")

    # --- PESTAÑA 3: VALIDACIÓN DE PISO Y TAPETES ---
    with tab_piso:
        st.markdown("#### 🗺️ Control de Sistemas de Piso (EPA)")
        modo_piso = st.radio("Selecciona el tipo de superficie a evaluar:", ["🗺️ Cuadrícula General (Piso Fijo)", "🟦 Tapetes Antifatiga / Estación"], horizontal=True, label_visibility="collapsed")
        st.divider()

        # =======================================================
        # MODO A: PISO FIJO (CÓDIGO ORIGINAL DEL MAPA DE CALOR)
        # =======================================================
        if modo_piso == "🗺️ Cuadrícula General (Piso Fijo)":
            st.info("Medición de Resistencia a Tierra (RTG). Límite de aprobación: < 1.0x10^9 Ω.")
            
            # 1. DICCIONARIOS DE RECURSOS
            diagramas_cuartos = {
                "Cuarto 1": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/1.png",
                "Cuarto 2": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/2.png",
                "Cuarto 3": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/3.png",
                "Cuarto 4": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/4.png",
                "Cuarto 5": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/5.png",
                "Cuarto 6": "https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/testing/6.png"
            }

            COORDENADAS_PISOS = {
                "Cuarto 1": {1: (53, 649), 2: (241, 656), 3: (508, 651), 4: (576, 568), 5: (484, 567), 6: (242, 567), 7: (56, 472), 8: (241, 466), 9: (471, 466), 10: (533, 381), 11: (243, 384), 12: (242, 259), 13: (593, 258), 14: (205, 173), 15: (561, 66)},
                "Cuarto 2": {1: (38, 404), 2: (174, 365), 3: (154, 277), 4: (255, 222), 5: (109, 65), 6: (346, 85), 7: (523, 90), 8: (579, 211), 9: (334, 201), 10: (330, 380), 11: (253, 461), 12: (251, 585), 13: (588, 385), 14: (590, 511), 15: (482, 595)},
                "Cuarto 3": {1: (74, 585), 2: (128, 422), 3: (126, 199), 4: (263, 93), 5: (329, 37), 6: (614, 71), 7: (545, 180), 8: (341, 259), 9: (233, 338), 10: (280, 474), 11: (225, 586), 12: (424, 394), 13: (424, 543), 14: (549, 472), 15: (633, 380)},
                "Cuarto 4": {1: (71, 425), 2: (84, 271), 3: (117, 59), 4: (375, 60), 5: (503, 65), 6: (581, 205), 7: (547, 328), 8: (175, 335), 9: (274, 381), 10: (434, 375), 11: (415, 466), 12: (174, 557), 13: (598, 517), 14: (293, 629), 15: (568, 629)},
                "Cuarto 5": {1: (50, 81), 2: (107, 309), 3: (176, 569), 4: (293, 487), 5: (523, 563), 6: (826, 488), 7: (923, 376), 8: (682, 369), 9: (391, 276), 10: (733, 239), 11: (389, 145), 12: (718, 128), 13: (905, 215), 14: (860, 89), 15: (963, 547)},
                "Cuarto 6": {1: (92, 567), 2: (135, 466), 3: (112, 313), 4: (147, 167), 5: (185, 40), 6: (370, 42), 7: (708, 46), 8: (702, 196), 9: (368, 197), 10: (705, 295), 11: (370, 297), 12: (602, 387), 13: (707, 587), 14: (437, 587), 15: (247, 596)}
            }

            # Obtenemos equipos
            try:
                resp_eq_piso = supabase.table("equipos_medicion").select("id_equipo").execute()
                equipos_piso = sorted([str(x['id_equipo']).strip() for x in resp_eq_piso.data if x.get('id_equipo')])
            except:
                equipos_piso = ["Error al cargar equipos"]

            if not equipos_piso:
                equipos_piso = ["Sin equipos registrados"]

            cuarto_sel = st.selectbox("1. Selecciona el Cuarto a Validar:", options=list(diagramas_cuartos.keys()))
            
            # Inicializar borrador
            if "borrador_piso" not in st.session_state:
                st.session_state.borrador_piso = {}

            # 2. DESCARGAR LA IMAGEN PARA RECORTES DINÁMICOS
            import requests
            from PIL import Image
            from io import BytesIO
            
            img_url = diagramas_cuartos[cuarto_sel]
            img_pil = None
            img_w, img_h = 0, 0
            try:
                response = requests.get(img_url)
                img_pil = Image.open(BytesIO(response.content))
                img_w, img_h = img_pil.size
            except Exception as e:
                st.error("No se pudo cargar la imagen del cuarto de referencia.")

            # --- SECCIÓN A: MAPA GENERAL ESTÁTICO (REFERENCIA) ---
            with st.expander("👁️ Ver Mapa General del Cuarto", expanded=False):
                if img_pil:
                    st.image(img_pil, use_container_width=True)

            # --- SECCIÓN B: FORMULARIO DE CAPTURA VISUAL ---
            st.markdown("#### 📝 Captura Dinámica de Auditoría")
            with st.form("form_validacion_piso"):
                c_met1, c_met2, c_met3 = st.columns(3)
                equipo_piso_sel = c_met1.selectbox("Equipo de Medición:", options=equipos_piso)
                temp_piso = c_met2.text_input("Temperatura (°C):", value="23.5")
                hum_piso = c_met3.text_input("Humedad (% RH):", value="45")
                
                st.markdown("##### 📍 Captura de Puntos (Ohms)")
                st.caption("Si la medición está en formato científico, introdúcela como base y exponente (Ej: 5.2e7 -> 52000000). Deja en 0 los puntos que no apliquen.")
                st.divider()
                
                puntos_rtg = {}
                coords_map = COORDENADAS_PISOS.get(cuarto_sel, {})
                
                # Generamos las filas y columnas del formulario
                for fila in range(3):
                    cols = st.columns(5)
                    for col_idx in range(5):
                        punto_num = (fila * 5) + col_idx + 1
                        llave_unica = f"{cuarto_sel}_{punto_num}"
                        valor_previo = st.session_state.borrador_piso.get(llave_unica, None)
                        
                        with cols[col_idx]:
                            # 3. RECORTAR LA IMAGEN PARA EL PUNTO ESPECÍFICO
                            if img_pil and punto_num in coords_map:
                                cx, cy = coords_map[punto_num]
                                
                                # Definimos una "caja de recorte" de 200x200 píxeles centrada en el punto
                                box_size = 200 
                                left = max(0, cx - box_size)
                                upper = max(0, cy - box_size)
                                right = min(img_w, cx + box_size)
                                lower = min(img_h, cy + box_size)
                                
                                cropped_img = img_pil.crop((left, upper, right, lower))
                                # Mostramos el recorte con el número del punto como título
                                st.image(cropped_img, use_container_width=True, caption=f"📍 Punto {punto_num}")
                            else:
                                st.markdown(f"**📍 Punto {punto_num}**")
                                
                            # El input de captura justo debajo de la imagen
                            val = st.number_input("Ohms:", min_value=0.0, format="%.2e", step=1e6, value=valor_previo, placeholder="0.0", label_visibility="collapsed", key=f"input_{cuarto_sel}_{punto_num}")
                            puntos_rtg[punto_num] = val

                st.divider()
                c_btn1, c_btn2 = st.columns(2)
                btn_borrador = c_btn1.form_submit_button("📝 Guardar Borrador (Temporal)", use_container_width=True)
                submit_piso = c_btn2.form_submit_button("💾 Guardar Validación Final", type="primary", use_container_width=True)

            # Lógica formularios (Borrador / Guardado)
            if btn_borrador:
                for p_num, p_val in puntos_rtg.items():
                    if p_val is not None and p_val > 0: 
                        st.session_state.borrador_piso[f"{cuarto_sel}_{p_num}"] = p_val
                st.success("✅ Progreso guardado temporalmente.")

            if submit_piso:
                puntos_a_guardar = {k: v for k, v in puntos_rtg.items() if v is not None and v > 0}
                
                if not puntos_a_guardar:
                    st.error("⚠️ Registra al menos un punto.")
                else:
                    with st.spinner(f"Guardando..."):
                        registros_db = []
                        fecha_reg = datetime.now().isoformat()
                        for p_num, p_val in puntos_a_guardar.items():
                            estatus = "VIGENTE" if p_val < 1.0e9 else "VENCIDO"
                            registros_db.append({
                                "cuarto": cuarto_sel, "punto": p_num, "medicion_ohms": p_val,
                                "temperatura": temp_piso, "humedad": hum_piso, "equipo_medicion": equipo_piso_sel,
                                "estatus": estatus, "auditor": st.session_state.usuario_nombre, "fecha_medicion": fecha_reg
                            })
                        try:
                            supabase.table("validacion_piso").insert(registros_db).execute()
                            for p_num in range(1, 16): st.session_state.borrador_piso.pop(f"{cuarto_sel}_{p_num}", None)
                            st.success(f"✅ ¡Datos guardados!")
                            st.balloons()
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e: st.error(f"Error SQL: {e}")

            # --- SECCIÓN C: TABLA HISTÓRICA COMPLETA ---
            st.divider()
            st.markdown("#### 📂 Historial de Mediciones (Tabla)")
            try:
                resp_piso_hist = supabase.table("validacion_piso").select("*").eq("cuarto", cuarto_sel).order("fecha_medicion", desc=True).limit(500).execute()
                df_piso_hist = pd.DataFrame(resp_piso_hist.data)
                
                if not df_piso_hist.empty:
                    df_mostrar = df_piso_hist[['fecha_medicion', 'cuarto', 'punto', 'medicion_ohms', 'estatus', 'auditor']].copy()
                    df_mostrar['fecha_medicion'] = pd.to_datetime(df_mostrar['fecha_medicion']).dt.strftime('%d-%b-%Y')
                    df_mostrar['medicion_ohms'] = df_mostrar['medicion_ohms'].apply(lambda x: f"{float(x):.2e} Ω")
                    df_mostrar.columns = ['Fecha', 'Cuarto', 'Punto', 'Resistencia', 'Estatus', 'Auditor']
                    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No hay mediciones históricas registradas para el {cuarto_sel}.")
            except Exception as e:
                st.error(f"Error al cargar historial: {e}")


        # =======================================================
        # MODO B: TAPETES ANTIFATIGA / ESTACIÓN (INVENTARIO MAESTRO)
        # =======================================================
        elif modo_piso == "🟦 Tapetes Antifatiga / Estación":
            st.info("Los tapetes se registran e impactan directamente el Inventario Maestro de Mobiliario, pero se evalúan desde aquí para centralizar los sistemas de piso. Límite: < 1.0x10^9 Ω.")
            
            # 1. Traer los tapetes que ya existen en el inventario general
            try:
                resp_tpt = supabase.table("inventario_esd").select("id_producto, linea_ubicacion, valor_actual, fecha_ultima_verif, estatus_verificacion").eq("clasificacion", "Tapete de piso").execute()
                tapetes_existentes = pd.DataFrame(resp_tpt.data)
            except:
                tapetes_existentes = pd.DataFrame()

            c_tpt1, c_tpt2 = st.columns(2)
            linea_tpt = c_tpt1.selectbox("1. Línea / Ubicación:", options=obtener_catalogo_lineas(), key="tpt_linea")
            
            # 2. LÓGICA DE AUTOCOMPLETADO Y GENERACIÓN DE ID
            operacion_base = c_tpt2.text_input("2. Estación / Operación (Ej: OP-850)", placeholder="Ingresa la operación para buscar o generar un ID...")
            
            id_tpt_propuesto = ""
            if operacion_base:
                op_limpia = str(operacion_base).strip().upper()
                if not tapetes_existentes.empty:
                    # Buscamos si ya existen tapetes vinculados a esa operación (Ej: OP-850-TPT...)
                    tpt_relacionados = tapetes_existentes[tapetes_existentes['id_producto'].str.startswith(f"{op_limpia}-TPT", na=False)]
                    if not tpt_relacionados.empty:
                        # Extraemos la secuencia numérica del final
                        nums = tpt_relacionados['id_producto'].str.extract(r'-TPT(\d+)$')[0].dropna().astype(int)
                        if not nums.empty:
                            siguiente = nums.max() + 1
                            id_tpt_propuesto = f"{op_limpia}-TPT{siguiente}"
                        else:
                            id_tpt_propuesto = f"{op_limpia}-TPT2" # Si existía OP-850-TPT, sigue el TPT2
                    else:
                        id_tpt_propuesto = f"{op_limpia}-TPT1"
                else:
                    id_tpt_propuesto = f"{op_limpia}-TPT1"

            # 3. SELECTOR / CREADOR FINAL
            lista_ids_tpt = sorted(tapetes_existentes['id_producto'].dropna().unique().tolist()) if not tapetes_existentes.empty else []
            
            # Inyectamos la sugerencia matemática hasta arriba para que sea la predeterminada
            if id_tpt_propuesto and id_tpt_propuesto not in lista_ids_tpt:
                lista_ids_tpt = [id_tpt_propuesto] + lista_ids_tpt
                
            id_tpt_final = st.selectbox("3. ID del Tapete (Selecciona uno existente o usa el sugerido):", options=lista_ids_tpt, index=0 if lista_ids_tpt else None)
            
            st.divider()

            # 4. FORMULARIO DE MEDICIÓN
            if id_tpt_final:
                # Verificamos si este ID ya existe para mostrar su historial reciente
                es_nuevo = True
                if not tapetes_existentes.empty and id_tpt_final in tapetes_existentes['id_producto'].values:
                    es_nuevo = False
                    datos_previos = tapetes_existentes[tapetes_existentes['id_producto'] == id_tpt_final].iloc[0]
                    col_info1, col_info2, col_info3 = st.columns(3)
                    col_info1.metric("Última Medición", str(datos_previos.get('fecha_ultima_verif'))[:10])
                    val_prev_float = float(datos_previos.get('valor_actual')) if pd.notna(datos_previos.get('valor_actual')) else 0.0
                    col_info2.metric("Valor Anterior", f"{val_prev_float:.2e} Ω")
                    col_info3.metric("Estatus Actual", str(datos_previos.get('estatus_verificacion')))

                with st.form("form_val_tapetes"):
                    titulo_form = "✨ Registrar Nuevo Tapete" if es_nuevo else "🔄 Actualizar Tapete Existente"
                    st.markdown(f"##### {titulo_form}: `{id_tpt_final}`")
                    
                    c_amb1, c_amb2 = st.columns(2)
                    temp_tpt = c_amb1.number_input("Temperatura (°C)", value=23.5, step=0.1)
                    hum_tpt = c_amb2.number_input("Humedad (%)", value=45, step=1)
                    
                    c_val1, c_val2 = st.columns(2)
                    res_tpt = c_val1.number_input("Resistencia a Tierra (Ω)", min_value=0.0, format="%.2e", step=1e6, value=None, placeholder="Ej: 5.0e7")
                    c_val2.text_input("Límite Permitido", value="1.00e+09 Ω", disabled=True)
                    
                    notas_tpt = st.text_input("Observaciones (Opcional)")
                    
                    if st.form_submit_button("💾 Guardar Validación de Tapete en Inventario", type="primary", use_container_width=True):
                        if res_tpt is None:
                            st.error("⚠️ Debes capturar el valor de resistencia de la medición actual.")
                        else:
                            with st.spinner("Integrando al padrón maestro de Mobiliario..."):
                                from dateutil.relativedelta import relativedelta
                                lim_tpt = 1e9
                                estatus_tpt = "VIGENTE" if res_tpt < lim_tpt else "VENCIDO"
                                fecha_hoy = datetime.now()
                                prox_fecha = (fecha_hoy + relativedelta(years=1)).isoformat()
                                
                                # Payload inteligente (UPSERT): Si no existe lo crea, si existe lo actualiza
                                payload_tpt = {
                                    "id_producto": id_tpt_final,
                                    "categoria": "Mobiliario",
                                    "clasificacion": "Tapete de piso",
                                    "linea_ubicacion": linea_tpt,
                                    "estatus_operativo": "OPERATIVO",
                                    "limite_minimo": 0.0,
                                    "limite_maximo": lim_tpt,
                                    "unidad_medida": "Ohms",
                                    "valor_actual": float(res_tpt),
                                    "fecha_ultima_verif": fecha_hoy.isoformat(),
                                    "fecha_proxima_verif": prox_fecha,
                                    "estatus_verificacion": estatus_tpt,
                                    "frecuencia": "Anual",
                                    "auditor_responsable": st.session_state.usuario_nombre,
                                    "comentarios": notas_tpt
                                }
                                
                                try:
                                    # Acción 1: Actualizar o insertar en el Inventario de Activos
                                    supabase.table("inventario_esd").upsert(payload_tpt).execute()
                                    
                                    # Acción 2: Dejar huella en el historial para gráficas de degradación y auditorías pasadas
                                    supabase.table("historial_mediciones").insert({
                                        "id_equipo": id_tpt_final,
                                        "tipo_equipo": "Tapete de piso",
                                        "ubicacion": linea_tpt,
                                        "valor_actual": float(res_tpt),
                                        "fecha_validacion": fecha_hoy.isoformat(),
                                        "fecha_vencimiento": prox_fecha,
                                        "auditor": st.session_state.usuario_nombre,
                                        "fecha_modificacion": fecha_hoy.isoformat()
                                    }).execute()
                                    
                                    st.success(f"✅ Tapete {id_tpt_final} asimilado con éxito. Estatus: {estatus_tpt}")
                                    st.balloons()
                                    st.cache_data.clear()
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al integrar el tapete en la base de datos: {e}")
    # --- PESTAÑA 4: CHECADORES INTEGRADOS (NUEVO) ---
    with tab_checadores:
        st.markdown("#### 🛂 Verificación Mensual de Checadores Integrados")
        st.info("La variación máxima que podemos obtener es el 5% sobre el rango total de medición (1e9 ohms). El valor de referencia es el del megóhmetro.")

        # Opciones fijas para los 4 checadores que mencionas
        checadores_disponibles = ["CHECADOR-01", "CHECADOR-02", "CHECADOR-03", "CHECADOR-04"]

        with st.form("form_verif_checadores"):
            c_ch1, c_ch2, c_ch3 = st.columns(3)
            id_checador = c_ch1.selectbox("1. Equipo a verificar:", checadores_disponibles)
            equipo_ref = c_ch2.selectbox("2. Megóhmetro (Referencia):", equipos_t) # Usamos la lista de equipos cargada arriba
            fecha_verif = c_ch3.date_input("3. Fecha de Verificación", datetime.today().date())

            st.markdown("##### 👣 Pie Izquierdo")
            col_izq1, col_izq2 = st.columns(2)
            ref_izq = col_izq1.number_input("Megóhmetro (Referencia) - Izq (Ohms)", min_value=0.0, format="%.2e", step=1e6, key="ref_izq", value=None, placeholder="Ej: 1.00e+08")
            lec_izq = col_izq2.number_input("Lectura Checador - Izq (Ohms)", min_value=0.0, format="%.2e", step=1e6, key="lec_izq", value=None, placeholder="Ej: 1.05e+08")

            st.markdown("##### 👣 Pie Derecho")
            col_der1, col_der2 = st.columns(2)
            ref_der = col_der1.number_input("Megóhmetro (Referencia) - Der (Ohms)", min_value=0.0, format="%.2e", step=1e6, key="ref_der", value=None, placeholder="Ej: 1.00e+08")
            lec_der = col_der2.number_input("Lectura Checador - Der (Ohms)", min_value=0.0, format="%.2e", step=1e6, key="lec_der", value=None, placeholder="Ej: 9.80e+07")
            
            obs_checador = st.text_input("Observaciones / Notas:")

            if st.form_submit_button("💾 Comparar y Guardar Verificación", use_container_width=True):
                if ref_izq is None or lec_izq is None or ref_der is None or lec_der is None:
                    st.error("⚠️ Debes ingresar todas las lecturas (Megóhmetro y Checador) para ambos pies.")
                else:
                    # 1. Cálculo de Desviación Absoluta
                    desv_izq = abs(lec_izq - ref_izq)
                    desv_der = abs(lec_der - ref_der)
                    
                    # 2. Límite de 5% sobre 1e9 Ohms (50,000,000 Ohms)
                    limite_desv = 1e9 * 0.05 
                    
                    # 3. Evaluación de Estatus
                    if desv_izq <= limite_desv and desv_der <= limite_desv:
                        estatus_ch = "PASA"
                    else:
                        estatus_ch = "FALLA"
                        
                    # 4. Feedback Visual Inmediato
                    st.markdown("##### 📊 Resultados de la Desviación")
                    c_res1, c_res2 = st.columns(2)
                    c_res1.metric("Desviación P. Izquierdo", f"{desv_izq:.2e} Ω", delta="Dentro del límite" if desv_izq <= limite_desv else "Excede el límite", delta_color="normal" if desv_izq <= limite_desv else "inverse")
                    c_res2.metric("Desviación P. Derecho", f"{desv_der:.2e} Ω", delta="Dentro del límite" if desv_der <= limite_desv else "Excede el límite", delta_color="normal" if desv_der <= limite_desv else "inverse")

                    with st.spinner("Guardando en la base de datos..."):
                        try:
                            # Inserción a la nueva tabla en Supabase
                            supabase.table("verificacion_checadores").insert({
                                "id_checador": id_checador,
                                "megohmetro_utilizado": equipo_ref,
                                "fecha_verificacion": fecha_verif.isoformat(),
                                "ref_izq": float(ref_izq),
                                "lec_izq": float(lec_izq),
                                "desviacion_izq": float(desv_izq),
                                "ref_der": float(ref_der),
                                "lec_der": float(lec_der),
                                "desviacion_der": float(desv_der),
                                "estatus": estatus_ch,
                                "auditor": st.session_state.usuario_nombre,
                                "observaciones": obs_checador
                            }).execute()
                            
                            if estatus_ch == "PASA":
                                st.success(f"✅ Verificación exitosa. Las variaciones no superan el 5% sobre el rango total (5.00e+07 Ω).")
                                st.balloons()
                            else:
                                st.error("🚨 ¡Falla de Calibración! El checador muestra desviaciones superiores al límite permitido contra el megóhmetro.")
                                
                        except Exception as e:
                            st.error(f"Error al guardar el registro en SQL. ¿Ya creaste la tabla 'verificacion_checadores'? Detalle: {e}")

#####################################
#VISTA ENTRENAMIENTO
#####################################

elif st.session_state.vista_actual == "Entrenamiento" and not st.session_state.modo_lectura:
    st.markdown("### 🎓 Gestión de Entrenamiento y Certificación ESD")
    st.info("Administra el historial de capacitaciones, calificaciones y analiza las áreas de oportunidad (preguntas con mayor índice de falla).")

    tab_dash, tab_historico, tab_semanal, tab_auditoria = st.tabs([
        "📊 Dashboard de Resultados", 
        "📥 Cargar Histórico (Forms)", 
        "🔄 Actualización Semanal",
        "🕵️ Auditoría Cronológica"
    ])

    # --- PESTAÑA 1: DASHBOARD Y ANÁLISIS ---
    with tab_dash:
        st.markdown("#### 📊 Dashboard de Certificación y Cumplimiento ESD")
        st.write("Monitoreo en tiempo real de vigencias. El sistema calcula los vencimientos **exclusivamente** a partir de la última evaluación del personal activo.")
        
        # Configuración de ventanas de tiempo relativas al día de hoy
        hoy = datetime.today().date()
        limite_365 = hoy + timedelta(days=365)
        
        primer_dia_mes = hoy.replace(day=1)
        if hoy.month == 12:
            ultimo_dia_mes = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            ultimo_dia_mes = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)

        # 1. Cargar padrón maestro (FUENTE DE LA VERDAD UNIFICADA PARA FECHAS)
        try:
            # AGREGADO: 'fecha_ingreso' para poder validar la sanidad de los datos durante el cruce
            resp_maestro = supabase.table("empleados_batas").select("num_empleado, nombre, fecha_ingreso, fecha_ultimo_entrenamiento, fecha_proximo_entrenamiento").eq("estatus_empleado", "Activo").execute()
            df_maestro = pd.DataFrame(resp_maestro.data)
        except Exception as e:
            df_maestro = pd.DataFrame()
            st.error(f"Error al conectar con la base maestra de personal: {e}")

        # 2. Cargar historial completo de exámenes (Para extraer calificaciones y fechas de rescate)
        try:
            resp_todo_train = supabase.table("entrenamientos_esd").select("num_empleado, fecha_entrenamiento, calificacion_total, detalle_respuestas").execute()
            df_todo_train = pd.DataFrame(resp_todo_train.data)
        except Exception as e:
            df_todo_train = pd.DataFrame()

        # =====================================================================
        # 3. FILTRO MAESTRO GLOBAL UNIFICADO Y AUTO-SANIDAD
        # =====================================================================
        if not df_maestro.empty:
            df_maestro['num_empleado'] = df_maestro['num_empleado'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_maestro = df_maestro.drop_duplicates(subset=['num_empleado'], keep='first')
            
            # Formatear fechas desde la tabla maestra
            df_maestro['fecha_entrenamiento_oficial'] = pd.to_datetime(df_maestro['fecha_ultimo_entrenamiento'], errors='coerce').dt.date
            df_maestro['fecha_proximo'] = pd.to_datetime(df_maestro['fecha_proximo_entrenamiento'], errors='coerce').dt.date
            
            if not df_todo_train.empty:
                df_todo_train['num_empleado'] = df_todo_train['num_empleado'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                df_todo_train['fecha_entrenamiento'] = pd.to_datetime(df_todo_train['fecha_entrenamiento'], errors='coerce')
                
                # Extraer la última calificación y FECHA registrada
                df_recientes = df_todo_train.sort_values('fecha_entrenamiento', ascending=False).drop_duplicates(subset=['num_empleado'], keep='first')
                
                # CORRECCIÓN VITAL: Mantener 'fecha_entrenamiento' en el DataFrame cruzado
                df_recientes = df_recientes[['num_empleado', 'fecha_entrenamiento', 'calificacion_total', 'detalle_respuestas']]
            else:
                df_recientes = pd.DataFrame(columns=['num_empleado', 'fecha_entrenamiento', 'calificacion_total', 'detalle_respuestas'])

            # Unir padrón maestro con su última calificación
            df_merged = pd.merge(df_maestro, df_recientes, on='num_empleado', how='left')
            
            # --- NUEVO: AUTO-SANIDAD DE DATOS (RESCATE DE EXÁMENES DESINCRONIZADOS Y SOBREESCRITOS) ---
            if 'fecha_entrenamiento' in df_merged.columns:
                df_merged['ingreso_dt'] = pd.to_datetime(df_merged['fecha_ingreso'], errors='coerce')
                
                # Convertimos la fecha oficial a datetime para compararla matemáticamente
                f_oficial_dt = pd.to_datetime(df_merged['fecha_entrenamiento_oficial'], errors='coerce')
                
                # Condición 1: Está en blanco pero sí hay examen registrado en el historial
                cond1 = df_merged['fecha_entrenamiento_oficial'].isna() & df_merged['fecha_entrenamiento'].notna()
                
                # Condición 2: La fecha oficial en la ficha quedó "atrasada" por subir un Excel viejo después de uno nuevo
                cond2 = df_merged['fecha_entrenamiento'].notna() & f_oficial_dt.notna() & (f_oficial_dt.dt.date < df_merged['fecha_entrenamiento'].dt.date)
                
                mask_rescate = cond1 | cond2
                
                # Respetamos la Cronología: NO rescatamos si el examen es más viejo que su fecha de ingreso oficial
                mask_valida = df_merged['ingreso_dt'].isna() | (df_merged['fecha_entrenamiento'] >= df_merged['ingreso_dt'])
                mask_rescate = mask_rescate & mask_valida

                if mask_rescate.any():
                    # Si detecta desfase, sobreescribe en vivo con la fecha real del examen más reciente
                    df_merged.loc[mask_rescate, 'fecha_entrenamiento_oficial'] = df_merged.loc[mask_rescate, 'fecha_entrenamiento'].dt.date
                    df_merged.loc[mask_rescate, 'fecha_proximo'] = (df_merged.loc[mask_rescate, 'fecha_entrenamiento'] + pd.DateOffset(years=1)).dt.date
            # -------------------------------------------------------------------------
            
            # Recalcular calificación real base 10 leyendo el JSON del último intento
            def calcular_nota_real(row):
                detalle = row.get('detalle_respuestas', {})
                if isinstance(detalle, dict) and len(detalle) > 0:
                    total_r = len(detalle)
                    aciertos = sum([1.0 for v in detalle.values() if float(v) > 0])
                    return round((aciertos / total_r) * 10.0, 2)
                else:
                    try:
                        return min(float(row['calificacion_total']), 10.0)
                    except:
                        return 0.0
                        
            df_merged['nota_real_base_10'] = df_merged.apply(calcular_nota_real, axis=1)

            # --- SEGMENTACIÓN DE DATOS PARA MÉTRICAS ---
            
            # A) Sin Vigencia / Vencidos (No tienen fecha oficial de próximo O ya expiró)
            mask_sin_vigencia = df_merged['fecha_proximo'].isna() | (df_merged['fecha_proximo'] < hoy)
            df_sin_vigencia = df_merged[mask_sin_vigencia]

            # B) Cronograma General (Próximos 365 días EXCLUSIVAMENTE, omite pasados)
            mask_proximos_365 = (df_merged['fecha_proximo'] >= hoy) & (df_merged['fecha_proximo'] <= limite_365)
            df_vencen_anio = df_merged[mask_proximos_365]

            # C) Vencen este mes
            mask_mes = (df_merged['fecha_proximo'] >= hoy) & (df_merged['fecha_proximo'] <= ultimo_dia_mes)
            df_vencen_mes = df_merged[mask_mes]

            # D) Notas Críticas: Solo los que SÍ tienen fecha de entrenamiento oficial y su último intento es <= 7.0
            mask_tiene_examen = df_merged['fecha_entrenamiento_oficial'].notna()
            df_bajos = df_merged[mask_tiene_examen & (df_merged['nota_real_base_10'] <= 7.0)]

            # --- DESPLIEGUE DE KPI CARDS (4 Columnas) ---
            c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
            c_kpi1.metric("🚨 Sin Vigencia / Vencidos", len(df_sin_vigencia), delta="Acción Requerida", delta_color="inverse" if len(df_sin_vigencia) > 0 else "normal")
            c_kpi2.metric("📌 Vencen este Mes", len(df_vencen_mes), delta=f"Límite: {ultimo_dia_mes.strftime('%d-%b')}")
            c_kpi3.metric("📅 Proyección 365", len(df_vencen_anio), delta="Próximos 12 Meses", delta_color="off")
            c_kpi4.metric("⚠️ Notas ≤ 80%", len(df_bajos), delta="Requieren Capacitación", delta_color="inverse" if len(df_bajos) > 0 else "normal")

            st.divider()

            # --- TABLAS OPERACIONALES ---
            col_tablas1, col_tablas2 = st.columns(2)
            
            with col_tablas1:
                st.markdown("##### 🚨 Personal SIN Entrenamiento Vigente (Prioridad)")
                if not df_sin_vigencia.empty:
                    df_sin_vigencia_show = df_sin_vigencia[['num_empleado', 'nombre', 'fecha_proximo']].copy()
                    df_sin_vigencia_show['fecha_proximo'] = df_sin_vigencia_show['fecha_proximo'].fillna("Sin Registro / Nunca Evaluado")
                    df_sin_vigencia_show.columns = ['No. Empleado', 'Nombre', 'Estatus Vigencia']
                    st.dataframe(df_sin_vigencia_show, width="stretch", hide_index=True)
                else:
                    st.success("🎉 Óptimo: Todo el personal activo cuenta con entrenamiento vigente.")

                st.markdown("##### 🔴 Notas Críticas Activas (≤ 80%)")
                if not df_bajos.empty:
                    # Usamos la fecha oficial unificada para mostrarla en la tabla
                    df_bajos_show = df_bajos[['num_empleado', 'nombre', 'nota_real_base_10', 'fecha_entrenamiento_oficial']].copy()
                    df_bajos_show['fecha_entrenamiento_oficial'] = pd.to_datetime(df_bajos_show['fecha_entrenamiento_oficial']).dt.strftime('%d-%b-%Y')
                    df_bajos_show.columns = ['No. Empleado', 'Nombre', 'Calificación Real', 'Último Examen']
                    st.dataframe(df_bajos_show, width="stretch", hide_index=True)
                else:
                    st.success("🎉 Ningún usuario activo tiene calificación reprobatoria en su evaluación más reciente.")

            with col_tablas2:
                st.markdown("##### 📅 Cronograma de Reentrenamientos")
                
                # --- NUEVO: SELECTOR DE PROYECCIÓN DINÁMICA ---
                from dateutil.relativedelta import relativedelta
                opciones_tiempo = {
                    "Próximo Mes": 1, 
                    "Próximos 3 Meses": 3, 
                    "Próximos 6 Meses": 6, 
                    "Próximos 12 Meses": 12
                }
                filtro_meses = st.selectbox("⏳ Rango de proyección:", options=list(opciones_tiempo.keys()), index=3)
                
                # Calcular el límite de fecha basado en la selección
                meses_delta = opciones_tiempo[filtro_meses]
                limite_dinamico = hoy + relativedelta(months=meses_delta)
                
                # Filtrar el padrón maestro según la nueva ventana de tiempo
                mask_dinamica = (df_merged['fecha_proximo'] >= hoy) & (df_merged['fecha_proximo'] <= limite_dinamico)
                df_vencen_dinamico = df_merged[mask_dinamica]

                if not df_vencen_dinamico.empty:
                    df_vencen_show = df_vencen_dinamico[['num_empleado', 'nombre', 'fecha_proximo']].copy()
                    df_vencen_show = df_vencen_show.sort_values('fecha_proximo') # Ordenar los más próximos a vencer arriba
                    df_vencen_show.columns = ['No. Empleado', 'Nombre', 'Próximo Reentrenamiento']
                    
                    st.dataframe(df_vencen_show, width="stretch", hide_index=True)
                    st.caption(f"Mostrando {len(df_vencen_show)} vencimientos proyectados hasta el {limite_dinamico.strftime('%d-%b-%Y')}.")
                else:
                    st.info(f"No hay reentrenamientos proyectados para el rango de '{filtro_meses}'.")
            # =====================================================================
            # NUEVA SECCIÓN: RESUMEN DE CALIFICACIONES POR SEMANA
            # =====================================================================
            st.divider()
            st.markdown("#### 📅 Resumen de Calificaciones por Semana")
            st.caption("Filtra por rango de fechas para visualizar la distribución y el porcentaje de aprobación semanal.")
            
            c_f1, c_f2 = st.columns(2)
            # Por defecto: desde el inicio del año actual hasta hoy
            from datetime import date
            fecha_inicio_filtro = c_f1.date_input("Fecha de Inicio", date(hoy.year, 1, 1))
            fecha_fin_filtro = c_f2.date_input("Fecha de Fin", hoy)

            if not df_todo_train.empty:
                df_semanal = df_todo_train.copy()
                df_semanal['fecha_entrenamiento'] = pd.to_datetime(df_semanal['fecha_entrenamiento'], errors='coerce')
                
                # 1. Filtrar por el rango de fechas seleccionado
                mask_fechas = (df_semanal['fecha_entrenamiento'].dt.date >= fecha_inicio_filtro) & (df_semanal['fecha_entrenamiento'].dt.date <= fecha_fin_filtro)
                df_semanal = df_semanal[mask_fechas]

                if not df_semanal.empty:
                    # 2. Calcular nota real base 10 (reutilizamos tu función ya existente)
                    df_semanal['Nota'] = df_semanal.apply(calcular_nota_real, axis=1)

                    # 3. Extraer el Mes y la Semana ISO (WK)
                    df_semanal['Mes'] = df_semanal['fecha_entrenamiento'].dt.month
                    df_semanal['Semana'] = "WK " + df_semanal['fecha_entrenamiento'].dt.isocalendar().week.astype(str)

                    # 4. Clasificar cada examen en su columna correspondiente
                    df_semanal['Reprobados'] = (df_semanal['Nota'] < 8.0).astype(int)
                    df_semanal['Calif_8'] = ((df_semanal['Nota'] >= 8.0) & (df_semanal['Nota'] < 9.0)).astype(int)
                    df_semanal['Calif_9'] = ((df_semanal['Nota'] >= 9.0) & (df_semanal['Nota'] < 10.0)).astype(int)
                    df_semanal['Calif_10'] = (df_semanal['Nota'] >= 10.0).astype(int)

                    # 5. Agrupar la información
                    agrupado = df_semanal.groupby(['Mes', 'Semana']).agg(
                        Examenes_aplicados=('num_empleado', 'count'),
                        No_aprobados=('Reprobados', 'sum'),
                        Calif_8=('Calif_8', 'sum'),
                        Calif_9=('Calif_9', 'sum'),
                        Calif_10=('Calif_10', 'sum')
                    ).reset_index()

                    # 6. Calcular el porcentaje de aprobación
                    agrupado['Aprobación de examenes %'] = agrupado.apply(
                        lambda x: round((x['Examenes_aplicados'] - x['No_aprobados']) / x['Examenes_aplicados'] * 100, 2) if x['Examenes_aplicados'] > 0 else 0.0, 
                        axis=1
                    )

                    # Renombrar columnas para que coincidan con tu formato deseado
                    agrupado.columns = ['Mes', 'Semana', 'Exámenes aplicados', 'Exámenes no aprobados <8', 'Calificación 8', 'Calificación 9', 'Calificación 10', 'Aprobación de examenes %']

                    # 7. Crear el mapeo de colores (semáforo) al estilo de Excel
                    def estilar_aprobacion(val):
                        try:
                            v = float(val)
                            if v >= 90: return 'background-color: #63be7b; color: white; font-weight: bold;' # Verde Fuerte
                            elif v >= 80: return 'background-color: #c6d96e; color: black; font-weight: bold;' # Verde/Amarillo
                            elif v >= 70: return 'background-color: #ffeb84; color: black; font-weight: bold;' # Amarillo
                            elif v >= 60: return 'background-color: #f7aa67; color: black; font-weight: bold;' # Naranja
                            else: return 'background-color: #e55c5c; color: white; font-weight: bold;'        # Rojo
                        except:
                            return ''

                    # Aplicar formato visual al DataFrame
                    df_estilado_semanal = agrupado.style.map(estilar_aprobacion, subset=['Aprobación de examenes %']).format({
                        "Aprobación de examenes %": "{:.2f}"
                    })
                    
                    st.dataframe(df_estilado_semanal, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay exámenes registrados en el rango de fechas seleccionado.")
            else:
                st.info("La base de datos de entrenamientos está vacía.")
            
            # --- ANÁLISIS AVANZADO DE REACTIVOS (CON FILTRADO CONCEPTUAL) ---
            st.divider()
            st.markdown("#### 🧠 Análisis de Reactivos Críticos (Áreas de Oportunidad Técnica)")
            st.caption("Gráfica automatizada que contabiliza las incorrecciones del personal únicamente en reactivos de conocimiento de control de descargas electrostáticas.")
            
            if not df_todo_train.empty:
                todas_respuestas = []
                for _, row in df_todo_train.iterrows():
                    resp_json = row.get('detalle_respuestas', {})
                    if isinstance(resp_json, dict):
                        for pregunta, puntaje in resp_json.items():
                            # EXCLUSIÓN CRÍTICA: Filtrar y omitir preguntas sobre el capacitador, instructor o la calidad del curso
                            palabras_filtro = [
                                'qué te pareció', 'que te parecio',
                                'qué le mejorarías', 'que le mejorarias',
                                'desempeño del capacitador', 'desempeño del',
                                'capacitador', 'instructor', 'curso',
                                'comentarios', 'sugerencias', 'evaluación', 
                                'evaluacion del', 'entrenador', 'entrenamiento', 
                                'instalaciones', 'recomendarías', 'recomendar', 
                                'satisfacción', 'material didáctico', 'rh', 
                                'recursos humanos', 'utilidad', 'fomento', 'trabajo', 'conocimientos', 'cambiarías', 'presentaciones', 'califica', 'conocimientos'
                            ]
                            
                            if any(x in pregunta.lower() for x in palabras_filtro):
                                continue
                                
                            try:
                                p = float(puntaje)
                                acertada = 1 if p > 0 else 0
                            except:
                                acertada = 0
                            todas_respuestas.append({"Pregunta": pregunta, "Acertada": acertada})
                
                if todas_respuestas:
                    df_resp = pd.DataFrame(todas_respuestas)
                    resumen_preguntas = df_resp.groupby('Pregunta').agg(
                        Total_Intentos=('Acertada', 'count'),
                        Aciertos=('Acertada', 'sum')
                    ).reset_index()
                    
                    resumen_preguntas['Porcentaje_Falla'] = ((resumen_preguntas['Total_Intentos'] - resumen_preguntas['Aciertos']) / resumen_preguntas['Total_Intentos']) * 100
                    resumen_preguntas = resumen_preguntas.sort_values('Porcentaje_Falla', ascending=False)
                    
                    # Limpieza estética de las cabeceras nativas de Microsoft Forms
                    resumen_preguntas['Concepto Técnico'] = resumen_preguntas['Pregunta'].str.replace('Puntos: ', '', regex=False).str.strip()
                    
                    # Descartar meta-columnas del archivo que no sean preguntas reales
                    df_preguntas_reales = resumen_preguntas[~resumen_preguntas['Concepto Técnico'].str.contains('Nombre|Puesto|Número|Fecha|Turno|Exámen|Examen', case=False, na=False)].head(5)
                    
                    if not df_preguntas_reales.empty:
                        fig = px.bar(
                            df_preguntas_reales, 
                            x='Porcentaje_Falla', 
                            y='Concepto Técnico', 
                            orientation='h',
                            text_auto='.1f',
                            labels={'Porcentaje_Falla': '% de Fallas Globales', 'Concepto Técnico': 'Reactivo Evaluado'},
                            title="Top 5 Conceptos Técnicos con Mayor Frecuencia de Error",
                            color='Porcentaje_Falla',
                            color_continuous_scale='Reds'
                        )
                        fig.update_layout(yaxis={'categoryorder':'total ascending'}, coloraxis_showscale=False, height=320, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("No se localizaron reactivos de conocimiento puro tras aplicar los filtros conceptuales.")
            # =====================================================================
            # 🔍 SECCIÓN: BÚSQUEDA INTERACTIVA POR EMPLEADO 
            # =====================================================================
            st.divider()
            st.markdown("#### 🔍 Consultar Historial Individual de Entrenamiento")
            st.write("Introduce el número de empleado para extraer su expediente completo de certificaciones, puesto y fecha de ingreso.")
    
            # 1. Variable para recordar a quién estamos auditando (Persistencia tras abrir expanders)
            if "empleado_consultado" not in st.session_state:
                st.session_state.empleado_consultado = ""
    
            with st.form("form_busqueda_individual"):
                c_search1, c_search2 = st.columns([3, 1])
                # 2. CORRECCIÓN VITAL: Eliminamos el 'value='. Usar solo el 'key' evita que Streamlit borre lo que tecleas
                c_search1.text_input(
                    "ID de Empleado / Personnel ID:", 
                    key="texto_busqueda_empleado",
                    autocomplete="off"
                )
                btn_buscar = c_search2.form_submit_button("🔍 Buscar Historial", use_container_width=True)
    
            # 3. Solo cuando se presiona el botón, actualizamos a quién vamos a consultar
            if btn_buscar:
                st.session_state.empleado_consultado = st.session_state.texto_busqueda_empleado.strip()
                
            # 4. Si tenemos un empleado fijado en memoria, procesamos y mostramos todo
            if st.session_state.empleado_consultado:
                
                with st.spinner(f"Consultando expediente para el ID {st.session_state.empleado_consultado}..."):
                    try:
                        # Consulta directa y selectiva a Supabase para optimizar rendimiento
                        resp_individual = supabase.table("entrenamientos_esd")\
                                                  .select("fecha_entrenamiento, nombre_empleado, calificacion_total, archivo_origen, detalle_respuestas")\
                                                  .eq("num_empleado", st.session_state.empleado_consultado)\
                                                  .order("fecha_entrenamiento", desc=True)\
                                                  .execute()
                        
                        if resp_individual.data:
                            df_individual = pd.DataFrame(resp_individual.data)
                            df_individual = df_individual.drop_duplicates(subset=['fecha_entrenamiento'], keep='first')
                            df_individual['fecha_entrenamiento'] = pd.to_datetime(df_individual['fecha_entrenamiento']).dt.strftime('%d-%b-%Y %H:%M')
                            
                            nombre_detectado = df_individual.iloc[0]['nombre_empleado']
                            
                            # --- CONSULTA DIRECTA Y BLINDADA A LA BASE DE DATOS MAESTRA ---
                            puesto_detectado = "N/D"
                            ingreso_detectado = "N/D"
                            
                            try:
                                resp_ficha = supabase.table("empleados_batas").select("departamento, fecha_ingreso").eq("num_empleado", st.session_state.empleado_consultado).execute()
                                
                                if resp_ficha.data:
                                    ficha_usuario = resp_ficha.data[0]
                                    
                                    p_val = ficha_usuario.get('departamento')
                                    if pd.notna(p_val) and str(p_val).strip().lower() not in ['none', 'nan', 'null', '', 'n/d']:
                                        puesto_detectado = str(p_val).strip()
                                        
                                    f_val = ficha_usuario.get('fecha_ingreso')
                                    if pd.notna(f_val) and str(f_val).strip().lower() not in ['none', 'nan', 'null', '', 'n/d']:
                                        ingreso_detectado = str(f_val).strip()[:10]
                            except:
                                pass
                            # ------------------------------------------------------------------
                            
                            st.markdown(f"##### 📋 Ficha de Identificación de Personal")
                            c_emp1, c_emp2, c_emp3 = st.columns(3)
                            c_emp1.metric("Empleado", nombre_detectado)
                            c_emp2.metric("Puesto", puesto_detectado)
                            c_emp3.metric("Fecha de Ingreso", ingreso_detectado)
                            st.write("")
                            
                            # Recalcular la nota exacta al vuelo para registros históricos
                            def calcular_nota_real(detalle):
                                if isinstance(detalle, dict) and len(detalle) > 0:
                                    total = len(detalle)
                                    aciertos = sum([1.0 for v in detalle.values() if float(v) > 0])
                                    return round((aciertos / total) * 10.0, 2)
                                return 0.0
                                
                            df_individual['Calificación (Base 10)'] = df_individual['detalle_respuestas'].apply(calcular_nota_real)
                            
                            # Preparar DataFrame estructurado
                            df_tabla_individual = df_individual[['fecha_entrenamiento', 'Calificación (Base 10)', 'archivo_origen']].copy()
                            df_tabla_individual.columns = ['Fecha de Aplicación', 'Calificación (Base 10)', 'Reporte de Origen']

                            # Definimos el estilo condicional: Rojo para reprobados (<= 7.0), verde para aprobados
                            def estilar_calificaciones(val):
                                try:
                                    v = float(val)
                                    if v <= 7.0:
                                        return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
                                    else:
                                        return 'background-color: #e2f0d9; color: #385723;'
                                except:
                                    return ''
    
                            # Aplicamos el mapeo de color
                            df_estilado = df_tabla_individual.style.map(estilar_calificaciones, subset=['Calificación (Base 10)'])
                            st.dataframe(df_estilado, use_container_width=True, hide_index=True)
    
                            # --- DESGLOSE INTERACTIVO DE REACTIVOS POR INTENTO ---
                            st.markdown("##### 📜 Desglose de preguntas por examen")
                            st.caption("Despliega cada contenedor para revisar qué reactivos específicos contestó de forma correcta (1.0) o incorrecta (0.0) en cada fecha.")
                            
                            for idx, row in df_individual.iterrows():
                                fecha_intento = row['fecha_entrenamiento']
                                detalle_json = row.get('detalle_respuestas', {})
                                
                                # RECALCULAR NOTA EXACTA BASE 10 PARA EL ENCABEZADO DEL DESPLEGABLE
                                if isinstance(detalle_json, dict) and len(detalle_json) > 0:
                                    total_r = len(detalle_json)
                                    aciertos_r = sum([1.0 for v in detalle_json.values() if float(v) > 0])
                                    nota_intento = round((aciertos_r / total_r) * 10.0, 2)
                                else:
                                    try:
                                        nota_intento = min(float(row['calificacion_total']), 10.0)
                                    except:
                                        nota_intento = 0.0
                                
                                # Determinar el ícono del semáforo según la nota real recalculated
                                icono_intento = "🟢" if nota_intento > 7.0 else "🔴"
                                
                                with st.expander(f"{icono_intento} Evaluación del {fecha_intento} — Calificación Real: {nota_intento} / 10.0"):
                                    if isinstance(detalle_json, dict) and len(detalle_json) > 0:
                                        # Convertir el JSON a un formato de lista limpio para el usuario
                                        lista_reactivos = []
                                        for preg, puntaje in detalle_json.items():
                                            limpio_preg = preg.replace('Puntos: ', '', 1).strip()
                                            lista_reactivos.append({
                                                "Reactivo Evaluado": limpio_preg,
                                                "Puntaje Obtenido": f"✔️ Correcta (1.0)" if float(puntaje) > 0 else "❌ Incorrecta (0.0)"
                                            })
                                        
                                        df_reactivos = pd.DataFrame(lista_reactivos)
                                        st.dataframe(df_reactivos, use_container_width=True, hide_index=True)
                                    else:
                                        st.info("Este registro histórico no cuenta con el desglose detallado de reactivos en formato JSON.")
                        else:
                            st.warning(f"🔍 No se localizaron registros de capacitación para el número de empleado: **{st.session_state.empleado_consultado}**.")
                            
                    except Exception as e:
                        st.error(f"Ocurrió un error al consultar el registro en la base de datos: {e}")

    # --- PESTAÑA 2: CARGAR ARCHIVOS HISTÓRICOS (FORMS) ---
    with tab_historico:
        st.markdown("#### 📥 Importar Excel/CSV Histórico (Google Forms / MS Forms)")
        st.write("Sube tus archivos antiguos. El sistema detectará automáticamente el Número de Empleado, Calificación Total y las respuestas individuales evaluando las columnas que dicen 'Puntos: ...'")
        
        archivos_hist = st.file_uploader("Seleccionar archivos históricos", type=["csv", "xlsx"], accept_multiple_files=True, key="up_hist")
        
        if archivos_hist:
            for archivo in archivos_hist:
                with st.expander(f"⚙️ Procesando: {archivo.name}", expanded=True):
                    try:
                        if archivo.name.endswith('.csv'):
                            df_raw = pd.read_csv(archivo)
                        else:
                            df_raw = pd.read_excel(archivo)
                            
                        # Detectar columnas clave independientemente de variaciones minúsculas/mayúsculas
                        cols = df_raw.columns
                        col_num = next((c for c in cols if 'número de empleado' in str(c).lower() or 'numero de empleado' in str(c).lower()), None)
                        col_nom = next((c for c in cols if 'nombre' in str(c).lower() and 'completo' in str(c).lower()), None)
                        if not col_nom:
                            col_nom = next((c for c in cols if str(c).lower() == 'nombre'), None)
                        
                        col_calif = next((c for c in cols if 'total de puntos' in str(c).lower()), None)
                        col_fecha = next((c for c in cols if 'hora de finalización' in str(c).lower() or 'fecha de aplicación' in str(c).lower()), None)
                        
                        if not col_num or not col_calif:
                            st.error(f"❌ No se detectó la columna 'Número de empleado' o 'Total de puntos' en {archivo.name}.")
                        else:
                            # Encontrar todas las columnas que representan puntaje de una pregunta
                            cols_preguntas = [c for c in cols if str(c).strip().startswith('Puntos:')]
                            
                            df_clean = df_raw.dropna(subset=[col_num]).copy()
                            df_clean[col_num] = df_clean[col_num].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            
                            st.success(f"✅ Se detectaron {len(df_clean)} registros y {len(cols_preguntas)} preguntas evaluables.")
                            
                            if st.button(f"🚀 Guardar datos de {archivo.name} en la nube", key=f"btn_{archivo.name}"):
                                with st.spinner("Procesando certificaciones y calculando vigencias anuales..."):
                                    
                                    # --- NUEVO: OBTENER REGISTROS EXISTENTES PARA EVITAR DUPLICADOS ---
                                    try:
                                        resp_ex = supabase.table("entrenamientos_esd").select("num_empleado, fecha_entrenamiento").execute()
                                        set_existentes = set()
                                        for x in resp_ex.data:
                                            emp_db = str(x.get('num_empleado')).strip()
                                            fecha_db = str(x.get('fecha_entrenamiento'))[:10]
                                            set_existentes.add(f"{emp_db}|{fecha_db}")
                                    except:
                                        set_existentes = set()
                                    
                                    # --- NUEVO: ELIMINAR DUPLICADOS DENTRO DEL PROPIO EXCEL ---
                                    if col_fecha:
                                        df_clean = df_clean.drop_duplicates(subset=[col_num, col_fecha], keep='first')

                                    lote_insercion = []
                                    registros_omitidos = 0
                                    
                                    for _, row in df_clean.iterrows():
                                        emp_id = str(row[col_num]).strip()
                                        nombre_emp = str(row.get(col_nom, "N/D"))[:100]
                                        
                                        # Parsear fecha de la evaluación
                                        fecha_raw = row.get(col_fecha, datetime.now())
                                        try:
                                            fecha_dt = pd.to_datetime(fecha_raw)
                                            fecha_val_str = fecha_dt.strftime('%Y-%m-%d')
                                            fecha_proximo_str = (fecha_dt + relativedelta(years=1)).strftime('%Y-%m-%d')
                                        except:
                                            fecha_dt = datetime.now()
                                            fecha_val_str = fecha_dt.strftime('%Y-%m-%d')
                                            fecha_proximo_str = (fecha_dt + relativedelta(years=1)).strftime('%Y-%m-%d')
                                            
                                        # --- NUEVO: FILTRO ANTI-DUPLICADOS ---
                                        llave_unica = f"{emp_id}|{fecha_val_str}"
                                        if llave_unica in set_existentes:
                                            registros_omitidos += 1
                                            continue # Si ya existe, nos saltamos a la siguiente fila
                                        
                                        # (AQUÍ CONTINÚA LA LÓGICA DE DICCIONARIO QUE YA TENÍAS)
                                        # Declaramos la lista negra FUERA del for para mayor velocidad
                                        palabras_filtro = [
                                            'nombre', 'puesto', 'empleado', 'fecha', 'exámen', 'examen',
                                            'qué te pareció', 'que te parecio', 'qué le mejorarías', 'que le mejorarias',
                                            'desempeño del capacitador', 'desempeño del', 'capacitador', 'instructor', 'curso',
                                            'comentarios', 'sugerencias', 'evaluación', 
                                            'evaluacion del', 'entrenador', 'entrenamiento', 
                                            'instalaciones', 'recomendarías', 'recomendar', 
                                            'satisfacción', 'material didáctico', 'rh', 
                                            'recursos humanos', 'utilidad', 'fomento', 'trabajo', 
                                            'conocimientos', 'cambiarías', 'presentaciones', 'califica'
                                        ]

                                        detalle = {}
                                        for cp in cols_preguntas:
                                            if any(x in cp.lower() for x in palabras_filtro):
                                                continue 
                                                
                                            val_raw = row.get(cp)
                                            if pd.isna(val_raw) or str(val_raw).strip() == '':
                                                continue
                                                
                                            try:
                                                detalle[cp] = float(val_raw)
                                            except:
                                                pass 
                                        
                                        total_reactivos = len(detalle)
                                        if total_reactivos > 0:
                                            aciertos_totales = sum([1.0 for v in detalle.values() if float(v) > 0])
                                            calif_total = round((aciertos_totales / total_reactivos) * 10.0, 2)
                                        else:
                                            calif_total = 0.0
                                            
                                        # 1. Añadir al lote del historial de exámenes
                                        lote_insercion.append({
                                            "num_empleado": emp_id,
                                            "nombre_empleado": nombre_emp,
                                            "fecha_entrenamiento": fecha_dt.isoformat(),
                                            "calificacion_total": calif_total,
                                            "detalle_respuestas": detalle,
                                            "archivo_origen": archivo.name
                                        })
                                        
                                        # 2. Actualizar la ficha maestra del empleado
                                        try:
                                            supabase.table("empleados_batas").update({
                                                "fecha_ultimo_entrenamiento": fecha_val_str,
                                                "fecha_proximo_entrenamiento": fecha_proximo_str
                                            }).eq("num_empleado", emp_id).execute()
                                        except:
                                            pass

                                    # 3. Inserción masiva del historial
                                    if lote_insercion:
                                        for i in range(0, len(lote_insercion), 300):
                                            supabase.table("entrenamientos_esd").insert(lote_insercion[i:i+300]).execute()
                                        
                                        st.success(f"🎉 ¡{len(lote_insercion)} exámenes archivados! Las fechas de reentrenamiento han sido calculadas.")
                                        if registros_omitidos > 0:
                                            st.info(f"💡 Se omitieron {registros_omitidos} registros que ya existían previamente en la base de datos.")
                                        st.cache_data.clear()
                                    elif registros_omitidos > 0:
                                        st.warning(f"No se agregaron datos nuevos. Se omitieron {registros_omitidos} registros que ya existían.")
                    except Exception as e:
                        st.error(f"Error procesando {archivo.name}: {e}")

    # --- PESTAÑA 3: ACTUALIZACIÓN SEMANAL ---
    with tab_semanal:
        st.markdown("#### 🔄 Cargar Formato Semanal de Inducción")
        st.write("Sube el archivo semanal. El sistema filtrará automáticamente los registros de **'ESD - Teórico'** y validará la columna **'Nombre Completo'**.")

        archivo_sem = st.file_uploader("Subir archivo semanal (Inducción)", type=["csv", "xlsx"], key="up_sem")

        if archivo_sem:
            with st.expander(f"⚙️ Procesando: {archivo_sem.name}", expanded=True):
                try:
                    # Leer archivo sin procesar
                    if archivo_sem.name.endswith('.csv'):
                        df_raw = pd.read_csv(archivo_sem)
                    else:
                        df_raw = pd.read_excel(archivo_sem)

                    cols = [str(c).strip() for c in df_raw.columns]
                    df_raw.columns = cols
                    
                    # 1. Búsqueda exacta y estricta de las columnas requeridas
                    col_examen = next((c for c in cols if 'exámen va a presentar' in c.lower() or 'examen va a presentar' in c.lower()), None)
                    col_num = next((c for c in cols if 'número de empleado' in c.lower() or 'numero de empleado' in c.lower()), None)
                    col_nom = 'Nombre Completo' # Forzado literal según requerimiento técnico
                    col_calif = next((c for c in cols if 'total de puntos' in c.lower()), None)
                    col_fecha = next((c for c in cols if 'hora de finalización' in c.lower() or 'fecha que se realiza' in c.lower()), None)

                    if col_nom not in cols:
                        st.error(f"❌ No se encontró la columna exacta '{col_nom}' en el archivo. Columnas disponibles: {', '.join(cols)}")
                    elif not col_examen or not col_num or not col_calif:
                        st.error("❌ No se encontraron las columnas de control ('¿Qué exámen va a presentar?', 'Número de Empleado' o 'Total de puntos').")
                    else:
                        total_raw = len(df_raw)

                        # 2. Filtrar únicamente los exámenes de la materia de interés
                        df_esd = df_raw[df_raw[col_examen].astype(str).str.contains('ESD', case=False, na=False)].copy()
                        total_esd = len(df_esd)

                        # 3. Limpieza y segmentación de IDs de empleados
                        df_esd['num_emp_str'] = df_esd[col_num].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                        mask_sin_id = df_esd['num_emp_str'].isin(['nan', '', 'None', 'N/A', '0']) | df_esd[col_num].isna()
                        
                        df_sin_id = df_esd[mask_sin_id]
                        df_clean = df_esd[~mask_sin_id]

                        st.success(f"📊 **Resumen del archivo:**\n- Total de exámenes en el reporte: **{total_raw}**\n- Exámenes de ESD detectados: **{total_esd}**\n- Listos para guardar automáticamente (Con número de empleado): **{len(df_clean)}**")

                        # 4. Mesa de ayuda interactiva para registros sin ID asignado aún
                        if not df_sin_id.empty:
                            st.warning(f"⚠️ **Atención:** Se detectaron **{len(df_sin_id)}** exámenes de ESD sin Número de Empleado. Se muestran a continuación para su seguimiento manual:")
                            
                            # Sanitización del nombre para visualización en la tabla de advertencias
                            df_sin_id_show = df_sin_id.copy()
                            df_sin_id_show[col_nom] = df_sin_id_show[col_nom].apply(lambda x: "Sin Nombre Registrado" if pd.isna(x) or str(x).strip().lower() == 'nan' else str(x).strip())
                            
                            df_mostrar_sin_id = df_sin_id_show[[col_fecha, col_nom, col_calif, col_examen]].copy()
                            df_mostrar_sin_id.columns = ['Fecha / Hora', 'Nombre en Formulario', 'Calificación', 'Examen']
                            st.dataframe(df_mostrar_sin_id, width="stretch", hide_index=True)

                        # 5. Procesamiento transaccional seguro hacia Supabase
                        if not df_clean.empty:
                            cols_preguntas = [c for c in cols if str(c).strip().startswith('Puntos:')]

                            if st.button("🚀 Procesar y Guardar Exámenes Semanales", key="btn_semanal_guardar", type="primary"):
                                with st.spinner("Registrando calificaciones y asegurando datos..."):
                                    
                                    # --- 1. OBTENER REGISTROS EXISTENTES PARA EVITAR DUPLICADOS ---
                                    try:
                                        # Traemos solo los datos clave para que sea ultra rápido
                                        resp_existentes = supabase.table("entrenamientos_esd").select("num_empleado, fecha_entrenamiento").execute()
                                        
                                        # Creamos un "Set" (conjunto) con la llave "NUM_EMPLEADO|YYYY-MM-DD"
                                        # Los Sets en Python son increíblemente rápidos para buscar si algo ya existe
                                        set_existentes = set()
                                        for x in resp_existentes.data:
                                            emp_db = str(x.get('num_empleado')).strip()
                                            fecha_db = str(x.get('fecha_entrenamiento'))[:10] # Solo YYYY-MM-DD
                                            set_existentes.add(f"{emp_db}|{fecha_db}")
                                    except Exception as e:
                                        set_existentes = set()
                                        st.warning(f"No se pudo cargar el historial para validar duplicados: {e}")

                                    lote_insercion = []
                                    registros_omitidos = 0

                                    for _, row in df_clean.iterrows():
                                        emp_id = str(row['num_emp_str'])
                                        
                                        # Determinar fechas primero para poder validar si ya existe
                                        fecha_raw = row.get(col_fecha, datetime.now())
                                        try:
                                            fecha_dt = pd.to_datetime(fecha_raw)
                                            fecha_val_str = fecha_dt.strftime('%Y-%m-%d')
                                            fecha_proximo_str = (fecha_dt + relativedelta(years=1)).strftime('%Y-%m-%d')
                                        except:
                                            fecha_dt = datetime.now()
                                            fecha_val_str = fecha_dt.strftime('%Y-%m-%d')
                                            fecha_proximo_str = (fecha_dt + relativedelta(years=1)).strftime('%Y-%m-%d')

                                        # --- 2. FILTRO ANTI-DUPLICADOS ---
                                        llave_unica = f"{emp_id}|{fecha_val_str}"
                                        if llave_unica in set_existentes:
                                            registros_omitidos += 1
                                            continue # Saltamos este registro porque ya está en la base de datos
                                            
                                        # A PARTIR DE AQUÍ SOLO LLEGAN LOS REGISTROS VERDADERAMENTE NUEVOS

                                        # BLINDAJE CONTRA NaN EN EL NOMBRE
                                        raw_nombre = row.get(col_nom)
                                        if pd.isna(raw_nombre) or str(raw_nombre).strip().lower() == 'nan' or not str(raw_nombre).strip():
                                            nombre_emp = "Personal en Inducción (Nombre Vacío)"
                                        else:
                                            nombre_emp = str(raw_nombre).strip()[:100]

                                        # MAPEADO DE PUNTAJES CON FILTRO DE RAMIFICACIÓN Y LISTA NEGRA
                                        detalle = {}
                                        
                                        # Declaramos la lista negra FUERA del for para mayor velocidad
                                        palabras_filtro = [
                                            'nombre', 'puesto', 'empleado', 'fecha', 'exámen', 'examen',
                                            'qué te pareció', 'que te parecio', 'qué le mejorarías', 'que le mejorarias',
                                            'desempeño del capacitador', 'desempeño del', 'capacitador', 'instructor', 'curso',
                                            'comentarios', 'sugerencias', 'evaluación', 
                                            'evaluacion del', 'entrenador', 'entrenamiento', 
                                            'instalaciones', 'recomendarías', 'recomendar', 
                                            'satisfacción', 'material didáctico', 'rh', 
                                            'recursos humanos', 'utilidad', 'fomento', 'trabajo', 
                                            'conocimientos', 'cambiarías', 'presentaciones', 'califica'
                                        ]

                                        for cp in cols_preguntas:
                                            # 1. FILTRO DE LISTA NEGRA: Si la pregunta contiene alguna palabra de RH o metadatos, la ignoramos.
                                            if any(x in cp.lower() for x in palabras_filtro):
                                                continue 
                                                
                                            # 2. FILTRO DE RAMIFICACIÓN (Evitar 0s fantasmas de otras materias)
                                            col_respuesta_texto = cp.replace("Puntos: ", "", 1).strip()
                                            if col_respuesta_texto in df_raw.columns:
                                                respuesta = row.get(col_respuesta_texto)
                                                if pd.isna(respuesta) or str(respuesta).strip() == '':
                                                    continue # Si no contestó nada de texto, nunca vio la pregunta. La ignoramos.

                                            # 3. GUARDADO SEGURO DEL PUNTAJE
                                            val_raw = row.get(cp, 0)
                                            try:
                                                val_num = float(val_raw)
                                                val_puntos = 0.0 if pd.isna(val_num) else val_num
                                            except:
                                                val_puntos = 0.0
                                                
                                            detalle[cp] = val_puntos

                                        # NUEVA LÓGICA: Ignoramos el total crudo del Excel.
                                        # Calculamos la calificación exacta (Base 10) según la cantidad real de reactivos extraídos.
                                        total_reactivos = len(detalle)
                                        if total_reactivos > 0:
                                            # Sumamos 1.0 por cada respuesta que tenga un valor mayor a 0
                                            aciertos_totales = sum([1.0 for v in detalle.values() if float(v) > 0])
                                            # Obtenemos proporción y multiplicamos por 10 (con 2 decimales)
                                            calif_total = round((aciertos_totales / total_reactivos) * 10.0, 2)
                                        else:
                                            calif_total = 0.0

                                        # Estructurar objeto para la bitácora histórica
                                        lote_insercion.append({
                                            "num_empleado": emp_id,
                                            "nombre_empleado": nombre_emp,
                                            "fecha_entrenamiento": fecha_dt.isoformat(),
                                            "calificacion_total": calif_total,
                                            "detalle_respuestas": detalle,
                                            "archivo_origen": archivo_sem.name
                                        })

                                        # Actualizar vigencia en el padrón maestro del personal
                                        try:
                                            supabase.table("empleados_batas").update({
                                                "fecha_ultimo_entrenamiento": fecha_val_str,
                                                "fecha_proximo_entrenamiento": fecha_proximo_str
                                            }).eq("num_empleado", emp_id).execute()
                                        except:
                                            pass

                                    # C. Inserción masiva en Supabase
                                    if lote_insercion:
                                        for i in range(0, len(lote_insercion), 300):
                                            supabase.table("entrenamientos_esd").insert(lote_insercion[i:i+300]).execute()
                                            
                                        st.success(f"🎉 ¡Sincronización exitosa! Se guardaron **{len(lote_insercion)}** exámenes NUEVOS.")
                                        if registros_omitidos > 0:
                                            st.info(f"💡 Se omitieron **{registros_omitidos}** registros que ya existían previamente en la base de datos.")
                                            
                                        st.cache_data.clear()
                                        time.sleep(2.5)
                                        st.rerun()
                                    else:
                                        st.warning(f"No se encontraron exámenes nuevos. Se omitieron {registros_omitidos} registros duplicados/ya existentes.")
                except Exception as e:
                    st.error(f"Error procesando el archivo semanal: {e}")
# --- PESTAÑA 4: AUDITORÍA CRONOLÓGICA (BRECHAS Y REENTRENAMIENTOS) ---
    with tab_auditoria:
        st.markdown("#### 🕵️ Auditoría de Cumplimiento (Gaps y Reentrenamientos)")
        st.info("Esta herramienta recorre la línea del tiempo de cada colaborador y detecta dos anomalías críticas: **1)** Brechas mayores a 365 días entre certificaciones. **2)** Reentrenamientos que tardaron **más de 2 días** tras una reprobación (< 8.0).")

        if "anomalias_entrenamiento" not in st.session_state:
            st.session_state.anomalias_entrenamiento = None

        if st.button("🔍 Escanear Historial Completo", type="secondary", use_container_width=True):
            with st.spinner("Cruzando padrón de empleados y analizando líneas del tiempo..."):
                try:
                    # 1. Traer fechas de ingreso desde el padrón de empleados
                    # Usamos .select("*") temporalmente para ver qué columnas existen realmente
                    resp_emp = supabase.table("empleados_batas").select("num_empleado, fecha_ingreso").execute()
                    df_emp = pd.DataFrame(resp_emp.data)
                    
                    dict_ingreso = {}
                    if not df_emp.empty:
                        # Limpieza estricta de num_empleado para asegurar coincidencia
                        df_emp['num_empleado'] = df_emp['num_empleado'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                        
                        # Si la columna se llama diferente en SQL (ej: 'fecha ingreso' con espacio), esto fallará.
                        # Asegúrate que el nombre aquí coincida EXACTAMENTE con tu tabla en Supabase:
                        if 'fecha_ingreso' in df_emp.columns:
                            dict_ingreso = dict(zip(df_emp['num_empleado'], df_emp['fecha_ingreso']))
                        else:
                            st.error(f"⚠️ Error: No encontré la columna 'fecha_ingreso' en 'empleados_batas'. Columnas detectadas: {list(df_emp.columns)}")
                            
                    # 2. Traer todo el historial de exámenes ordenado por fecha
                    resp_train = supabase.table("entrenamientos_esd").select("id, num_empleado, nombre_empleado, fecha_entrenamiento, calificacion_total").order("fecha_entrenamiento").execute()
                    df_train = pd.DataFrame(resp_train.data)
                    
                    anomalias_encontradas = []
                    
                    if not df_train.empty:
                        # Limpiar y asegurar el formato de fechas
                        df_train['fecha_dt'] = pd.to_datetime(df_train['fecha_entrenamiento'], errors='coerce')
                        df_train['num_empleado'] = df_train['num_empleado'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                        df_train = df_train.dropna(subset=['fecha_dt'])
                        
                        # Ordenar primariamente por empleado y secundariamente por fecha (cronología estricta)
                        df_train = df_train.sort_values(by=['num_empleado', 'fecha_dt'])
                        
                        # 3. Agrupar por empleado y recorrer su línea del tiempo
                        for emp, group in df_train.groupby('num_empleado'):
                            group = group.reset_index(drop=True)
                            
                            # Obtener fecha de ingreso del diccionario
                            f_ingreso_raw = dict_ingreso.get(emp)
                            f_ingreso_str = str(f_ingreso_raw)[:10] if pd.notna(f_ingreso_raw) and f_ingreso_raw else "N/D"
                            
                            for i in range(len(group)):
                                row_actual = group.iloc[i]
                                
                                # Solo podemos comparar si hay un examen previo (i > 0)
                                if i > 0:
                                    row_prev = group.iloc[i-1]
                                    dias_transcurridos = (row_actual['fecha_dt'].date() - row_prev['fecha_dt'].date()).days
                                    
                                    # Determinar si el examen previo fue su primera evaluación
                                    es_primer_examen = "Sí" if (i - 1) == 0 else "No"
                                    
                                    # Extraemos notas de forma segura
                                    try: nota_previa = float(row_prev['calificacion_total'])
                                    except: nota_previa = 10.0
                                    
                                    try: nota_siguiente = float(row_actual['calificacion_total'])
                                    except: nota_siguiente = 0.0
                                    
                                    # Base del registro anómalo
                                    registro_base = {
                                        "id_bd_actual": row_actual['id'],
                                        "id_bd_previo": row_prev['id'],
                                        "No. Empleado": emp,
                                        "Nombre": row_actual['nombre_empleado'],
                                        "Fecha Ingreso": f_ingreso_str,
                                        "Es Primer Examen?": es_primer_examen,
                                        "Fecha Examen Previo": row_prev['fecha_dt'].strftime('%Y-%m-%d'),
                                        "Nueva Fecha Previa": row_prev['fecha_dt'].strftime('%Y-%m-%d'), # Editable
                                        "Nota Previa": nota_previa,
                                        "Días Gap": dias_transcurridos,
                                        "Fecha Siguiente Examen": row_actual['fecha_dt'].strftime('%Y-%m-%d'),
                                        "Nueva Fecha (Correcta)": row_actual['fecha_dt'].strftime('%Y-%m-%d'), # Editable
                                        "Nota Siguiente Examen": nota_siguiente
                                    }

                                    # --- REGLA A: REENTRENAMIENTO TRAS FALLA ---
                                    if nota_previa < 8.0:
                                        if dias_transcurridos > 2:
                                            reg_falla = registro_base.copy()
                                            reg_falla["Motivo de Alerta"] = "Reentrenamiento Tardío"
                                            anomalias_encontradas.append(reg_falla)
                                            continue 
                                            
                                    # --- REGLA B: BRECHA DE CERTIFICACIÓN ANUAL ---
                                    if dias_transcurridos > 365:
                                        reg_brecha = registro_base.copy()
                                        reg_brecha["Motivo de Alerta"] = "Brecha Anual Excedida"
                                        anomalias_encontradas.append(reg_brecha)

                    st.session_state.anomalias_entrenamiento = anomalias_encontradas

                except Exception as e:
                    st.error(f"Error al analizar el historial: {e}")

        # --- EDITOR Y GUARDADO ---
        if st.session_state.anomalias_entrenamiento is not None:
            lista_anomalias = st.session_state.anomalias_entrenamiento
            st.divider()
            
            if len(lista_anomalias) == 0:
                st.success("✨ ¡Cumplimiento cronológico perfecto!")
                st.session_state.anomalias_entrenamiento = None
            else:
                st.warning(f"⚠️ **Atención: Se encontraron {len(lista_anomalias)} registros anómalos.**")
                
                # Convertir lista a DataFrame
                df_anomalias = pd.DataFrame(lista_anomalias)
                
                # Lista maestra de todas las columnas esperadas
                columnas_maestras = [
                    "id_bd_actual", "id_bd_previo", "No. Empleado", "Nombre", "Fecha Ingreso", 
                    "Motivo de Alerta", "Es Primer Examen?", "Fecha Examen Previo", 
                    "Nota Previa", "Días Gap", "Fecha Siguiente Examen", "Nota Siguiente Examen"
                ]

                # Asegurar que todas existan
                for col in columnas_maestras:
                    if col not in df_anomalias.columns:
                        df_anomalias[col] = None

                # Crear las columnas de edición si no existen
                df_anomalias['Nueva Fecha Previa'] = pd.to_datetime(df_anomalias['Fecha Examen Previo'], errors='coerce')
                df_anomalias['Nueva Fecha (Correcta)'] = pd.to_datetime(df_anomalias['Fecha Siguiente Examen'], errors='coerce')

                # Reorganizar columnas
                cols_ordenadas = [
                    "id_bd_actual", "id_bd_previo", "No. Empleado", "Nombre", "Fecha Ingreso", 
                    "Motivo de Alerta", "Es Primer Examen?", "Fecha Examen Previo", "Nueva Fecha Previa", 
                    "Nota Previa", "Días Gap", "Fecha Siguiente Examen", "Nueva Fecha (Correcta)", "Nota Siguiente Examen"
                ]
                df_anomalias = df_anomalias[[c for c in cols_ordenadas if c in df_anomalias.columns]]

                editor_train = st.data_editor(
                    df_anomalias,
                    column_config={
                        "id_bd_actual": None, "id_bd_previo": None,
                        "No. Empleado": st.column_config.TextColumn("No. Empleado", disabled=True),
                        "Nombre": st.column_config.TextColumn("Nombre", disabled=True),
                        "Fecha Ingreso": st.column_config.TextColumn("Ingreso", disabled=True),
                        "Motivo de Alerta": st.column_config.TextColumn("Motivo", disabled=True),
                        "Es Primer Examen?": st.column_config.TextColumn("1er Examen?", disabled=True),
                        "Fecha Examen Previo": st.column_config.TextColumn("Examen Previo", disabled=True),
                        "Nueva Fecha Previa": st.column_config.DateColumn("Edita Fecha Previa"),
                        "Nota Previa": st.column_config.NumberColumn("Nota Previa", disabled=True),
                        "Días Gap": st.column_config.NumberColumn("Días Gap", disabled=True),
                        "Fecha Siguiente Examen": st.column_config.TextColumn("Sig. Examen", disabled=True),
                        "Nueva Fecha (Correcta)": st.column_config.DateColumn("Edita Fecha Sig."),
                        "Nota Siguiente Examen": st.column_config.NumberColumn("Nota Sig.", disabled=True),
                    },
                    hide_index=True,
                    width='stretch',
                    key="editor_train_audit"
                )
                
                if st.button("💾 Guardar Correcciones", type="primary", use_container_width=True):
                    cambios = st.session_state.editor_train_audit.get("edited_rows", {})
                    if not cambios:
                        st.info("No hay cambios pendientes.")
                    else:
                        with st.spinner("Sincronizando SQL..."):
                            errores = 0
                            for idx_str, edits in cambios.items():
                                idx = int(idx_str)
                                fila = df_anomalias.iloc[idx]
                                
                                # Actualizar fecha del examen actual
                                if "Nueva Fecha (Correcta)" in edits:
                                    try:
                                        supabase.table("entrenamientos_esd").update({"fecha_entrenamiento": str(edits["Nueva Fecha (Correcta)"]) + "T00:00:00"}).eq("id", fila['id_bd_actual']).execute()
                                    except: errores += 1
                                # Actualizar fecha del examen previo
                                if "Nueva Fecha Previa" in edits:
                                    try:
                                        supabase.table("entrenamientos_esd").update({"fecha_entrenamiento": str(edits["Nueva Fecha Previa"]) + "T00:00:00"}).eq("id", fila['id_bd_previo']).execute()
                                    except: errores += 1
                            
                            if errores == 0:
                                st.success("✅ ¡Registros actualizados!")
                                st.session_state.anomalias_entrenamiento = None
                                st.rerun()
