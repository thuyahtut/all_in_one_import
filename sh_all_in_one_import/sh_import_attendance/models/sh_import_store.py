# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
from datetime import datetime
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging
import pytz
_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_attendance(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_attendance':
            value = True
        return value

    import_attendance_type = fields.Selection(related='base_id.import_attendance_type',readonly=False, string=" Import File Type")
    attendance_by = fields.Selection(related='base_id.attendance_by',readonly=False, string="Attendance Import Type")
    sh_import_attendance_boolean = fields.Boolean(
        "Import Attendance Boolean", default=check_sh_import_attendance)

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

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_attendance':
            self.import_attendance(record)
        return res

    def import_attendance(self,record):
        self = record
        hr_attendance_obj = self.env['hr.attendance']
        ir_model_fields_obj = self.env['ir.model.fields']
        # # perform import Attendance Image
        if self and self.sh_file:

            if self.import_attendance_type == 'csv' or self.import_attendance_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                count=0
                try:
                    if self.import_attendance_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.import_attendance_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    dic = {}
                    till = length_reader
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    for row in range(self.count_start_from - 1, till):
                        try:
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
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
                                        naive = datetime.strptime(check_in_time, DEFAULT_SERVER_DATETIME_FORMAT)
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
                                        naive = datetime.strptime(check_out_time, DEFAULT_SERVER_DATETIME_FORMAT)
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
                                        naive = datetime.strptime(check_in_time, DEFAULT_SERVER_DATETIME_FORMAT)
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
                                        naive = datetime.strptime(check_out_time, DEFAULT_SERVER_DATETIME_FORMAT)
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
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 1
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
                        self.state = 'done'
                    else:
                        self.received_error = True
                        self.create_store_logs(
                            completed_records, skipped_line_no)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done'
