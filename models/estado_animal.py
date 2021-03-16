# -*- coding: utf-8 -*-

from odoo import models, fields, api


class EstadoAnimal(models.Model):
    _name = 'estado.animal'
    _description = 'Estado del Ganado'

    name = fields.Char()
    en_produccion = fields.Boolean()
    consumo_alimentación = fields.Float()
    edad_min_meses = fields.Integer(string = "Edad minima meses" )
    edad_max_meses = fields.Integer(string = "Edad máxima meses" )
    estado_registro = fields.Boolean(string = "Estado" )
    product_template_ids = fields.One2many(comodel_name='product.template', inverse_name='estado_animal_id', string='Registro de ganado')
    

class PartoAnimal(models.Model):
    _name = 'parto.animal'
    _description = 'Partos de animal'

    name = fields.Char(string="Descripción")
    nro_parto = fields.Integer(string = "Numero de Parto" )
    fecha_registro = fields.Date(string="Fecha de registro")
    product_template_id = fields.Many2one('product.template', string = "Inventario de Animal")


class VacunacionAnimal(models.Model):
    _name = 'vacunacion.animal'
    _description = 'Vacunacion Animal'

    name = fields.Char(string="Descripción")
    fecha_registro = fields.Date(string="Fecha de registro")
    product_template_id = fields.Many2one('product.template', string = "Vacunacion Animal")

                           

class ProductTemplate(models.Model):
    _inherit = "product.template"

    estado_animal_id = fields.Many2one('estado.animal', string = "Estado ganado")
    parto_animal_ids = fields.One2many(comodel_name='parto.animal', inverse_name='product_template_id', string='Parto Animal')
    vacunacion_animal_ids = fields.One2many(comodel_name='vacunacion.animal', inverse_name='product_template_id', string='Vacunacion Animal')
    edad_meses = fields.Integer(string="Edad al momento de registro")
    fecha_registro = fields.Date(string="Fecha de registro")
    fecha_nacimiento_animal = fields.Date(string="Fecha de nacimiento")
    nombre_animal = fields.Char(string="Nombre Animal")
    notas = fields.Char(string="Notas")
    produccion_leche = fields.Integer(string="Produccion Leche")
    default_quantity = fields.Float(string="Cantidad" ,default=1,required=True)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Nombre de animal debe ser único.'),
        ('default_code_uniq', 'UNIQUE (default_code)', 'Código de animal debe ser único.'),
    ]


    @api.model
    def create(self,vals):
        name = vals.get("name", "-")
        company_id = vals.get("company_id", "-")
        default_code = vals.get("default_code", "-")
        nombre_animal = vals.get("nombre_animal", "-")

        vals["name"] = nombre_animal + "-" + str(company_id) + "-" +  str(default_code)
        vals["default_code"] = str(company_id) + "-" + default_code     



        return  super(ProductTemplate,self).create(vals)



    # @api.model
    # def create(self, vals):
    #     """ Override to handle the "inventory mode" and create a quant as
    #     superuser the conditions are met.
    #     """
    #     if self._is_inventory_mode() and 'inventory_quantity' in vals:
    #         allowed_fields = self._get_inventory_fields_create()
    #         if any(field for field in vals.keys() if field not in allowed_fields):
    #             raise UserError(_("Quant's creation is restricted, you can't do this operation."))
    #         inventory_quantity = vals.pop('inventory_quantity')

    #         # Create an empty quant or write on a similar one.
    #         product = self.env['product.product'].browse(vals['product_id'])
    #         location = self.env['stock.location'].browse(vals['location_id'])
    #         lot_id = self.env['stock.production.lot'].browse(vals.get('lot_id'))
    #         package_id = self.env['stock.quant.package'].browse(vals.get('package_id'))
    #         owner_id = self.env['res.partner'].browse(vals.get('owner_id'))
    #         quant = self._gather(product, location, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=True)
    #         if quant:
    #             quant = quant[0]
    #         else:
    #             quant = self.sudo().create(vals)
    #         # Set the `inventory_quantity` field to create the necessary move.
    #         quant.inventory_quantity = inventory_quantity
    #         return quant
    #     res = super(StockQuant, self).create(vals)
    #     if self._is_inventory_mode():
    #         res._check_company()
    #     return res








class CrmLead(models.Model):
    _inherit = "crm.lead"

    partner_fecha_nacimiento = fields.Date(string="Fecha de nacimiento")


class ResCompany(models.Model):
    _inherit = "res.company"

    zona_geografica = fields.Char(string="Zona Geografica")
    tacho_ids = fields.One2many("tacho", "company_id")    
    

class Tacho(models.Model):
    _name = "tacho"
    _description = "Tacho"

    name = fields.Char("Tacho")
    company_id = fields.Many2one("res.company", string="Tacho")


