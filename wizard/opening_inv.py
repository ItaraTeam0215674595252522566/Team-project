from odoo import api, fields, models, _

class PendingInvoice(models.Model):
    _name = "pending.invoice"

    @api.model
    def default_get(self, fields):
        rec = super(PendingInvoice, self).default_get(fields)
        invoice_total = 0
        context = dict(self._context or {})
        active_ids = context.get('active_ids')
        sale = self.env['sale.order'].browse(active_ids)
        invoices = self.env['account.invoice'].search([('partner_id', '=', sale.partner_id.id), ('state', '=', 'open')])

        customer_inv = self.env["account.invoice"].search([('partner_id','=', sale.partner_id.id), ('state','in',['open']),('type', '=','out_invoice')])
        for inv in customer_inv:
            invoice_total+= inv.residual
        exceed_amount = sale.partner_id.credit_limit - invoice_total
        print invoice_total, sale.partner_id.credit_limit, exceed_amount, "exceed_amountexceed_amountexceed_amount"

        rec.update({
            'partner_id': sale.partner_id.id,
            'approved_credit_limit': sale.partner_id.credit_limit,
            'pending_invoices': invoices.ids,
            'available_credit_limit': exceed_amount
        })
        return rec

    approved_credit_limit = fields.Float("Approved Credit Limit")
    available_credit_limit = fields.Float("Available Credit Limit", store=True)
    partner_id = fields.Many2one('res.partner',"Customer")
    pending_invoices = fields.One2many('account.invoice','pending_id',"Pending Lines")

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    pending_id = fields.Many2one('pending.invoice', "PendingInvoice")
