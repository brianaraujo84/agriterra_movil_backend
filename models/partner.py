# -*- coding: utf-8 -*-
from odoo import fields, models,api, _
from odoo.osv.expression import get_unaccent_wrapper
import re
class ResPartner(models.Model):
    _inherit = 'res.partner'
    SELECTION_EXPEDITION = [
        ('La Paz', 'LP'),
        ('Oruro', 'OR'),
        ('Cochabamba', 'CB'),
        ('Santa Cruz', 'SZ'),
        ('Beni', 'BN'),
        ('Pando', 'PN'),
        ('Chuquisaca', 'CH'),
        ('Tarija', 'TJ'),
        ('Potosi', 'PT'),
        ('Extranjero', 'EX'),
    ]
    razon_social = fields.Char(u"Razón Social", size=100, required=True, copy=False, default='S/N')
    nit_ci = fields.Char(u"NIT/CI", size=12, required=True, index=True, copy=False, default='0')
    nro_tacho = fields.Char(string="Número de Tacho",required=True)
    fecha_nacimiento =fields.Date(string="Fecha Nacimiento",track_visibility="onchange")
    expedido = fields.Selection(SELECTION_EXPEDITION, u"Expedido en", copy=False)

    @api.onchange('name')
    def onchange_name_razon_social(self):
        for partner in self:
            partner.razon_social = partner.name

    @api.onchange('nit_ci')
    def onchange_nitci(self):
        for partner in self:
            partner.vat = partner.nit_ci

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        self = self.sudo(name_get_uid or self.env.uid)
        if args is None:
            args = []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            self.check_access_rights('read')
            where_query = self._where_calc(args)
            self._apply_ir_rules(where_query, 'read')
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            from_str = from_clause if from_clause else 'res_partner'
            where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

            # search on the name of the contacts and of its company
            search_name = name
            if operator in ('ilike', 'like'):
                search_name = '%%%s%%' % name
            if operator in ('=ilike', '=like'):
                operator = operator[1:]

            unaccent = get_unaccent_wrapper(self.env.cr)

            query = """SELECT res_partner.id
                             FROM {from_str}
                          {where} ({email} {operator} {percent}
                               OR {display_name} {operator} {percent}
                               OR {reference} {operator} {percent}
                               OR {vat} {operator} {percent}
                               OR {nit_ci} {operator} {percent})
                               -- don't panic, trust postgres bitmap
                         ORDER BY {display_name} {operator} {percent} desc,
                                  {display_name}
                        """.format(from_str=from_str,
                                   where=where_str,
                                   operator=operator,
                                   email=unaccent('res_partner.email'),
                                   display_name=unaccent('res_partner.display_name'),
                                   reference=unaccent('res_partner.ref'),
                                   percent=unaccent('%s'),
                                   vat=unaccent('res_partner.vat'),
                                   nit_ci=unaccent('res_partner.nit_ci'),)

            where_clause_params += [search_name] * 3  # for email / display_name, reference
            where_clause_params += [re.sub('[^a-zA-Z0-9]+', '', search_name) or None]  # for vat
            where_clause_params += [re.sub('[^a-zA-Z0-9]+', '', search_name) or None]  # for nit_ci
            where_clause_params += [search_name]  # for order by
            if limit:
                query += ' limit %s'
                where_clause_params.append(limit)
            self.env.cr.execute(query, where_clause_params)
            partner_ids = [row[0] for row in self.env.cr.fetchall()]

            if partner_ids:
                return self.browse(partner_ids).name_get()
            else:
                return []
        return super(ResPartner, self)._name_search(name, args, operator=operator, limit=limit, name_get_uid=name_get_uid)