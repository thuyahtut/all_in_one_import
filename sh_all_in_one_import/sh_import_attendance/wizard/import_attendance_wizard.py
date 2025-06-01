# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
import pytz
from odoo.tools import ustr
import datetime
import logging
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)


class ImportAttendanceWizard(models.TransientModel):
    _name = "import.attendance.wizard"
    _description = "Import Attendance Wizard"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    attendance_by = fields.Selection([('employee_id', 'Employee ID'), (
        'badge', 'Badge')], default="employee_id", string="Attendance Import Type", required=True)
    file = fields.Binary(string="File", required=True)

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
            name_relational_model = self.env['hr.attendance'].fields_get()[
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
            name_relational_model = self.env['hr.attendance'].fields_get()[
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
        selection_key_value_list = self.env['hr.attendance'].sudo(
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

    def import_attendance_apply(self):

        hr_attendance_obj = self.env['hr.attendance']
        ir_model_fields_obj = self.env['ir.model.fields']
        # perform import lead
        if self and self.file:
            # For CSV
            if self.import_type == 'csv' or self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
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
                                for i in range(3, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "hr.attendance"),
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
                            vals = {}
                            if self.attendance_by == 'badge':
                                badge = False
                                if row[0] != '':
                                    badge = self.env['hr.employee'].sudo().search(
                                        [('barcode', '=', row[0])], limit=1)
                                    if badge:
                                        badge = badge.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Badge not found. "
                                        counter = counter + 1
                                        continue
                                check_in_time = None
                                if row[1] != '':
                                    if row[1]:
                                        check_in_time = row[1]
                                        local = pytz.timezone(self.env.user.tz)
                                        naive = datetime.datetime.strptime(check_in_time, DEFAULT_SERVER_DATETIME_FORMAT)
                                        local_dt = local.localize(naive, is_dst=None)
                                        utc_dt = local_dt.astimezone(pytz.utc)
                                        check_in_time = utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Check in Date and Time not found. "
                                        counter = counter + 1
                                        continue
                                check_out_time = None
                                if row[2] != '':
                                    if row[2]:
                                        check_out_time = row[2]
                                        local = pytz.timezone(self.env.user.tz)
                                        naive = datetime.datetime.strptime(check_out_time, DEFAULT_SERVER_DATETIME_FORMAT)
                                        local_dt = local.localize(naive, is_dst=None)
                                        utc_dt = local_dt.astimezone(pytz.utc)
                                        check_out_time = utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Check out Date and Time not found. "
                                        counter = counter + 1
                                        continue
                                vals.update({
                                    'employee_id': badge,
                                    'check_in': check_in_time,
                                    'check_out': check_out_time,
                                    })
                            elif self.attendance_by == 'employee_id':
                                employee_id = False
                                if row[0] != '':
                                    employee_id = self.env['hr.employee'].sudo().search(
                                        [('id', '=', int(row[0]))], limit=1)
                                    if employee_id:
                                        employee_id = employee_id.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Employee not found. "
                                        counter = counter + 1
                                        continue
                                check_in_time = None
                                if row[1] != '':
                                    if row[1]:
                                        check_in_time = row[1]
                                        local = pytz.timezone(self.env.user.tz)
                                        naive = datetime.datetime.strptime(check_in_time, DEFAULT_SERVER_DATETIME_FORMAT)
                                        local_dt = local.localize(naive, is_dst=None)
                                        utc_dt = local_dt.astimezone(pytz.utc)
                                        check_in_time = utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Check in Date and Time not found. "
                                        counter = counter + 1
                                        continue
                                check_out_time = None
                                if row[2] != '':
                                    if row[2]:
                                        check_out_time = row[2]
                                        local = pytz.timezone(self.env.user.tz)
                                        naive = datetime.datetime.strptime(check_out_time, DEFAULT_SERVER_DATETIME_FORMAT)
                                        local_dt = local.localize(naive, is_dst=None)
                                        utc_dt = local_dt.astimezone(pytz.utc)
                                        check_out_time = utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Check out Date and Time not found. "
                                        counter = counter + 1
                                        continue
                                vals.update({
                                    'employee_id': employee_id,
                                    'check_in': check_in_time,
                                    'check_out': check_out_time,
                                    })
                            is_any_error_in_dynamic_field = False
                            for k_row_index, v_field_dic in row_field_dic.items():

                                field_name = v_field_dic.get("name")
                                field_ttype = v_field_dic.get("ttype")
                                field_value = row[k_row_index]
                                field_required = v_field_dic.get(
                                    "required")
                                field_name_m2o = v_field_dic.get(
                                    "name_m2o")

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

                            hr_attendance_obj.create(vals)
                            counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))
                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(completed_records,
                                                skipped_line_no)
                    return res