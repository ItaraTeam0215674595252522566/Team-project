from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round

class Picking(models.Model):
    _inherit = "stock.picking"

    @api.multi
    def button_validate(self):
        self.ensure_one()
        invoice_total = 0
        payment_total = 0
        exceed_amount = 0
        customer_inv = self.env["account.invoice"].search([('partner_id','=', self.partner_id.id), ('state','not in',['draft','cancel']),('type', '=','out_invoice')])
        for inv in customer_inv:
            invoice_total+= inv.amount_total
        customer_payment = self.env["account.payment"].search([('partner_id','=', self.partner_id.id), ('payment_type', '=','inbound'),('state','in',['posted','reconciled'])])
        for pay in customer_payment:
            payment_total+= pay.amount
        sale = self.env['sale.order'].search([('name','=',self.origin)])
        delivered_quantity = all(line.product_id.invoice_policy == 'delivery' for line in self.move_line_ids)
        print (delivered_quantity, "delivered_quantitydelivered_quantity-----------")
        if payment_total > invoice_total:
            print ("else")
        elif invoice_total > payment_total:
            exceed_amount = (invoice_total + sale.amount_total) - payment_total
        if delivered_quantity:
            if exceed_amount > self.partner_id.credit_limit:
                raise UserError(_('Credit limit exceeded for this customer'))
        else:
            if not self.move_lines and not self.move_line_ids:
                raise UserError(_('Please add some lines to move'))

            # If no lots when needed, raise error
            picking_type = self.picking_type_id
            no_quantities_done = all(line.qty_done == 0.0 for line in self.move_line_ids)
            no_initial_demand = all(move.product_uom_qty == 0.0 for move in self.move_lines)
            if no_initial_demand and no_quantities_done:
                raise UserError(_('You cannot validate a transfer if you have not processed any quantity.'))

            if picking_type.use_create_lots or picking_type.use_existing_lots:
                lines_to_check = self.move_line_ids
                if not no_quantities_done:
                    lines_to_check = lines_to_check.filtered(
                        lambda line: float_compare(line.qty_done, 0,
                                                   precision_rounding=line.product_uom_id.rounding)
                    )

                for line in lines_to_check:
                    product = line.product_id
                    if product and product.tracking != 'none' and (line.qty_done == 0 or (not line.lot_name and not line.lot_id)):
                        raise UserError(_('You need to supply a lot/serial number for %s.') % product.name)

            if no_quantities_done:
                view = self.env.ref('stock.view_immediate_transfer')
                wiz = self.env['stock.immediate.transfer'].create({'pick_ids': [(4, self.id)]})
                return {
                    'name': _('Immediate Transfer?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.immediate.transfer',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'res_id': wiz.id,
                    'context': self.env.context,
                }

            if self._get_overprocessed_stock_moves() and not self._context.get('skip_overprocessed_check'):
                view = self.env.ref('stock.view_overprocessed_transfer')
                wiz = self.env['stock.overprocessed.transfer'].create({'picking_id': self.id})
                return {
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.overprocessed.transfer',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'res_id': wiz.id,
                    'context': self.env.context,
                }

            # Check backorder should check for other barcodes
            if self._check_backorder():
                return self.action_generate_backorder_wizard()
            self.action_done()
        return