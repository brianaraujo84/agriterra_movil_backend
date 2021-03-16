# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"
    razon_social = fields.Char(string=u"Razón Social", size=100)
    nit_ci = fields.Char(string=u"NIT/CI", size=12)

    @api.onchange('name')
    def onchange_name_razon_social(self):
        for company in self:
            company.razon_social = company.name
