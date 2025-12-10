# -*- coding: utf-8 -*-

from odoo import models,fields, api 
from datetime import datetime,date
import pytz


class AccountMove(models.mode):
    _inherit ='account.move'
    
    def action_post(self):
        """
         Funcion desde contabilidad que se ejecuta al validar un DTE SV
       
        """
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.journal_id.l10n_sv_dte_enable: # Si el diario tiene habilitado DTE SV
                move._l10n_sv_dte_generate_dte()
        return res
    
    def url_hora(self):
        """
        Funcion para obtener la hora actual en El Salvador y la URL del servicio de firma

        Returns:
            _type_: _dict con la zona horaria, hora actual y URL del servicio
        """
        tz = pytz.timezone('America/El_Salvador')
        hora_actual = datetime.now(tz).strftime('%H:%M:%S')
        url = f"http://dominio_ip:8113/firmardocumento" # Reemplazar con la URL real del servicio
        
        return {
            'tz': tz,
            'hora_actual': hora_actual,
            'url': url
        }
        
    def _l10n_sv_dte_generate_dte(self):
        """
        Funcion para generar el DTE SV desde la cuenta move
        """
        # Lógica para generar el DTE SV
        # Esto puede incluir la creación del XML, envío al servicio de facturación, etc.
        
        pass