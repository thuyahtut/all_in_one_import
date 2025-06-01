# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
import json
from odoo.tools import ustr
import logging
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)


class ImportJournalItemWizard(models.TransientModel):
    _name = "import.journal.item.wizard"
    _description = "Import Journal Item"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    sh_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")

    def validate_field_value(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        """ Validate field value, depending on field type and given value """
        self.ensure_one()

        try:
            checker = getattr(self, 'validate_field_' + field_ttype)
        except AttributeError:
            _logger.warning(
                field_ttype + ": This type of field has no validation method")
            return {}
        else:
            return checker(field_name, field_ttype, field_value, field_required, field_name_m2o)

    def validate_field_many2many(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['account.move.line'].fields_get()[
                field_name]['relation']

            ids_list = []
            if field_value.strip() not in (None, ""):
                for x in field_value.split(','):
                    x = x.strip()
                    if x != '':
                        record = self.env[name_relational_model].sudo().search([
                            (field_name_m2o, '=', x)
                        ], limit=1)

                        if record:
                            ids_list.append(record.id)
                        else:
                            return {"error": " - " + x + " not found. "}
                            break

            return {field_name: [(6, 0, ids_list)]}

    def validate_field_many2one(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['account.move.line'].fields_get()[
                field_name]['relation']
            record = self.env[name_relational_model].sudo().search([
                (field_name_m2o, '=', field_value)
            ], limit=1)
            return {field_name: record.id if record else False}

    def validate_field_text(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_integer(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_float(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_char(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_boolean(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        boolean_field_value = False
        if field_value.strip() == 'TRUE':
            boolean_field_value = True

        return {field_name: boolean_field_value}

    def validate_field_selection(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}

        # get selection field key and value.
        selection_key_value_list = self.env['account.move.line'].sudo(
        )._fields[field_name].selection
        if selection_key_value_list and field_value not in (None, ""):
            for tuple_item in selection_key_value_list:
                if tuple_item[1] == field_value:
                    return {field_name: tuple_item[0] or False}

            return {"error": " - " + field_name + " given value " + str(field_value) + " does not match for selection. "}

        # finaly return false
        if field_value in (None, ""):
            return {field_name: False}

        return {field_name: field_value or False}

    def show_success_msg(self, counter, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def read_xls_book(self):
        book = xlrd.open_workbook(file_contents=base64.decodebytes(self.file))
        sheet = book.sheet_by_index(0)
        # emulate Sheet.get_rows for pre-0.9.4
        values_sheet = []
        for rowx, row in enumerate(map(sheet.row, range(sheet.nrows)), 1):
            values = []
            for colx, cell in enumerate(row, 1):
                if cell.ctype is xlrd.XL_CELL_NUMBER:
                    is_float = cell.value % 1 != 0.0
                    values.append(
                        str(cell.value) if is_float else str(int(cell.value)))
                elif cell.ctype is xlrd.XL_CELL_DATE:
                    is_datetime = cell.value % 1 != 0.0
                    # emulate xldate_as_datetime for pre-0.9.3
                    dt = datetime.datetime(*xlrd.xldate.xldate_as_tuple(
                        cell.value, book.datemode))
                    values.append(
                        dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT
                                    ) if is_datetime else dt.
                        strftime(DEFAULT_SERVER_DATE_FORMAT))
                elif cell.ctype is xlrd.XL_CELL_BOOLEAN:
                    values.append(u'True' if cell.value else u'False')
                elif cell.ctype is xlrd.XL_CELL_ERROR:
                    raise ValueError(
                        _("Invalid cell value at row %(row)s, column %(col)s: %(cell_value)s"
                          ) % {
                              'row':
                              rowx,
                              'col':
                              colx,
                              'cell_value':
                              xlrd.error_text_from_code.get(
                                  cell.value,
                                  _("unknown error code %s") % cell.value)
                        })
                else:
                    values.append(cell.value)
            values_sheet.append(values)
        return values_sheet

    def import_journal_item_apply(self):
        ''' .............. import Journal Item in Journal Entry Using CSV and EXCEL ............'''
        journal_obj = self.env['account.move']
        ir_model_fields_obj = self.env['ir.model.fields']
        if self and self.file and self.env.context.get('sh_journal_entry_id', False):
            if self.import_type == 'csv' or self.import_type == 'excel':
                line_list = []
                counter = 1
                skipped_line_no = {}
                completed_records = 0
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    values = []
                    if self.import_type == 'csv':
                        file = str(
                            base64.decodebytes(self.file).decode('utf-8'))
                        values = csv.reader(file.splitlines())

                    elif self.import_type == 'excel':
                        values = self.read_xls_book()
                    skip_header = True
                    for row in values:
                        try:
                            if skip_header:
                                skip_header = False
                                for i in range(8, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "account.move.line"),
                                        ("name", "=", name_field),
                                        ("store", "=", True),
                                    ], limit=1)

                                    if search_field:
                                        field_dic = {
                                            'name': name_field,
                                            'ttype': search_field.ttype,
                                            'required': search_field.required,
                                            'name_m2o': name_m2o
                                        }
                                        row_field_dic.update({i: field_dic})
                                    else:
                                        row_field_error_dic.update(
                                            {row[i]: " - field not found"})
                                counter = counter + 1
                                continue
                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res

                            if row[0] not in (None, ""):
                                vals = {}
                                domain = []

                                search_account = self.env['account.account'].search(
                                    [('code', '=', row[0])], limit=1)
                                if search_account:
                                    vals.update(
                                        {'account_id': search_account.id})
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Account not found. "
                                    counter = counter + 1
                                    continue
                                search_partner = False
                                if row[1] not in (None, ""):

                                    search_partner = self.env["res.partner"]

                                    if self.sh_partner_by == 'name':
                                        domain += [('name',
                                                    '=', row[1])]
                                    if self.sh_partner_by == 'ref':
                                        domain += [('ref',
                                                    '=', row[1])]
                                    if self.sh_partner_by == 'id':
                                        domain += [('id', '=', row[1])]

                                    search_partner = search_partner.search(
                                        domain, limit=1)

                                    if search_partner:
                                        vals.update(
                                            {'partner_id': search_partner.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Partner not found. "
                                        counter = counter + 1
                                        continue

                                if row[2] not in (None, ""):
                                    vals.update({'name': row[2]})

                                if row[3] not in (None, ""):
                                    names = row[3].split(',')
                                    analytic_dic = {}
                                    for name in names:
                                        search_analytic_acccount = self.env['account.analytic.account'].sudo().search([('name', '=', name)
                                                                                                                       ])
                                        if search_analytic_acccount:
                                            analytic_dic[str(
                                                search_analytic_acccount.id)] = 100
                                    if analytic_dic:
                                        vals.update(
                                            {'analytic_distribution': analytic_dic})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Analytic Account not found. "
                                        counter = counter + 1
                                        continue

                                if row[4] not in (None, ""):
                                    vals.update(
                                        {'amount_currency': float(row[4])})
                                else:
                                    vals.update({'amount_currency': 0})

                                if row[5] not in (None, ""):
                                    search_currency = self.env['res.currency'].search(
                                        [('name', '=', row[5])], limit=1)
                                    if search_currency:
                                        vals.update(
                                            {'currency_id': search_currency.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Currency not found. "
                                        counter = counter + 1
                                        continue

                                if row[6] not in (None, ""):
                                    vals.update({'debit': float(row[6])})
                                else:
                                    vals.update({'debit': 0.0})

                                if row[7] not in (None, ""):
                                    vals.update({'credit': float(row[7])})
                                else:
                                    vals.update({'credit': 0.0})

                                line_list.append((0, 0, vals))
                                counter = counter + 1

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Account is empty. "
                                counter = counter + 1
                            is_any_error_in_dynamic_field = False
                            for k_row_index, v_field_dic in row_field_dic.items():

                                field_name = v_field_dic.get("name")
                                field_ttype = v_field_dic.get("ttype")
                                field_value = row[k_row_index]
                                field_required = v_field_dic.get("required")
                                field_name_m2o = v_field_dic.get("name_m2o")

                                dic = self.validate_field_value(
                                    field_name, field_ttype, field_value, field_required, field_name_m2o)
                                if dic.get("error", False):
                                    skipped_line_no[str(counter)] = dic.get(
                                        "error")
                                    is_any_error_in_dynamic_field = True
                                    break
                                else:
                                    vals.update(dic)
                            if is_any_error_in_dynamic_field:
                                counter = counter + 1
                                continue

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue
                    if len(skipped_line_no) == 0:
                        move_id = journal_obj.browse(
                            self.env.context.get('sh_journal_entry_id'))
                        move_id.write({'line_ids': line_list})
                        completed_records = (
                            counter - len(skipped_line_no)) - 2
                    else:
                        completed_records = 0

                except Exception as e:
                    raise UserError(
                        _("Sorry, Your file does not match with our format " + ustr(e)))

                if counter > 1:
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
