# -*- coding: utf-8 -*-
"""
Tests para el módulo de Facturación Electrónica El Salvador
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from unittest.mock import patch, MagicMock
import json
import uuid


class TestAccountMoveFEL(TransactionCase):
    
    def setUp(self):
        super(TestAccountMoveFEL, self).setUp()
        
        # Crear empresa de prueba
        self.company = self.env['res.company'].create({
            'name': 'Empresa Test FEL',
            'vat': '06140000000000',
            'ambiente_dte': '00',  # Ambiente de pruebas
            'url_firmador_dte': 'https://api-test.firmador.com',
            'token_mh': 'test_token_123',
        })
        
        # Crear partner de prueba
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'vat': '0000000000',
            'email': 'cliente@test.com',
            'phone': '2222-2222',
            'street': 'Calle Test 123',
        })
        
        # Crear producto de prueba
        self.product = self.env['ref.product'].create({
            'name': 'Producto Test',
            'default_code': 'PROD001',
            'type': 'product',
            'list_price': 100.00,
            'tipo_item_dte': 1,
        })
        
        # Crear factura de prueba
        self.invoice = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2024-01-15',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2,
                'price_unit': 100.00,
            })],
        })
    
    def test_preparar_payload_dte_estructura(self):
        """Test: Verificar estructura correcta del payload DTE"""
        payload = self.invoice._preparar_payload_dte()
        
        # Verificar estructura principal
        self.assertIn('nit', payload)
        self.assertIn('dteJson', payload)
        
        dte = payload['dteJson']
        
        # Verificar secciones requeridas
        self.assertIn('identificacion', dte)
        self.assertIn('emisor', dte)
        self.assertIn('receptor', dte)
        self.assertIn('cuerpoDocumento', dte)
        self.assertIn('resumen', dte)
        
        # Verificar tipos de datos
        self.assertIsInstance(dte['cuerpoDocumento'], list)
        self.assertIsInstance(dte['resumen'], dict)
    
    def test_preparar_items_documento(self):
        """Test: Verificar preparación correcta de items"""
        items = self.invoice._preparar_items_documento()
        
        # Verificar que se generó un item
        self.assertEqual(len(items), 1)
        
        item = items[0]
        
        # Verificar campos requeridos
        self.assertEqual(item['numItem'], 1)
        self.assertEqual(item['cantidad'], 2)
        self.assertEqual(item['codigo'], 'PROD001')
        self.assertIn('descripcion', item)
        
        # Verificar cálculos
        self.assertGreater(item['precioUni'], 0)
        self.assertGreater(item['ventaGravada'], 0)
        self.assertGreater(item['ivaItem'], 0)
    
    def test_preparar_receptor(self):
        """Test: Verificar datos del receptor"""
        receptor = self.invoice._preparar_receptor()
        
        # Verificar campos obligatorios
        self.assertEqual(receptor['nombre'], 'Cliente Test')
        self.assertEqual(receptor['numDocumento'], '0000000000')
        self.assertEqual(receptor['correo'], 'cliente@test.com')
        
        # Verificar estructura de dirección
        self.assertIn('direccion', receptor)
        self.assertIn('departamento', receptor['direccion'])
        self.assertIn('municipio', receptor['direccion'])
        self.assertIn('complemento', receptor['direccion'])
    
    def test_preparar_emisor(self):
        """Test: Verificar datos del emisor"""
        emisor = self.invoice._preparar_emisor()
        
        # Verificar campos obligatorios
        self.assertEqual(emisor['nombre'], 'Empresa Test FEL')
        self.assertEqual(emisor['nit'], '06140000000000')
        self.assertIn('direccion', emisor)
        self.assertIn('correo', emisor)
    
    def test_preparar_resumen_calculos(self):
        """Test: Verificar cálculos del resumen"""
        resumen = self.invoice._preparar_resumen()
        
        # Verificar que los totales son correctos
        self.assertGreater(resumen['totalGravada'], 0)
        self.assertGreater(resumen['totalIva'], 0)
        self.assertGreater(resumen['totalPagar'], 0)
        
        # Verificar que total pagar = total gravado (sin descuentos ni retenciones)
        self.assertEqual(
            resumen['totalPagar'],
            self.invoice.amount_total
        )
        
        # Verificar campos en cero cuando no aplican
        self.assertEqual(resumen['totalNoSuj'], 0.00)
        self.assertEqual(resumen['totalExenta'], 0.00)
        self.assertEqual(resumen['totalDescu'], 0.00)
    
    def test_uuid_generation(self):
        """Test: Verificar generación de UUID único"""
        payload1 = self.invoice._preparar_payload_dte()
        payload2 = self.invoice._preparar_payload_dte()
        
        uuid1 = payload1['dteJson']['identificacion']['codigoGeneracion']
        uuid2 = payload2['dteJson']['identificacion']['codigoGeneracion']
        
        # Cada llamada debe generar un UUID diferente
        self.assertNotEqual(uuid1, uuid2)
        
        # Verificar formato de UUID
        try:
            uuid.UUID(uuid1)
            uuid_valido = True
        except ValueError:
            uuid_valido = False
        
        self.assertTrue(uuid_valido)
    
    @patch('requests.post')
    def test_enviar_a_firmar_exitoso(self, mock_post):
        """Test: Simular firma exitosa del documento"""
        # Configurar mock de respuesta exitosa
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'OK',
            'body': 'documento_firmado_base64_ejemplo'
        }
        mock_post.return_value = mock_response
        
        payload = self.invoice._preparar_payload_dte()
        url = 'https://api-test.firmador.com/firmardocumento/'
        
        resultado = self.invoice._enviar_a_firmar(url, payload)
        
        # Verificar resultado exitoso
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['documento'], 'documento_firmado_base64_ejemplo')
        
        # Verificar que se hizo la llamada correcta
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_enviar_a_firmar_error(self, mock_post):
        """Test: Simular error al firmar documento"""
        # Configurar mock de respuesta con error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'ERROR',
            'body': {'mensaje': 'Datos inválidos'}
        }
        mock_post.return_value = mock_response
        
        payload = self.invoice._preparar_payload_dte()
        url = 'https://api-test.firmador.com/firmardocumento/'
        
        resultado = self.invoice._enviar_a_firmar(url, payload)
        
        # Verificar que se manejó el error
        self.assertFalse(resultado['success'])
        self.assertIn('inválidos', resultado['message'])
    
    @patch('requests.post')
    def test_enviar_a_firmar_timeout(self, mock_post):
        """Test: Simular timeout en servicio de firma"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        payload = self.invoice._preparar_payload_dte()
        url = 'https://api-test.firmador.com/firmardocumento/'
        
        resultado = self.invoice._enviar_a_firmar(url, payload)
        
        # Verificar manejo de timeout
        self.assertFalse(resultado['success'])
        self.assertIn('Tiempo de espera', resultado['message'])
    
    def test_action_firmar_dte_sin_configuracion(self):
        """Test: Intentar firmar sin URL configurada"""
        # Limpiar configuración
        self.company.url_firmador_dte = False
        
        # Debe lanzar error
        with self.assertRaises(UserError) as context:
            self.invoice.action_firmar_dte()
        
        self.assertIn('configurar la URL', str(context.exception))
    
    def test_action_firmar_dte_documento_ya_procesado(self):
        """Test: Intentar firmar documento ya procesado"""
        self.invoice.estado_dte = 'procesado'
        
        # Debe lanzar error
        with self.assertRaises(UserError) as context:
            self.invoice.action_firmar_dte()
        
        self.assertIn('ya ha sido procesado', str(context.exception))
    
    @patch('requests.post')
    def test_enviar_a_mh_exitoso(self, mock_post):
        """Test: Simular envío exitoso al MH"""
        # Configurar invoice como firmado
        self.invoice.estado_dte = 'firmado'
        self.invoice.documento_firmado = 'documento_test'
        self.invoice.uuid_generation_code = str(uuid.uuid4())
        
        # Configurar mock de respuesta exitosa del MH
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'estado': 'PROCESADO',
            'selloRecibido': 'SELLO123ABC',
            'descripcionMsg': 'Documento procesado correctamente'
        }
        mock_post.return_value = mock_response
        
        url = self.invoice._get_url_mh()
        payload = {
            "ambiente": "00",
            "documento": self.invoice.documento_firmado,
            "codigoGeneracion": self.invoice.uuid_generation_code
        }
        
        resultado = self.invoice._enviar_a_mh(url, payload)
        
        # Verificar resultado exitoso
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['sello'], 'SELLO123ABC')
    
    def test_get_url_mh_ambiente_pruebas(self):
        """Test: Verificar URL correcta para ambiente de pruebas"""
        self.company.ambiente_dte = '00'
        url = self.invoice._get_url_mh()
        
        self.assertIn('apitest', url)
    
    def test_get_url_mh_ambiente_produccion(self):
        """Test: Verificar URL correcta para ambiente de producción"""
        self.company.ambiente_dte = '01'
        url = self.invoice._get_url_mh()
        
        self.assertIn('api.dtes', url)
        self.assertNotIn('apitest', url)
    
    def test_action_enviar_a_mh_sin_firma(self):
        """Test: Intentar enviar sin documento firmado"""
        self.invoice.estado_dte = 'draft'
        
        with self.assertRaises(UserError) as context:
            self.invoice.action_enviar_a_mh()
        
        self.assertIn('debe estar firmado', str(context.exception))
    
    def test_preparar_extension(self):
        """Test: Verificar preparación de extensión"""
        self.invoice.narration = 'Observaciones de prueba'
        extension = self.invoice._preparar_extension()
        
        self.assertIn('observaciones', extension)
        self.assertEqual(extension['observaciones'], 'Observaciones de prueba')
    
    def test_preparar_apendice(self):
        """Test: Verificar preparación de apéndice"""
        self.invoice.payment_reference = 'REF-001'
        apendice = self.invoice._preparar_apendice()
        
        self.assertIsInstance(apendice, list)
        self.assertGreater(len(apendice), 0)
        
        primer_campo = apendice[0]
        self.assertEqual(primer_campo['campo'], 'numeroInterno')
        self.assertEqual(primer_campo['valor'], 'REF-001')
    
    def test_multiple_items_numeracion(self):
        """Test: Verificar numeración correcta con múltiples items"""
        # Agregar más líneas a la factura
        self.env['account.move.line'].create({
            'move_id': self.invoice.id,
            'product_id': self.product.id,
            'quantity': 1,
            'price_unit': 50.00,
        })
        
        items = self.invoice._preparar_items_documento()
        
        # Verificar cantidad de items
        self.assertEqual(len(items), 2)
        
        # Verificar numeración secuencial
        self.assertEqual(items[0]['numItem'], 1)
        self.assertEqual(items[1]['numItem'], 2)
    
    def test_json_data_guardado_correctamente(self):
        """Test: Verificar que el JSON se guarda correctamente"""
        payload = self.invoice._preparar_payload_dte()
        json_str = json.dumps(payload['dteJson'], ensure_ascii=False)
        
        # El JSON debe ser válido
        json_parsed = json.loads(json_str)
        self.assertIsInstance(json_parsed, dict)
        
        # Debe contener las secciones principales
        self.assertIn('identificacion', json_parsed)
        self.assertIn('cuerpoDocumento', json_parsed)