from flask import Blueprint, make_response, abort, current_app, render_template, session, jsonify
from app.models import Venta, Abono
from app.pdf.venta import generar_pdf_venta
from app.pdf.abono import generar_pdf_abono
import hashlib
import base64

public_bp = Blueprint('public', __name__, url_prefix='/public')

def generar_token_simple(id, tipo, secret_key='creditmobileapp2025'):
    """Genera token para validar acceso público a PDFs"""
    message = f"{tipo}_{id}_{secret_key}"
    return hashlib.sha256(message.encode()).hexdigest()[:20]

@public_bp.route('/venta/<int:id>/pdf/<token>')
def venta_pdf_directo(id, token):
    """Genera y muestra PDF de venta directamente sin autenticación"""
    try:
        # Verificar token
        expected_token = generar_token_simple(id, 'venta')
        if token != expected_token:
            current_app.logger.warning(f"Token inválido para venta {id}")
            abort(403)
        
        # Buscar la venta
        venta = Venta.query.get_or_404(id)
        
        # Generar el PDF
        pdf_bytes = generar_pdf_venta(venta)
        
        # Crear respuesta para visualizar en navegador
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="factura_{venta.id}.pdf"'
        response.headers['Content-Length'] = str(len(pdf_bytes))
        
        current_app.logger.info(f"PDF de venta {id} generado exitosamente")
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generando PDF de venta {id}: {str(e)}")
        abort(500, description="Error al generar el PDF de la venta")

@public_bp.route('/abono/<int:id>/pdf/<token>')
def abono_pdf_directo(id, token):
    """Genera y muestra PDF de abono directamente sin autenticación"""
    try:
        # Verificar token
        expected_token = generar_token_simple(id, 'abono')
        if token != expected_token:
            current_app.logger.warning(f"Token inválido para abono {id}")
            abort(403)
        
        # Buscar el abono
        abono = Abono.query.get_or_404(id)
        
        # Generar el PDF
        pdf_bytes = generar_pdf_abono(abono)
        
        # Crear respuesta para visualizar en navegador
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="abono_{abono.id}.pdf"'
        response.headers['Content-Length'] = str(len(pdf_bytes))
        
        current_app.logger.info(f"PDF de abono {id} generado exitosamente")
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generando PDF de abono {id}: {str(e)}")
        abort(500, description="Error al generar el PDF del abono")

@public_bp.route('/venta/<int:id>/descargar/<token>')
def venta_pdf_descarga(id, token):
    """Descarga pública de PDF de venta con token de seguridad"""
    try:
        # Verificar token
        expected_token = generar_token_simple(id, 'venta')
        if token != expected_token:
            current_app.logger.warning(f"Token inválido para venta {id}")
            abort(403)
        
        # Buscar la venta
        venta = Venta.query.get_or_404(id)
        
        # Generar el PDF
        pdf_bytes = generar_pdf_venta(venta)
        
        # Crear respuesta con headers optimizados para dispositivos móviles
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        # Forzar descarga con nombre de archivo
        response.headers['Content-Disposition'] = f'attachment; filename="factura_{venta.id}.pdf"'
        response.headers['Content-Length'] = str(len(pdf_bytes))
        # Headers para evitar caché
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        current_app.logger.info(f"PDF de venta {id} generado exitosamente")
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generando PDF de venta {id}: {str(e)}")
        abort(500, description="Error al generar el PDF de la venta")

@public_bp.route('/abono/<int:id>/descargar/<token>')
def abono_pdf_descarga(id, token):
    """Descarga pública de PDF de abono con token de seguridad"""
    try:
        # Verificar token
        expected_token = generar_token_simple(id, 'abono')
        if token != expected_token:
            current_app.logger.warning(f"Token inválido para abono {id}")
            abort(403)
        
        # Buscar el abono
        abono = Abono.query.get_or_404(id)
        
        # Generar el PDF
        pdf_bytes = generar_pdf_abono(abono)
        
        # Crear respuesta con headers optimizados para dispositivos móviles
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        # Forzar descarga con nombre de archivo
        response.headers['Content-Disposition'] = f'attachment; filename="abono_{abono.id}.pdf"'
        response.headers['Content-Length'] = str(len(pdf_bytes))
        # Headers para evitar caché
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        current_app.logger.info(f"PDF de abono {id} generado exitosamente")
        return response
    except Exception as e:
        current_app.logger.error(f"Error generando PDF de abono {id}: {str(e)}")
        abort(500, description="Error al generar el PDF del abono")

@public_bp.route('/share/<tipo>/<int:id>')
def share_page(tipo, id):
    """Página para compartir con enlaces directos"""
    try:
        # Generar token
        token = generar_token_simple(id, tipo)
        
        # Crear URLs públicas
        if tipo == 'venta':
            pdf_url = f"/public/venta/{id}/pdf/{token}"
            download_url = f"/public/venta/{id}/descargar/{token}"
            title = f"Factura de Venta #{id}"
        elif tipo == 'abono':
            pdf_url = f"/public/abono/{id}/pdf/{token}"
            download_url = f"/public/abono/{id}/descargar/{token}"
            title = f"Comprobante de Abono #{id}"
        else:
            abort(404)
        
        return render_template('public/share.html', 
                             pdf_url=pdf_url,
                             download_url=download_url,
                             title=title,
                             tipo=tipo,
                             id=id)
    except Exception as e:
        current_app.logger.error(f"Error en página de compartir: {str(e)}")
        abort(500, description="Error al cargar la página de compartir")
