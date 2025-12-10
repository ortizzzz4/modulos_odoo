# -*- coding: utf-8 -*-
"""
Módulo Demo - Sistema de Facturación Electrónica El Salvador Desde el modulo de POS
Autor:ortiz
Descripción: Demostración de integración con API de facturación electrónica
             basado en experiencia real con sistema del MH de El Salvador 
"""

import json
import uuid
import requests
from datetime import datetime
from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Campos adicionales para FEL
    uuid_generation_code = fields.Char(
        string='Código de Generación', 
        readonly=True,
        copy=False,
        help='UUID único generado para el DTE'
    )
    estado_dte = fields.Selection([
        ('draft', 'Borrador'),
        ('firmado', 'Firmado'),
        ('procesado', 'Procesado'),
        ('rechazado', 'Rechazado')
    ], string='Estado DTE', default='draft', tracking=True)
    
    documento_firmado = fields.Text(
        string='Documento Firmado',
        readonly=True,
        help='Documento firmado digitalmente en formato JSON'
    )
    
    json_data = fields.Text(
        string='JSON Original',
        readonly=True,
        help='JSON del documento antes de firmar'
    )
    
    json_mh = fields.Text(
        string='Respuesta MH',
        readonly=True,
        help='Respuesta del Ministerio de Hacienda'
    )
    
    confirmacion = fields.Char(
        string='Sello de Recepción',
        readonly=True,
        help='Sello de recepción del MH'
    )
    
    # Métodos principales
    
    def _preparar_payload_dte(self):
        """
        Prepara el payload JSON para enviar al servicio de firma
        
        Returns:
            dict: Estructura completa del DTE según especificaciones MH
        """
        self.ensure_one()
        
        # Generar UUID único
        codigo_generacion = str(uuid.uuid4()).upper()
        
        # Preparar items del documento
        items = self._preparar_items_documento()
        
        # Preparar información del receptor
        receptor = self._preparar_receptor()
        
        # Preparar resumen financiero
        resumen = self._preparar_resumen()
        
        # Estructura completa del DTE
        dte_json = {
            "identificacion": {
                "version": 1,
                "ambiente": self.company_id.ambiente_dte or "00",  # 00: Pruebas, 01: Producción
                "tipoDte": "01",  # Factura
                "numeroControl": self.name,
                "codigoGeneracion": codigo_generacion,
                "tipoModelo": 1,
                "tipoOperacion": 1,
                "fecEmi": self.invoice_date.strftime('%Y-%m-%d'),
                "horEmi": datetime.now().strftime('%H:%M:%S'),
                "tipoMoneda": "USD"
            },
            "emisor": self._preparar_emisor(),
            "receptor": receptor,
            "cuerpoDocumento": items,
            "resumen": resumen,
            "extension": self._preparar_extension(),
            "apendice": self._preparar_apendice()
        }
        
        return {
            "nit": self.company_id.vat or "0000000000000",
            "activo": True,
            "passwordPri": self.company_id.password_firma_dte,
            "dteJson": dte_json
        }
    
    def _preparar_items_documento(self):
        """
        Prepara los items del documento según especificación MH
        
        Returns:
            list: Lista de items con estructura requerida
        """
        items = []
        num_item = 1
        
        for line in self.invoice_line_ids:
            if line.display_type in ('line_note', 'line_section'):
                continue
                
            precio_unitario = round(line.price_unit * 1.13, 4)  # Precio con IVA
            venta_gravada = round(line.price_subtotal * 1.13, 4)
            descuento = round(precio_unitario * line.quantity * (line.discount / 100.0), 4)
            iva_item = round(line.price_subtotal * 0.13, 4)
            
            item = {
                "numItem": num_item,
                "tipoItem": int(line.product_id.tipo_item_dte or 1),
                "numeroDocumento": None,
                "cantidad": line.quantity,
                "codigo": line.product_id.default_code[:25] if line.product_id.default_code else None,
                "codTributo": None,
                "uniMedida": 59,  # Unidad
                "descripcion": line.name[:1000],
                "precioUni": precio_unitario,
                "montoDescu": descuento,
                "ventaNoSuj": 0.00,
                "ventaExenta": 0.00,
                "ventaGravada": venta_gravada,
                "tributos": None,
                "psv": line.price_unit,
                "noGravado": 0.00,
                "ivaItem": iva_item
            }
            items.append(item)
            num_item += 1
            
        return items
    
    def _preparar_receptor(self):
        """Prepara información del receptor/cliente"""
        partner = self.partner_id
        
        return {
            "tipoDocumento": "36",  # DUI por defecto
            "numDocumento": partner.vat or "0000000000",
            "nrc": partner.registro_comercial if hasattr(partner, 'registro_comercial') else None,
            "nombre": partner.name[:200],
            "codActividad": None,
            "descActividad": None,
            "direccion": {
                "departamento": partner.state_id.code[:2] if partner.state_id else "01",
                "municipio": "01",
                "complemento": partner.street[:200] if partner.street else "Ciudad"
            },
            "telefono": partner.phone[:25] if partner.phone else None,
            "correo": partner.email[:100] if partner.email else None
        }
    
    def _preparar_emisor(self):
        """Prepara información del emisor/empresa"""
        company = self.company_id
        
        return {
            "nit": company.vat or "0000000000000",
            "nrc": company.registro_comercial if hasattr(company, 'registro_comercial') else "000000-0",
            "nombre": company.name[:200],
            "codActividad": company.codigo_actividad if hasattr(company, 'codigo_actividad') else "10005",
            "descActividad": company.desc_actividad if hasattr(company, 'desc_actividad') else "Comercio",
            "nombreComercial": company.name[:200],
            "tipoEstablecimiento": "01",
            "direccion": {
                "departamento": "01",
                "municipio": "01",
                "complemento": company.street[:200] if company.street else "San Salvador"
            },
            "telefono": company.phone[:25] if company.phone else "0000-0000",
            "correo": company.email[:100],
            "codEstableMH": None,
            "codEstable": None,
            "codPuntoVentaMH": None,
            "codPuntoVenta": None
        }
    
    def _preparar_resumen(self):
        """Prepara el resumen financiero del documento"""
        total_gravado = round(self.amount_untaxed * 1.13, 2)
        total_iva = round(self.amount_tax, 2)
        
        return {
            "totalNoSuj": 0.00,
            "totalExenta": 0.00,
            "totalGravada": total_gravado,
            "subTotalVentas": total_gravado,
            "descuNoSuj": 0.00,
            "descuExenta": 0.00,
            "descuGravada": 0.00,
            "porcentajeDescuento": 0.00,
            "totalDescu": 0.00,
            "tributos": None,
            "subTotal": total_gravado,
            "ivaRete1": 0.00,
            "reteRenta": 0.00,
            "montoTotalOperacion": total_gravado,
            "totalNoGravado": 0.00,
            "totalPagar": self.amount_total,
            "totalLetras": self.amount_to_text,
            "totalIva": total_iva,
            "saldoFavor": 0.00,
            "condicionOperacion": 1,  # 1: Contado, 2: Crédito
            "pagos": None,
            "numPagoElectronico": None
        }
    
    def _preparar_extension(self):
        """Prepara datos de extensión del documento"""
        return {
            "nombEntrega": None,
            "docuEntrega": None,
            "nombRecibe": None,
            "docuRecibe": None,
            "observaciones": self.narration[:3000] if self.narration else None,
            "placaVehiculo": None
        }
    
    def _preparar_apendice(self):
        """Prepara información adicional en apéndice"""
        return [
            {
                "campo": "numeroInterno",
                "etiqueta": "Número Interno",
                "valor": self.payment_reference or self.name
            }
        ]
    
    def action_firmar_dte(self):
        """
        Acción para firmar el DTE mediante servicio externo
        Puede ser llamada desde botón en vista o automáticamente
        """
        self.ensure_one()
        
        if self.estado_dte != 'draft':
            raise UserError('Este documento ya ha sido procesado.')
        
        if not self.company_id.url_firmador_dte:
            raise UserError('Debe configurar la URL del servicio firmador en la empresa.')
        
        # Preparar payload
        payload = self._preparar_payload_dte()
        
        # Guardar JSON original
        self.json_data = json.dumps(payload['dteJson'], ensure_ascii=False)
        
        # Firmar documento
        url_firma = f"{self.company_id.url_firmador_dte}/firmardocumento/"
        resultado = self._enviar_a_firmar(url_firma, payload)
        
        if resultado['success']:
            self.write({
                'estado_dte': 'firmado',
                'documento_firmado': resultado['documento'],
                'uuid_generation_code': payload['dteJson']['identificacion']['codigoGeneracion']
            })
            self.message_post(body="DTE firmado correctamente", message_type="notification")
        else:
            raise ValidationError(f"Error al firmar: {resultado['message']}")
        
        return True
    
    def _enviar_a_firmar(self, url, payload):
        """
        Envía el documento al servicio de firma digital
        
        Args:
            url (str): URL del servicio firmador
            payload (dict): Datos del documento a firmar
            
        Returns:
            dict: Resultado de la operación
        """
        headers = {
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.post(
                url, 
                headers=headers, 
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            
            json_response = response.json()
            
            if json_response.get('status') == 'OK':
                return {
                    'success': True,
                    'documento': json_response.get('body'),
                    'message': 'Documento firmado correctamente'
                }
            else:
                return {
                    'success': False,
                    'message': json_response.get('body', {}).get('mensaje', 'Error desconocido')
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Tiempo de espera agotado al conectar con el servicio'
            }
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error en servicio de firma: {e}")
            return {
                'success': False,
                'message': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            _logger.error(f"Error inesperado al firmar: {e}")
            return {
                'success': False,
                'message': f'Error inesperado: {str(e)}'
            }
    
    def action_enviar_a_mh(self):
        """
        Envía el DTE firmado al Ministerio de Hacienda
        """
        self.ensure_one()
        
        if self.estado_dte != 'firmado':
            raise UserError('El documento debe estar firmado antes de enviarlo.')
        
        if not self.documento_firmado:
            raise UserError('No se encontró el documento firmado.')
        
        # Preparar payload para MH
        payload = {
            "ambiente": self.company_id.ambiente_dte or "00",
            "idEnvio": self.id,
            "version": 1,
            "tipoDte": "01",
            "documento": self.documento_firmado,
            "codigoGeneracion": self.uuid_generation_code
        }
        
        # Determinar URL según ambiente
        url_mh = self._get_url_mh()
        
        # Enviar a MH
        resultado = self._enviar_a_mh(url_mh, payload)
        
        if resultado['success']:
            self.write({
                'estado_dte': 'procesado',
                'confirmacion': resultado.get('sello'),
                'json_mh': json.dumps(resultado.get('respuesta'), ensure_ascii=False)
            })
            self.message_post(body="DTE procesado por MH correctamente", message_type="notification")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'DTE enviado y procesado correctamente',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            self.estado_dte = 'rechazado'
            raise ValidationError(f"Error del MH: {resultado['message']}")
    
    def _get_url_mh(self):
        """Retorna la URL del MH según el ambiente configurado"""
        ambiente = self.company_id.ambiente_dte or "00"
        
        urls = {
            "00": "https://apitest.dtes.mh.gob.sv/fesv/recepciondte",  # Pruebas
            "01": "https://api.dtes.mh.gob.sv/fesv/recepciondte"       # Producción
        }
        
        return urls.get(ambiente, urls["00"])
    
    def _enviar_a_mh(self, url, payload):
        """
        Envía el DTE firmado al Ministerio de Hacienda
        
        Args:
            url (str): URL del endpoint del MH
            payload (dict): Datos del documento firmado
            
        Returns:
            dict: Resultado de la operación
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.company_id.token_mh}'
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=60
            )
            
            json_response = response.json()
            
            if response.status_code == 200 and json_response.get('estado') == 'PROCESADO':
                return {
                    'success': True,
                    'sello': json_response.get('selloRecibido'),
                    'respuesta': json_response,
                    'message': 'Documento procesado correctamente'
                }
            else:
                return {
                    'success': False,
                    'message': json_response.get('descripcionMsg', 'Error desconocido'),
                    'respuesta': json_response
                }
                
        except Exception as e:
            _logger.error(f"Error al enviar a MH: {e}")
            return {
                'success': False,
                'message': f'Error de conexión con MH: {str(e)}'
            }
    
    def action_firmar_y_enviar(self):
        """
        Acción combinada: firma y envía el DTE en un solo paso
        """
        self.action_firmar_dte()
        return self.action_enviar_a_mh()