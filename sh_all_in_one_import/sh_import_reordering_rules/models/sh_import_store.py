# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from email.policy import default
from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from datetime import datetime
from odoo.tools import ustr
import logging
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_reordering_rule(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_reordering_rules':
            value = True
        return value

    sh_import_reordering_rule_type = fields.Selection(
        related="base_id.sh_import_reordering_rule_type", readonly=False, string="  Import File Type ", required=True)
    sh_import_reordering_rule_method = fields.Selection(
        related="base_id.sh_import_reordering_rule_method", readonly=False, string=" Method", required=True)
    sh_import_reordering_rule_product_by = fields.Selection(string="Product By", required=True,readonly=False,related='base_id.sh_import_reordering_rule_product_by')
    sh_import_reordering_rule_boolean = fields.Boolean(
        "Import Reordering Rule Boolean", default=check_sh_import_reordering_rule)
    sh_company_id_reordering_rule = fields.Many2one(
        related="base_id.sh_company_id_reordering_rule", readonly=False, string="Company", required=True)

    def create_store_logs(self, counter, skipped_line_no):
        dic_msg = str(counter) + " Records imported successfully"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        self.env['sh.import.log'].create({
            'message': dic_msg,
            'datetime': datetime.now(),
            'sh_store_id': self.id
        })

    def read_xls_book(self):
        book = xlrd.open_workbook(file_contents=base64.decodebytes(self.sh_file))
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

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_reordering_rules':
            self.import_reordering_rule(record)
        return res

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
            name_relational_model = self.env['stock.warehouse.orderpoint'].fields_get()[
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
            name_relational_model = self.env['stock.warehouse.orderpoint'].fields_get()[
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
        selection_key_value_list = self.env['stock.warehouse.orderpoint'].sudo(
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
    
    def validate_field_html(self, field_name, field_ttype, field_value,
                                field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: Markup(field_value) or False}

    def import_reordering_rule(self,record):
        self = record
        reordering_rule_obj = self.env['stock.warehouse.orderpoint']
        ir_model_fields_obj = self.env['ir.model.fields']

        # # perform import task
        if self and self.sh_file:

            if self.sh_import_reordering_rule_type == 'csv' or self.sh_import_reordering_rule_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                count=0
                try:
                    if self.sh_import_reordering_rule_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_reordering_rule_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
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
                                
                                for i in range(4, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "stock.warehouse.orderpoint"),
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


                            # ====================================================
                            # check if any error in dynamic field
                            # ====================================================

                            if row_field_error_dic:
                                self.create_store_logs(0, row_field_error_dic)
                                self.state = 'error'
                                break
                            if row[0] not in (None, ""):
                                vals = {}

                                field_nm = 'name'
                                if self.sh_import_reordering_rule_product_by == 'name':
                                    field_nm = 'name'
                                elif self.sh_import_reordering_rule_product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.sh_import_reordering_rule_product_by == 'barcode':
                                    field_nm = 'barcode'

                                search_product = self.env['product.product'].search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_product and search_product.type == 'product':
                                    vals.update(
                                        {'product_id': search_product.id})

                                    if row[1] not in (None, ""):
                                        vals.update(
                                            {'product_min_qty': row[1]})
                                    else:
                                        vals.update({'product_min_qty': 0.0})

                                    if row[2] not in (None, ""):
                                        vals.update(
                                            {'product_max_qty': row[2]})
                                    else:
                                        vals.update({'product_max_qty': 0.0})

                                    if row[3] not in (None, ""):
                                        vals.update({'qty_multiple': row[3]})
                                    else:
                                        vals.update({'qty_multiple': 1.0})

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

                                    if self.sh_import_reordering_rule_method == 'create':
                                        search_reordering_rule = reordering_rule_obj.search(
                                            [('product_id', '=', search_product.id), ('company_id', '=', self.env.company.id)], limit=1)
                                        if search_reordering_rule:
                                            skipped_line_no[str(
                                                counter)] = " - A replenishment rule already exists for this product on this location."
                                            counter = counter + 1
                                            continue
                                        else:
                                            reordering_rule_obj.create(vals)
                                    else:
                                        search_reordering_rule = reordering_rule_obj.search(
                                            [('product_id', '=', search_product.id), ('company_id', '=', self.env.company.id)], limit=1)
                                        if search_reordering_rule:
                                            search_reordering_rule.write(vals)
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - No Reordering Rule is found for this product "
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product not found or it's not a Stockable Product. "
                                    counter = counter + 1
                                    continue
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product is empty. "
                                counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
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
