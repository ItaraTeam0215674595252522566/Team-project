from odoo import api, fields, models, _

class CreditLimitWarning(models.Model):
    _name = "credit.limit.warning"

    name = fields.Char("Name")

    @api.multi
    def action_set(self):
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            sale = self.env['sale.order'].browse(active_id)
            sale.write({'credit_limit_checked': True})
        return True
