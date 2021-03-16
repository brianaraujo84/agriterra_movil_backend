# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class AccountAssetCategory(models.Model):
    _name = 'account.asset.category'
    _description = 'Asset category'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, index=True, string="Tipo de activo")
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analítica')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Etiqueta analítica')
    account_asset_id = fields.Many2one('account.account', string='Cuenta de activos', required=True, domain=[('internal_type','=','other'), ('deprecated', '=', False)], help="Cuenta utilizada para registrar la compra del activo a su precio original.")
    account_depreciation_id = fields.Many2one('account.account', string='Asientos de amortización: Cuenta de activo fijo', required=True, domain=[('internal_type','=','other'), ('deprecated', '=', False)], help="Cuenta utilizada en los asientos de depreciación, para disminuir el valor del activo.")
    account_depreciation_expense_id = fields.Many2one('account.account', string='Asientos de amortización: Cuenta de gastos', required=True, domain=[('internal_type','=','other'), ('deprecated', '=', False)], help="Cuenta utilizada en los asientos periódicos, para registrar una parte del activo como gasto.")
    journal_id = fields.Many2one('account.journal', string='Diario', required=True)
    company_id = fields.Many2one('res.company', string='Granja', required=True, default=lambda self: self.env['res.company']._company_default_get('account.asset.category'))
    method = fields.Selection([('linear', 'Lineal'), ('degressive', 'Regresiva')], string='Método de cálculo', required=True, default='linear',
        help="Elija el método a utilizar para calcular el importe de las líneas de amortización.\n"
            "  * Lineal: Calculado en base a: Valor bruto / Número de amortizaciones\n"
            "  * Regresiva: Calculado en base a: Valor Residual * Factor Degresivo")
    type_general = fields.Selection([('installations', 'Instalaciones'), ('machinery', 'Maquinaria Equipos y Herramientas')], string='Tipo Activo Agriterra', required=True, default='installations',
        help="Elija el tipo de clasificación general del activo.")
    method = fields.Selection([('linear', 'Lineal'), ('degressive', 'Regresiva')], string='Método de cálculo', required=True, default='linear',
        help="Elija el método a utilizar para calcular el importe de las líneas de amortización.\n"
            "  * Lineal: Calculado en base a: Valor bruto / Número de amortizaciones\n"
            "  * Regresiva: Calculado en base a: Valor Residual * Factor Degresivo")
    method_number = fields.Integer(string='Número de amortizaciones', default=5, help="El número de amortizaciones necesarias para depreciar su activo")
    method_period = fields.Integer(string='Duración del período', default=1, help="Indique aquí el tiempo entre 2 depreciaciones, en meses", required=True)
    method_progress_factor = fields.Float('Factor de Regresión', default=0.3)
    method_time = fields.Selection([('number', 'Número de Entradas'), ('end', 'Fecha Finalización')], string='Método del tiempo', required=True, default='number',
        help="Elija el método para calcular las fechas y el número de entradas.\n"
           "  * Número de entradas: Fija el número de entradas y el tiempo entre 2 amortizaciones.\n"
           "  * Fecha de finalización: Elija el tiempo entre 2 amortizaciones y la fecha en la que las amortizaciones no irán más allá.")
    method_end = fields.Date('Fecha Finalización')
    prorata = fields.Boolean(string='Prorata Temporis', help='Indica que el primer asiento de amortización de este activo debe realizarse a partir de la fecha de compra en lugar del primero de enero')
    open_asset = fields.Boolean(string='Confirmar automáticamente los activos', help="Marque esta opción si desea confirmar automáticamente los activos de esta categoría cuando sean creados por las facturas.")
    group_entries = fields.Boolean(string='Anotaciones en grupo del diario', help="Marque esta opción si desea agrupar las entradas generadas por categorías.")
    type = fields.Selection([('sale', 'Venta: Reconocimiento de ingresos'), ('purchase', 'Compra: Activo')], required=True, index=True, default='purchase')
    date_first_depreciation = fields.Selection([
        ('last_day_period', 'Basado en el último día del periodo de compra'),
        ('manual', 'Manual (por defecto en la fecha de compra)')],
        string='Fechas de amortización', default='manual', required=True,
        help='La forma de computar la fecha de la primera amortización.\n'
             '  * Basado en el último día del periodo de compra: Las fechas de amortización se basarán en el último día del mes de compra o del año de compra (dependiendo de la periodicidad de las amortizaciones).\n'
             '  * Basado en la fecha de compra: Las fechas de amortización se basarán en la fecha de compra.')

    @api.onchange('account_asset_id')
    def onchange_account_asset(self):
        if self.type == "purchase":
            self.account_depreciation_id = self.account_asset_id
        elif self.type == "sale":
            self.account_depreciation_expense_id = self.account_asset_id

    @api.onchange('type')
    def onchange_type(self):
        if self.type == 'sale':
            self.prorata = True
            self.method_period = 1
        else:
            self.method_period = 12

    @api.onchange('method_time')
    def _onchange_method_time(self):
        if self.method_time != 'number':
            self.prorata = False


class AccountAssetAsset(models.Model):
    _name = 'account.asset.asset'
    _description = 'Asset/Revenue Recognition'
    _inherit = ['mail.thread']

    entry_count = fields.Integer(compute='_entry_count', string='# Asset Entries')
    name = fields.Char(string='Nombre del Activo', required=True, readonly=True, states={'draft': [('readonly', False)]})
    code = fields.Char(string='Referencia', size=32, readonly=True, states={'draft': [('readonly', False)]})
    value = fields.Float(string='Valor Bruto', required=True, readonly=True, digits=0, states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env.user.company_id.currency_id.id)
    company_id = fields.Many2one('res.company', string='Granja', required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env['res.company']._company_default_get('account.asset.asset'))
    note = fields.Text()
    category_id = fields.Many2one('account.asset.category', string='Categoría', required=True, change_default=True, readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Date(string='Fecha', required=True, readonly=True, states={'draft': [('readonly', False)]}, default=fields.Date.context_today)
    state = fields.Selection([('draft', 'Borrador'), ('open', 'Corriendo'), ('close', 'Cerrado')], 'Status', required=True, copy=False, default='draft',
        help="Cuando se crea un activo, el estado es Borrador.'.\n"
            "Si se confirma el activo, el estado pasa a ser 'En ejecución'.' y las líneas de amortización se pueden contabilizar en la contabilidad.\n"
            "Puede cerrar manualmente un activo cuando la depreciación haya terminado. Si se contabiliza la última línea de depreciación, el activo pasa automáticamente a ese estado.")
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Socio', readonly=True, states={'draft': [('readonly', False)]})
    method = fields.Selection([('linear', 'Lineal'), ('degressive', 'Regresión')], string='Método de cálculo', required=True, readonly=True, states={'draft': [('readonly', False)]}, default='linear',
        help="Elija el método a utilizar para calcular el importe de las líneas de amortización.\n  * Lineal: Calculado en base a: Valor bruto / Número de amortizaciones\n"
            "  * Factor de regresión: Calculado en base a: Valor Residual * Factor de regresión")
    method_number = fields.Integer(string='Número de amortizaciones', readonly=True, states={'draft': [('readonly', False)]}, default=5, help="El número de amortizaciones necesarias para depreciar su activo")
    method_period = fields.Integer(string='Número de meses en un período', required=True, readonly=True, default=12, states={'draft': [('readonly', False)]},
        help="La cantidad de tiempo entre dos depreciaciones, en meses")
    method_end = fields.Date(string='Fecha de finalización', readonly=True, states={'draft': [('readonly', False)]})
    method_progress_factor = fields.Float(string='Factor de regresión', readonly=True, default=0.3, states={'draft': [('readonly', False)]})
    value_residual = fields.Float(compute='_amount_residual', method=True, digits=0, string='Valor residual')
    method_time = fields.Selection([('number', 'Número de registros'), ('end', 'Fecha de finalización')], string='Método del tiempo', required=True, readonly=True, default='number', states={'draft': [('readonly', False)]},
        help="Elija el método para calcular las fechas y el número de entradas.\n"
             "  * Número de registros: Fijar el número de registros y el tiempo entre 2 amortizaciones.\n"
             "  * Fecha de finalización: Elija el tiempo entre 2 amortizaciones y la fecha en la que las amortizaciones no irán más allá.")
    prorata = fields.Boolean(string='Prorata Temporis', readonly=True, states={'draft': [('readonly', False)]},
        help='Indica que el primer asiento de amortización para este activo debe realizarse a partir de la fecha del activo (fecha de compra) en lugar del primer enero / fecha de inicio del año fiscal')
    depreciation_line_ids = fields.One2many('account.asset.depreciation.line', 'asset_id', string='Líneas de amortización', readonly=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]})
    salvage_value = fields.Float(string='Valor residual', digits=0, readonly=True, states={'draft': [('readonly', False)]},
        help="Es la cantidad que planeas tener y que no puedes amortizar.")
    invoice_id = fields.Many2one('account.move', string='Factura', states={'draft': [('readonly', False)]}, copy=False)
    type = fields.Selection(related="category_id.type", string='Tipo', required=True)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analítica')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Etiqueta analítica')
    date_first_depreciation = fields.Selection([
        ('last_day_period', 'Basado en el último día del periodo de compra'),
        ('manual', 'Manual')],
        string='Fechas de amortización', default='manual',
        readonly=True, states={'draft': [('readonly', False)]}, required=True,
        help='La forma de computar la fecha de la primera amortización.\n'
             '  * Basado en el último día del periodo de compra: Las fechas de amortización se basarán en el último día del mes de compra o del año de compra (dependiendo de la periodicidad de las amortizaciones).\n'
             '  * Basado en la fecha de compra: Las fechas de amortización se basarán en la fecha de compra.\n')
    first_depreciation_manual_date = fields.Date(
        string='Primera fecha de amortización',
        readonly=True, states={'draft': [('readonly', False)]},
        help='Obsérvese que esta fecha no altera el cómputo del primer asiento en caso de activos prorata temporis. Simplemente cambia su fecha de contabilización'
    )

    
    def unlink(self):
        for asset in self:
            if asset.state in ['open', 'close']:
                raise UserError(_('No se puede eliminar un documento que esté en %s state.') % (asset.state,))
            for depreciation_line in asset.depreciation_line_ids:
                if depreciation_line.move_id:
                    raise UserError(_('No se puede borrar un documento que contenga entradas contabilizadas.'))
        return super(AccountAssetAsset, self).unlink()

    @api.model
    def _cron_generate_entries(self):
        self.compute_generated_entries(datetime.today())

    @api.model
    def compute_generated_entries(self, date, asset_type=None):
        # Entries generated : one by grouped category and one by asset from ungrouped category
        created_move_ids = []
        type_domain = []
        if asset_type:
            type_domain = [('type', '=', asset_type)]

        ungrouped_assets = self.env['account.asset.asset'].search(type_domain + [('state', '=', 'open'), ('category_id.group_entries', '=', False)])
        created_move_ids += ungrouped_assets._compute_entries(date, group_entries=False)

        for grouped_category in self.env['account.asset.category'].search(type_domain + [('group_entries', '=', True)]):
            assets = self.env['account.asset.asset'].search([('state', '=', 'open'), ('category_id', '=', grouped_category.id)])
            created_move_ids += assets._compute_entries(date, group_entries=True)
        return created_move_ids

    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
            if self.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                if self.prorata:
                    amount = amount_to_depr / self.method_number
                    if sequence == 1:
                        date = self.date
                        if self.method_period % 12 != 0:
                            month_days = calendar.monthrange(date.year, date.month)[1]
                            days = month_days - date.day + 1
                            amount = (amount_to_depr / self.method_number) / month_days * days
                        else:
                            days = (self.company_id.compute_fiscalyear_dates(date)['date_to'] - date).days + 1
                            amount = (amount_to_depr / self.method_number) / total_days * days
            elif self.method == 'degressive':
                amount = residual_amount * self.method_progress_factor
                if self.prorata:
                    if sequence == 1:
                        date = self.date
                        if self.method_period % 12 != 0:
                            month_days = calendar.monthrange(date.year, date.month)[1]
                            days = month_days - date.day + 1
                            amount = (residual_amount * self.method_progress_factor) / month_days * days
                        else:
                            days = (self.company_id.compute_fiscalyear_dates(date)['date_to'] - date).days + 1
                            amount = (residual_amount * self.method_progress_factor) / total_days * days
        return amount

    def _compute_board_undone_dotation_nb(self, depreciation_date, total_days):
        undone_dotation_number = self.method_number
        if self.method_time == 'end':
            end_date = self.method_end
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = date(depreciation_date.year, depreciation_date.month, depreciation_date.day) + relativedelta(months=+self.method_period)
                undone_dotation_number += 1
        if self.prorata:
            undone_dotation_number += 1
        return undone_dotation_number

    
    def compute_depreciation_board(self):
        self.ensure_one()

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.value_residual != 0.0:
            amount_to_depr = residual_amount = self.value_residual

            # if we already have some previous validated entries, starting date is last entry + method period
            if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                last_depreciation_date = fields.Date.from_string(posted_depreciation_line_ids[-1].depreciation_date)
                depreciation_date = last_depreciation_date + relativedelta(months=+self.method_period)
            else:
                # depreciation_date computed from the purchase date
                depreciation_date = self.date
                if self.date_first_depreciation == 'last_day_period':
                    # depreciation_date = the last day of the month
                    depreciation_date = depreciation_date + relativedelta(day=31)
                    # ... or fiscalyear depending the number of period
                    if self.method_period == 12:
                        depreciation_date = depreciation_date + relativedelta(month=self.company_id.fiscalyear_last_month)
                        depreciation_date = depreciation_date + relativedelta(day=self.company_id.fiscalyear_last_day)
                        if depreciation_date < self.date:
                            depreciation_date = depreciation_date + relativedelta(years=1)
                elif self.first_depreciation_manual_date and self.first_depreciation_manual_date != self.date:
                    # depreciation_date set manually from the 'first_depreciation_manual_date' field
                    depreciation_date = self.first_depreciation_manual_date

            total_days = (depreciation_date.year % 4) and 365 or 366
            month_day = depreciation_date.day
            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)

            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date)
                amount = self.currency_id.round(amount)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.id,
                    'sequence': sequence,
                    'name': (self.code or '') + '/' + str(sequence),
                    'remaining_value': residual_amount,
                    'depreciated_value': self.value - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date,
                }
                commands.append((0, False, vals))

                depreciation_date = depreciation_date + relativedelta(months=+self.method_period)

                if month_day > 28 and self.date_first_depreciation == 'manual':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=min(max_day_in_month, month_day))

                # datetime doesn't take into account that the number of days is not the same for each month
                if not self.prorata and self.method_period % 12 != 0 and self.date_first_depreciation == 'last_day_period':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=max_day_in_month)

        self.write({'depreciation_line_ids': commands})

        return True

    
    def validate(self):
        self.write({'state': 'open'})
        fields = [
            'method',
            'method_number',
            'method_period',
            'method_end',
            'method_progress_factor',
            'method_time',
            'salvage_value',
            'invoice_id',
        ]
        ref_tracked_fields = self.env['account.asset.asset'].fields_get(fields)
        for asset in self:
            tracked_fields = ref_tracked_fields.copy()
            if asset.method == 'linear':
                del(tracked_fields['method_progress_factor'])
            if asset.method_time != 'end':
                del(tracked_fields['method_end'])
            else:
                del(tracked_fields['method_number'])
            dummy, tracking_value_ids = asset._message_track(tracked_fields, dict.fromkeys(fields))
            asset.message_post(subject=_('Asset created'), tracking_value_ids=tracking_value_ids)

    def _return_disposal_view(self, move_ids):
        name = _('Disposal Move')
        view_mode = 'form'
        if len(move_ids) > 1:
            name = _('Disposal Moves')
            view_mode = 'tree,form'
        return {
            'name': name,
            'view_type': 'form',
            'view_mode': view_mode,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': move_ids[0],
        }

    def _get_disposal_moves(self):
        move_ids = []
        for asset in self:
            unposted_depreciation_line_ids = asset.depreciation_line_ids.filtered(lambda x: not x.move_check)
            if unposted_depreciation_line_ids:
                old_values = {
                    'method_end': asset.method_end,
                    'method_number': asset.method_number,
                }

                # Remove all unposted depr. lines
                commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

                # Create a new depr. line with the residual amount and post it
                sequence = len(asset.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
                today = fields.Datetime.today()
                vals = {
                    'amount': asset.value_residual,
                    'asset_id': asset.id,
                    'sequence': sequence,
                    'name': (asset.code or '') + '/' + str(sequence),
                    'remaining_value': 0,
                    'depreciated_value': asset.value - asset.salvage_value,  # the asset is completely depreciated
                    'depreciation_date': today,
                }
                commands.append((0, False, vals))
                asset.write({'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
                tracked_fields = self.env['account.asset.asset'].fields_get(['method_number', 'method_end'])
                changes, tracking_value_ids = asset._message_track(tracked_fields, old_values)
                if changes:
                    asset.message_post(subject=_('Asset sold or disposed. Accounting entry awaiting for validation.'), tracking_value_ids=tracking_value_ids)
                move_ids += asset.depreciation_line_ids[-1].create_move(post_move=False)

        return move_ids

    
    def set_to_close(self):
        move_ids = self._get_disposal_moves()
        if move_ids:
            return self._return_disposal_view(move_ids)
        # Fallback, as if we just clicked on the smartbutton
        return self.open_entries()

    def set_to_draft(self):
        self.write({'state': 'draft'})

    @api.depends('value', 'salvage_value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
        for rec in self:
            total_amount = 0.0
            for line in rec.depreciation_line_ids:
                if line.move_check:
                    total_amount += line.amount
            rec.value_residual = rec.value - total_amount - rec.salvage_value

    @api.onchange('company_id')
    def onchange_company_id(self):
        self.currency_id = self.company_id.currency_id.id

    
    @api.onchange('date_first_depreciation')
    def onchange_date_first_depreciation(self):
        for record in self:
            if record.date_first_depreciation == 'manual':
                record.first_depreciation_manual_date = record.date

    
    @api.depends('depreciation_line_ids.move_id')
    def _entry_count(self):
        for asset in self:
            res = self.env['account.asset.depreciation.line'].search_count([('asset_id', '=', asset.id), ('move_id', '!=', False)])
            asset.entry_count = res or 0


    @api.constrains('prorata', 'method_time')
    def _check_prorata(self):
        if self.prorata and self.method_time != 'number':
            raise ValidationError(_('La prorata temporis sólo puede aplicarse para el método del "número de amortizaciones".'))

    @api.onchange('category_id')
    def onchange_category_id(self):
        vals = self.onchange_category_id_values(self.category_id.id)
        # We cannot use 'write' on an object that doesn't exist yet
        if vals:
            for k, v in vals['value'].items():
                setattr(self, k, v)

    def onchange_category_id_values(self, category_id):
        if category_id:
            category = self.env['account.asset.category'].browse(category_id)
            return {
                'value': {
                    'method': category.method,
                    'method_number': category.method_number,
                    'method_time': category.method_time,
                    'method_period': category.method_period,
                    'method_progress_factor': category.method_progress_factor,
                    'method_end': category.method_end,
                    'prorata': category.prorata,
                    'date_first_depreciation': category.date_first_depreciation,
                    'account_analytic_id': category.account_analytic_id.id,
                    'analytic_tag_ids': [(6, 0, category.analytic_tag_ids.ids)],
                }
            }

    @api.onchange('method_time')
    def onchange_method_time(self):
        if self.method_time != 'number':
            self.prorata = False

    
    def copy_data(self, default=None):
        if default is None:
            default = {}
        default['name'] = self.name + _(' (copy)')
        return super(AccountAssetAsset, self).copy_data(default)

    
    def _compute_entries(self, date, group_entries=False):
        depreciation_ids = self.env['account.asset.depreciation.line'].search([
            ('asset_id', 'in', self.ids), ('depreciation_date', '<=', date),
            ('move_check', '=', False)])
        if group_entries:
            return depreciation_ids.create_grouped_move()
        return depreciation_ids.create_move()

    @api.model
    def create(self, vals):
        asset = super(AccountAssetAsset, self.with_context(mail_create_nolog=True)).create(vals)
        asset.sudo().compute_depreciation_board()
        asset.sudo().validate()
        return asset

    
    def write(self, vals):
        res = super(AccountAssetAsset, self).write(vals)
        if 'depreciation_line_ids' not in vals and 'state' not in vals:
            for rec in self:
                rec.compute_depreciation_board()
        return res

    
    def open_entries(self):
        move_ids = []
        for asset in self:
            for depreciation_line in asset.depreciation_line_ids:
                if depreciation_line.move_id:
                    move_ids.append(depreciation_line.move_id.id)
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', move_ids)],
        }


class AccountAssetDepreciationLine(models.Model):
    _name = 'account.asset.depreciation.line'
    _description = 'Asset depreciation line'

    name = fields.Char(string='Nombre de Depreciación', required=True, index=True)
    sequence = fields.Integer(required=True)
    asset_id = fields.Many2one('account.asset.asset', string='Activo', required=True, ondelete='cascade')
    parent_state = fields.Selection(related='asset_id.state', string='Estado del activo')
    amount = fields.Float(string='Depreciación actual', digits=0, required=True)
    remaining_value = fields.Float(string='Depreciación del próximo período', digits=0, required=True)
    depreciated_value = fields.Float(string='Depreciación acumulada', required=True)
    depreciation_date = fields.Date('Fecha de amortización - Depreciación', index=True)
    move_id = fields.Many2one('account.move', string='Asiento de depreciación')
    move_check = fields.Boolean(compute='_get_move_check', string='Linked', track_visibility='always', store=True)
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always', store=True)

    
    @api.depends('move_id')
    def _get_move_check(self):
        for line in self:
            line.move_check = bool(line.move_id)

    
    @api.depends('move_id.state')
    def _get_move_posted_check(self):
        for line in self:
            line.move_posted_check = True if line.move_id and line.move_id.state == 'posted' else False

    
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        for line in self:
            if line.move_id:
                raise UserError(_('Esta depreciación ya está vinculada a un asiento. Por favor, publíquelo o elimínelo.'))
            move_vals = self._prepare_move(line)
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            created_moves |= move

        if post_move and created_moves:
            created_moves.filtered(lambda m: any(m.asset_depreciation_ids.mapped('asset_id.category_id.open_asset'))).post()
        return [x.id for x in created_moves]

    def _prepare_move(self, line):
        category_id = line.asset_id.category_id
        account_analytic_id = line.asset_id.account_analytic_id
        analytic_tag_ids = line.asset_id.analytic_tag_ids
        depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
        company_currency = line.asset_id.company_id.currency_id
        current_currency = line.asset_id.currency_id
        prec = company_currency.decimal_places
        amount = current_currency._convert(
            line.amount, company_currency, line.asset_id.company_id, depreciation_date)
        asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, len(line.asset_id.depreciation_line_ids))
        move_line_1 = {
            'name': asset_name,
            'account_id': category_id.account_depreciation_id.id,
            'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'partner_id': line.asset_id.partner_id.id,
            'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
            'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
            'currency_id': company_currency != current_currency and current_currency.id or False,
            'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
        }
        move_line_2 = {
            'name': asset_name,
            'account_id': category_id.account_depreciation_expense_id.id,
            'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'partner_id': line.asset_id.partner_id.id,
            'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
            'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
            'currency_id': company_currency != current_currency and current_currency.id or False,
            'amount_currency': company_currency != current_currency and line.amount or 0.0,
        }
        move_vals = {
            'ref': line.asset_id.code,
            'date': depreciation_date or False,
            'journal_id': category_id.journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
        }
        return move_vals

    def _prepare_move_grouped(self):
        asset_id = self[0].asset_id
        category_id = asset_id.category_id  # we can suppose that all lines have the same category
        account_analytic_id = asset_id.account_analytic_id
        analytic_tag_ids = asset_id.analytic_tag_ids
        depreciation_date = self.env.context.get('depreciation_date') or fields.Date.context_today(self)
        amount = 0.0
        for line in self:
            # Sum amount of all depreciation lines
            company_currency = line.asset_id.company_id.currency_id
            current_currency = line.asset_id.currency_id
            company = line.asset_id.company_id
            amount += current_currency._convert(line.amount, company_currency, company, fields.Date.today())

        name = category_id.name + _(' (grouped)')
        move_line_1 = {
            'name': name,
            'account_id': category_id.account_depreciation_id.id,
            'debit': 0.0,
            'credit': amount,
            'journal_id': category_id.journal_id.id,
            'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
            'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
        }
        move_line_2 = {
            'name': name,
            'account_id': category_id.account_depreciation_expense_id.id,
            'credit': 0.0,
            'debit': amount,
            'journal_id': category_id.journal_id.id,
            'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
            'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
        }
        move_vals = {
            'ref': category_id.name,
            'date': depreciation_date or False,
            'journal_id': category_id.journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
        }

        return move_vals

    
    def create_grouped_move(self, post_move=True):
        if not self.exists():
            return []

        created_moves = self.env['account.move']
        move = self.env['account.move'].create(self._prepare_move_grouped())
        self.write({'move_id': move.id, 'move_check': True})
        created_moves |= move

        if post_move and created_moves:
            self.post_lines_and_close_asset()
            created_moves.post()
        return [x.id for x in created_moves]

    
    def post_lines_and_close_asset(self):
        # we re-evaluate the assets to determine whether we can close them
        for line in self:
            line.log_message_when_posted()
            asset = line.asset_id
            if asset.currency_id.is_zero(asset.value_residual):
                asset.message_post(body=_("Document closed."))
                asset.write({'state': 'close'})

    
    def log_message_when_posted(self):
        def _format_message(message_description, tracked_values):
            message = ''
            if message_description:
                message = '<span>%s</span>' % message_description
            for name, values in tracked_values.items():
                message += '<div> &nbsp; &nbsp; &bull; <b>%s</b>: ' % name
                message += '%s</div>' % values
            return message

        for line in self:
            if line.move_id and line.move_id.state == 'draft':
                partner_name = line.asset_id.partner_id.name
                currency_name = line.asset_id.currency_id.name
                msg_values = {_('Currency'): currency_name, _('Amount'): line.amount}
                if partner_name:
                    msg_values[_('Partner')] = partner_name
                msg = _format_message(_('Depreciation line posted.'), msg_values)
                line.asset_id.message_post(body=msg)

    
    def unlink(self):
        for record in self:
            if record.move_check:
                if record.asset_id.category_id.type == 'purchase':
                    msg = _("No se pueden borrar las líneas de amortización contabilizadas.")
                else:
                    msg = _("No se pueden borrar las líneas de pago a plazos contabilizadas.")
                raise UserError(msg)
        return super(AccountAssetDepreciationLine, self).unlink()
