from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime

class res_partner(models.Model):
    _inherit = "res.partner"

    license_applicable = fields.Boolean("License Applicable")
    license_no = fields.Char(string="License Number")
    license_date = fields.Date(string="License Date")
    credit_limit = fields.Float(string="Credit Limit")
    credit_limit_applicable = fields.Boolean("Credit Limit Applicable")

class SaleAdvanceInvoicePayment(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    @api.multi
    def create_invoices(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        default=fields.Date.today()
        if sale_orders.license_applicable:
            if not sale_orders.license_date:
                raise UserError(_('Assign License Expiry Date for Customer.'))
        if sale_orders.license_date < default:
            if not sale_orders.license_approved1:
                raise UserError(_('This Customer Trade License already Expired Please Collect renewed trade license from the customer or you need special approval to create invoice'))
        if sale_orders.license_date > default:
            if not sale_orders.license_approved1:
                raise UserError(_('This Customer Trade License already Expired Please Collect renewed trade license from the customer or you need special approval to create invoice'))

        invoice_total = 0
        payment_total = 0
        exceed_amount = 0
        customer_inv = self.env["account.invoice"].search([('partner_id','=', sale_orders.partner_id.id), ('state','not in',['draft','cancel']),('type', '=','out_invoice')])
        for inv in customer_inv:
            invoice_total+= inv.amount_total
        customer_payment = self.env["account.payment"].search([('partner_id','=', sale_orders.partner_id.id), ('payment_type', '=','inbound'),('state','in',['posted','reconciled'])])
        for pay in customer_payment:
            payment_total+= pay.amount
        if invoice_total == 0:
            if sale_orders.amount_total > sale_orders.credit_limit:
                if not sale_orders.credit_limit_updated:
                    raise UserError(_('Exceeded Credit limit Please Collect Payment from Customer Or you need special approval to Create Invoice'))
        if payment_total > invoice_total:
            # normal function
            if self.advance_payment_method == 'delivered':
            	sale_orders.action_invoice_create()
            elif self.advance_payment_method == 'all':
                sale_orders.action_invoice_create(final=True)
            else:
                # Create deposit product if necessary
                if not self.product_id:
                    vals = self._prepare_deposit_product()
                    self.product_id = self.env['product.product'].create(vals)
                    self.env['ir.values'].sudo().set_default('sale.config.settings', 'deposit_product_id_setting', self.product_id.id)

                sale_line_obj = self.env['sale.order.line']
                for order in sale_orders:
                    if self.advance_payment_method == 'percentage':
                        amount = order.amount_untaxed * self.amount / 100
                    else:
                        amount = self.amount
                    if self.product_id.invoice_policy != 'order':
                        raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                    if self.product_id.type != 'service':
                        raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                    if order.fiscal_position_id and self.product_id.taxes_id:
                        tax_ids = order.fiscal_position_id.map_tax(self.product_id.taxes_id).ids
                    else:
                        tax_ids = self.product_id.taxes_id.ids
                    so_line = sale_line_obj.create({
                        'name': _('Advance: %s') % (time.strftime('%m %Y'),),
                        'price_unit': amount,
                        'product_uom_qty': 0.0,
                        'order_id': order.id,
                        'discount': 0.0,
                        'product_uom': self.product_id.uom_id.id,
                        'product_id': self.product_id.id,
                        'tax_id': [(6, 0, tax_ids)],
                    })
                    self._create_invoice(order, so_line, amount)
            if self._context.get('open_invoices', False):
                return sale_orders.action_view_invoice()
            return {'type': 'ir.actions.act_window_close'}

        elif invoice_total > payment_total:
            exceed_amount = (invoice_total + sale_orders.amount_total) - payment_total
        if exceed_amount > sale_orders.credit_limit:
            if sale_orders.credit_limit_updated:
                if self.advance_payment_method == 'delivered':
                    sale_orders.action_invoice_create()
                elif self.advance_payment_method == 'all':
                    sale_orders.action_invoice_create(final=True)
                else:
                    # Create deposit product if necessary
                    if not self.product_id:
                        vals = self._prepare_deposit_product()
                        self.product_id = self.env['product.product'].create(vals)
                        self.env['ir.values'].sudo().set_default('sale.config.settings', 'deposit_product_id_setting', self.product_id.id)

                    sale_line_obj = self.env['sale.order.line']
                    for order in sale_orders:
                        if self.advance_payment_method == 'percentage':
                            amount = order.amount_untaxed * self.amount / 100
                        else:
                            amount = self.amount
                        if self.product_id.invoice_policy != 'order':
                            raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                        if self.product_id.type != 'service':
                            raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                        if order.fiscal_position_id and self.product_id.taxes_id:
                            tax_ids = order.fiscal_position_id.map_tax(self.product_id.taxes_id).ids
                        else:
                            tax_ids = self.product_id.taxes_id.ids
                        so_line = sale_line_obj.create({
                            'name': _('Advance: %s') % (time.strftime('%m %Y'),),
                            'price_unit': amount,
                            'product_uom_qty': 0.0,
                            'order_id': order.id,
                            'discount': 0.0,
                            'product_uom': self.product_id.uom_id.id,
                            'product_id': self.product_id.id,
                            'tax_id': [(6, 0, tax_ids)],
                        })
                        self._create_invoice(order, so_line, amount)
                if self._context.get('open_invoices', False):
                    return sale_orders.action_view_invoice()
                return {'type': 'ir.actions.act_window_close'}
            else:
                raise UserError(_('Exceeded Credit limit Please Collect Payment from Customer Or you need special approval to Create Invoice'))
        else:
        	# normal function
            if self.advance_payment_method == 'delivered':
                sale_orders.action_invoice_create()
            elif self.advance_payment_method == 'all':
                sale_orders.action_invoice_create(final=True)
            else:
                # Create deposit product if necessary
                if not self.product_id:
                    vals = self._prepare_deposit_product()
                    self.product_id = self.env['product.product'].create(vals)
                    self.env['ir.values'].sudo().set_default('sale.config.settings', 'deposit_product_id_setting', self.product_id.id)

                sale_line_obj = self.env['sale.order.line']
                for order in sale_orders:
                    if self.advance_payment_method == 'percentage':
                        amount = order.amount_untaxed * self.amount / 100
                    else:
                        amount = self.amount
                    if self.product_id.invoice_policy != 'order':
                        raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                    if self.product_id.type != 'service':
                        raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                    if order.fiscal_position_id and self.product_id.taxes_id:
                        tax_ids = order.fiscal_position_id.map_tax(self.product_id.taxes_id).ids
                    else:
                        tax_ids = self.product_id.taxes_id.ids
                    so_line = sale_line_obj.create({
                        'name': _('Advance: %s') % (time.strftime('%m %Y'),),
                        'price_unit': amount,
                        'product_uom_qty': 0.0,
                        'order_id': order.id,
                        'discount': 0.0,
                        'product_uom': self.product_id.uom_id.id,
                        'product_id': self.product_id.id,
                        'tax_id': [(6, 0, tax_ids)],
                    })
                    self._create_invoice(order, so_line, amount)
            if self._context.get('open_invoices', False):
                return sale_orders.action_view_invoice()
            return {'type': 'ir.actions.act_window_close'}



class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.one
    def _compute_credit_limit_updated(self):
        invoice_total = 0
        payment_total = 0
        exceed_amount = 0
        customer_inv = self.env["account.invoice"].search([('partner_id','=', self.partner_id.id), ('state','not in',['draft','cancel']),('type', '=','out_invoice')])
        for inv in customer_inv:
            invoice_total+= inv.amount_total
        customer_payment = self.env["account.payment"].search([('partner_id','=', self.partner_id.id), ('payment_type', '=','inbound'),('state','in',['posted','reconciled'])])
        for pay in customer_payment:
            payment_total+= pay.amount
        if invoice_total == 0:
            exceed_amount == 0
        if invoice_total > payment_total:
            self.credit_limit_updated = False


    @api.one
    @api.depends('license_date')
    def _compute_license_update(self):
        today = fields.Date.today()
        if self.license_date >= today:
            self.license_approved1 = True

    @api.one
    @api.depends('partner_id')
    def _compute_credit_license(self):
        if self.partner_id:
            self.credit_limit = self.partner_id.credit_limit
            self.credit_limit_applicable = self.partner_id.credit_limit_applicable
            self.license_applicable = self.partner_id.license_applicable
            self.license_no = self.partner_id.license_no
            self.license_date = self.partner_id.license_date

    license_applicable = fields.Boolean("License Applicable", compute='_compute_credit_license')
    license_no = fields.Char(string="License Number", compute='_compute_credit_license')
    license_date = fields.Date(string="License Date", compute='_compute_credit_license')
    credit_limit = fields.Float(string="Credit Limit", compute='_compute_credit_license')
    credit_limit_applicable = fields.Boolean("Credit Limit Applicable", compute='_compute_credit_license')
    license_approved1 = fields.Boolean("License Approved", compute='_compute_license_update', store=True)
    credit_limit_updated = fields.Boolean("Credit Limit Approved", compute='_compute_credit_limit_updated', store=True)
    license_history_ids = fields.One2many('license.history', 'sale_order_id', string="License")
    credit_limit_history_ids = fields.One2many('credit.limit.history', 'sale_order_id', string="License")


    def approve_license_date(self):
        history = self.env['license.history'].create({'approve_by':self.env.uid, 'approve_time':datetime.datetime.now(),'sale_order_id':self.id})
        self.write({'license_approved1' : True})

    def approve_credit(self):
        history = self.env['credit.limit.history'].create({'approve_by':self.env.uid, 'approve_time':datetime.datetime.now(), 'sale_order_id':self.id})
        self.write({'credit_limit_updated' : True})

class LicenseHistory(models.Model):
    _name = "license.history"

    approve_by = fields.Many2one('res.users', 'Approved by')
    approve_time = fields.Datetime('Approved time')
    sale_order_id = fields.Many2one('sale.order', "Sale")

class CreditLimitHistory(models.Model):
    _name = "credit.limit.history"

    approve_by = fields.Many2one('res.users', 'Approved by')
    approve_time = fields.Datetime('Approved time')
    sale_order_id = fields.Many2one('sale.order', "Sale")
