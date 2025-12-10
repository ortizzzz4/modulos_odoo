/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import {
  AlertDialog,
  ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";



patch(PaymentScreen.prototype, {
  setup() {
    super.setup(...arguments);

    this.orm = useService("orm");
    this.dialog = useService("dialog");
    this.notification = useService("notification");

    },



    async _get_functions_account(id) {
        try {
            const tipo_factura = this.document_type_sv.value;
        
        let result;

        // Mapeo de métodos según tipo de factura
        const methodMap = {
            "01": "firmar_documentos_fc_pos",
           
        };

        if (!methodMap[tipo_factura]) {
            this.dialog.add(AlertDialog, {
                title: "Error",
                body: "Diario no configurado para DTE",
            });
            return { success: false };
        }

        // Llamar al método dinámicamente
        result = await this.orm.call(
            "account.move",
            methodMap[tipo_factura],
            [id]
        );

        if (!result.success) {
            this.dialog.add(AlertDialog, {
                title: "Error en DTE",
                body: result.message,
            });
            return { success: false };
        }

        // ✅ Éxito - Extraer y guardar datos del payload
        const payload = result.payload || {};
    
        this.notification.add(_t(`DTE procesado correctamente\n\n📄 Factura: ${payload.numero_factura}\n🔐 UUID: ${payload.uuid_generation_code}`), {
            type: "success", // 'success', 'warning', 'danger', or 'info'
            sticky: false,
        })

      
        return {
            success: true,
            qr_link: payload.qr_link || null,
            confirmacion: payload.confirmacion || null,
            numero_factura: payload.numero_factura || null,
            uuid_generation_code: payload.uuid_generation_code || null,
            estado_dte: payload.estado_dte || null,
            fecha_factura: payload.fecha_factura || null,
        };
    } catch (e) {
        console.error("Error:", e);
        this.dialog.add(AlertDialog, {
            title: "Error",
            body: "Ocurrió un error inesperado: " + (e.message || ""),
        });
        return { success: false };
    } 

}


});