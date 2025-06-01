# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from email.policy import default
from operator import length_hint
from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from datetime import datetime
from odoo.tools import ustr
import requests
import codecs


class ImportSupplierInfo(models.Model):
    _inherit = "sh.import.store"

    def check_sh_supplier_info(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_supplier_info':
            value = True
        return value

    sh_import_type_supplier = fields.Selection(
        related="base_id.sh_import_type_supplier", readonly=False, string="Import File Type", required=True)
    sh_method_supplier = fields.Selection(related="base_id.sh_method_supplier",
                                          readonly=False, string="Method", required=True)
    sh_product_by_supplier = fields.Selection(
        related="base_id.sh_product_by_supplier", readonly=False, string="Product By", required=True)
    sh_product_model_supplier = fields.Selection(
        related="base_id.sh_product_model_supplier", readonly=False, string="Product Model", required=True)
    sh_import_supplier_info_boolean = fields.Boolean(
        "Supplier Info Boolean", default=check_sh_supplier_info)
    sh_company_id_supplier = fields.Many2one(
        related="base_id.sh_company_id_supplier", readonly=False, string="Company", required=True)

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

    def perform_the_action(self, record):
        res = super(ImportSupplierInfo, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_supplier_info':
            self.import_supplier_info(record)
        return res

    def import_supplier_info(self, record):
        self = record
        supplier_info_obj = self.env['product.supplierinfo']
        ir_model_fields_obj = self.env['ir.model.fields']
        # perform import lead
        if self and self.sh_file:
            # For CSV
            if self.sh_import_type_supplier == 'csv':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}

                try:
                    sh_file = str(base64.decodebytes(
                        self.sh_file).decode('utf-8'))
                    length_r = csv.reader(sh_file.splitlines())
                    length_reader = len(list(length_r))
                    myreader = csv.reader(sh_file.splitlines())
                    myreader = list(myreader)
                    count = 0
                    skip_header = True
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    for row in range(self.count_start_from - 1, till):
                        row = myreader[row]
                        try:
                            if skip_header:
                                skip_header = False
                                for i in range(9, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "product.supplierinfo"),
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
                            if self.sh_method_supplier == 'create':
                                if row[0] not in (None, "") and row[1] not in (None, ""):
                                    vals = {}

                                    field_nm = ''
                                    if self.sh_product_model_supplier == 'pro_tmpl':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    elif self.sh_product_model_supplier == 'pro_var':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'sh_display_name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    product_obj = False
                                    product_field_nm = 'product_id'
                                    if self.sh_product_model_supplier == 'pro_var':
                                        product_obj = self.env["product.product"]
                                        product_field_nm = 'product_id'
                                    else:
                                        product_obj = self.env["product.template"]
                                        product_field_nm = 'product_tmpl_id'

                                    search_product = product_obj.search(
                                        [(field_nm, '=', row[0].strip())], limit=1)
                                    if search_product:
                                        vals.update(
                                            {product_field_nm: search_product.id})
                                        if product_field_nm == 'product_id' and search_product.product_tmpl_id:
                                            vals.update(
                                                {'product_tmpl_id': search_product.product_tmpl_id.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue
                                    search_vendor = self.env['res.partner'].search(
                                        [('name', '=', row[1])], limit=1)
                                    if search_vendor:
                                        vals.update(
                                            {'partner_id': search_vendor.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Vendor not found or is not a supplier. "
                                        counter = counter + 1
                                        continue
                                    if row[2] not in (None, ""):
                                        vals.update({'product_name': row[2]})
                                    if row[3] not in (None, ""):
                                        vals.update({'product_code': row[3]})
                                    if row[4] not in (None, ""):
                                        vals.update({'delay': row[4]})
                                    else:
                                        vals.update({'delay': 1})
                                    if row[5] not in (None, ""):
                                        vals.update({'min_qty': row[5]})
                                    else:
                                        vals.update({'min_qty': 0.00})
                                    if row[6] not in (None, ""):
                                        vals.update({'price': row[6]})
                                    else:
                                        vals.update({'price': 0.00})
                                    if row[7] not in (None, ""):
                                        cd = row[7]
                                        vals.update({
                                            'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                        })
                                    if row[8] not in (None, ""):
                                        cd = row[8]
                                        vals.update({
                                            'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                        })
                                    vals.update({
                                        'company_id': self.sh_company_id_supplier.id,
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

                                    supplier_info_obj.create(vals)
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product or Vendor is empty. "
                                    counter = counter + 1
                            else:
                                if row[0] not in (None, "") and row[1] not in (None, ""):
                                    field_nm = ''
                                    vals = {}
                                    if self.sh_product_model_supplier == 'pro_tmpl':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    elif self.sh_product_model_supplier == 'pro_var':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'sh_display_name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    product_obj = False
                                    product_field_nm = 'product_id'
                                    if self.sh_product_model_supplier == 'pro_var':
                                        product_obj = self.env["product.product"]
                                        product_field_nm = 'product_id'
                                        search_product = product_obj.search(
                                            [(field_nm, '=', row[0].strip())], limit=1)
                                    else:
                                        product_obj = self.env["product.template"]
                                        product_field_nm = 'product_tmpl_id'
                                        search_product_template = product_obj.search(
                                            [(field_nm, '=', row[0].strip())], limit=1)
                                        search_product = self.env['product.product'].search(
                                            [('product_tmpl_id', '=', search_product_template.id)], limit=1)

                                    if search_product:
                                        search_vendor = self.env['res.partner'].search(
                                            [('name', '=', row[1])], limit=1)
                                        if search_vendor:
                                            search_seller_id = supplier_info_obj.search(
                                                [('product_id', '=', search_product.name), ('partner_id', '=', search_vendor.id)], limit=1)
                                            if search_seller_id:

                                                vals.update({
                                                    'product_id': search_product.id,
                                                    'product_tmpl_id': search_product.product_tmpl_id.id
                                                })
                                                if row[1] not in (None, ""):
                                                    vals.update({
                                                        'partner_id': search_vendor.id
                                                    })
                                                if row[2] not in (None, ""):
                                                    vals.update(
                                                        {'product_name': row[2]})
                                                if row[3] not in (None, ""):
                                                    vals.update(
                                                        {'product_code': row[3]})
                                                if row[4] not in (None, ""):
                                                    vals.update(
                                                        {'delay': row[4]})
                                                if row[5] not in (None, ""):
                                                    vals.update(
                                                        {'min_qty': row[5]})
                                                if row[6] not in (None, ""):
                                                    vals.update(
                                                        {'price': row[6]})
                                                if row[7] not in (None, ""):
                                                    cd = row[7]
                                                    vals.update({
                                                        'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                if row[8] not in (None, ""):
                                                    cd = row[8]
                                                    vals.update({
                                                        'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                vals.update({
                                                    'company_id': self.sh_company_id_supplier.id,
                                                })
                                                is_any_error_in_dynamic_field = False
                                                for k_row_index, v_field_dic in row_field_dic.items():

                                                    field_name = v_field_dic.get(
                                                        "name")
                                                    field_ttype = v_field_dic.get(
                                                        "ttype")
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
                                                search_seller_id.write(
                                                    vals)
                                                counter = counter + 1
                                            else:
                                                if row[0] not in (None, ""):
                                                    vals.update({
                                                        'product_id': search_product.id,
                                                        'product_tmpl_id': search_product.product_tmpl_id.id
                                                    })
                                                if row[1] not in (None, ""):
                                                    vals.update({
                                                        'partner_id': search_vendor.id
                                                    })
                                                if row[2] not in (None, ""):
                                                    vals.update(
                                                        {'product_name': row[2]})
                                                if row[3] not in (None, ""):
                                                    vals.update(
                                                        {'product_code': row[3]})
                                                if row[4] not in (None, ""):
                                                    vals.update(
                                                        {'delay': row[4]})
                                                else:
                                                    vals.update({'delay': 1})
                                                if row[5] not in (None, ""):
                                                    vals.update(
                                                        {'min_qty': row[5]})
                                                else:
                                                    vals.update(
                                                        {'min_qty': 0.00})
                                                if row[6] not in (None, ""):
                                                    vals.update(
                                                        {'price': row[6]})
                                                else:
                                                    vals.update(
                                                        {'price': 0.00})
                                                if row[7] not in (None, ""):
                                                    cd = row[7]
                                                    vals.update({
                                                        'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                    cd = row[8]
                                                    vals.update({
                                                        'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                vals.update({
                                                    'company_id': self.sh_company_id_supplier.id,
                                                })
                                                is_any_error_in_dynamic_field = False
                                                for k_row_index, v_field_dic in row_field_dic.items():

                                                    field_name = v_field_dic.get(
                                                        "name")
                                                    field_ttype = v_field_dic.get(
                                                        "ttype")
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

                                                supplier_info_obj.create(vals)
                                                counter = counter + 1
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Vendor not found in the Product "
                                            counter = counter + 1
                                            continue
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product or Vendor is empty. "
                                    counter = counter + 1
                                    continue

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue
                        count += 1
                        self.current_count += 1
                        if count == self.import_limit:
                            self.count_start_from += self.import_limit
                    if self.current_count >= (length_reader-1):
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done'
                            self.count_start_from = 1
                            self.current_count = 0

                except Exception as e:
                    raise UserError(
                        _("Sorry, Your file does not match with our format " + ustr(e)))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
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

            # For Excel
            if self.sh_import_type_supplier == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.sh_file))
                    sheet = wb.sheet_by_index(0)
                    count = 0
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > sheet.nrows:
                        till = sheet.nrows
                    else:
                        till = self.count_start_from+self.import_limit
                    skip_header = True
                    for row in range(self.count_start_from-1, till):
                        try:
                            if skip_header:
                                skip_header = False

                                for i in range(9, sheet.ncols):
                                    name_field = sheet.cell(row, i).value
                                    name_m2o = False
                                    if '@' in sheet.cell(row, i).value:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "product.supplierinfo"),
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
                                            {sheet.cell(row, i).value: " - field not found"})

                                if row_field_error_dic:
                                    res = self.show_success_msg(
                                        0, row_field_error_dic)
                                    return res

                                counter = counter + 1
                                continue

                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res

                            if self.sh_method_supplier == "create":
                                if sheet.cell(row, 0).value not in (None, "") and sheet.cell(row, 1).value not in (None, ""):
                                    vals = {}
                                    field_nm = ''
                                    if self.sh_product_model_supplier == 'pro_tmpl':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    elif self.sh_product_model_supplier == 'pro_var':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'sh_display_name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    product_obj = False
                                    product_field_nm = 'product_id'
                                    if self.sh_product_model_supplier == 'pro_var':
                                        product_obj = self.env["product.product"]
                                        product_field_nm = 'product_id'
                                    else:
                                        product_obj = self.env["product.template"]
                                        product_field_nm = 'product_tmpl_id'

                                    search_product = product_obj.search(
                                        [(field_nm, '=', sheet.cell(row, 0).value.strip())], limit=1)
                                    if search_product:
                                        vals.update(
                                            {product_field_nm: search_product.id})
                                        if product_field_nm == 'product_id' and search_product.product_tmpl_id:
                                            vals.update(
                                                {'product_tmpl_id': search_product.product_tmpl_id.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue

                                    search_vendor = self.env['res.partner'].search(
                                        [('name', '=', sheet.cell(row, 1).value.strip())], limit=1)
                                    if search_vendor:
                                        vals.update(
                                            {'partner_id': search_vendor.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Vendor not found or is not a supplier. "
                                        counter = counter + 1
                                        continue

                                    if sheet.cell(row, 2).value not in (None, ""):
                                        vals.update(
                                            {'product_name': sheet.cell(row, 2).value})
                                    if sheet.cell(row, 3).value not in (None, ""):
                                        vals.update(
                                            {'product_code': sheet.cell(row, 3).value})
                                    if sheet.cell(row, 4).value not in (None, ""):
                                        vals.update(
                                            {'delay': sheet.cell(row, 4).value})
                                    else:
                                        vals.update({'delay': 1})
                                    if sheet.cell(row, 5).value not in (None, ""):
                                        vals.update(
                                            {'min_qty': sheet.cell(row, 5).value})
                                    else:
                                        vals.update({'min_qty': 0.00})
                                    if sheet.cell(row, 6).value not in (None, ""):
                                        vals.update(
                                            {'price': sheet.cell(row, 6).value})
                                    else:
                                        vals.update({'price': 0.00})
                                    if sheet.cell(row, 7).value not in (None, ""):
                                        cd = sheet.cell(row, 7).value
                                        vals.update({
                                            'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                        })
                                    if sheet.cell(row, 8).value not in (None, ""):
                                        cd = sheet.cell(row, 8).value
                                        vals.update({
                                            'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                        })
                                    vals.update({
                                        'company_id': self.sh_company_id_supplier.id,
                                    })
                                    is_any_error_in_dynamic_field = False
                                    for k_row_index, v_field_dic in row_field_dic.items():

                                        field_name = v_field_dic.get("name")
                                        field_ttype = v_field_dic.get("ttype")
                                        field_value = sheet.cell(
                                            row, k_row_index).value
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
                                    supplier_info_obj.create(vals)
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product or Vendor is empty. "
                                    counter = counter + 1
                            else:
                                if sheet.cell(row, 0).value not in (None, "") and sheet.cell(row, 1).value not in (None, ""):
                                    field_nm = ''
                                    vals = {}
                                    if self.sh_product_model_supplier == 'pro_tmpl':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    elif self.sh_product_model_supplier == 'pro_var':
                                        if self.sh_product_by_supplier == 'name':
                                            field_nm = 'sh_display_name'
                                        elif self.sh_product_by_supplier == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_product_by_supplier == 'barcode':
                                            field_nm = 'barcode'
                                    product_obj = False
                                    product_field_nm = 'product_id'
                                    if self.sh_product_model_supplier == 'pro_var':
                                        product_obj = self.env["product.product"]
                                        product_field_nm = 'product_id'

                                        search_product = product_obj.search(
                                            [(field_nm, '=', sheet.cell(row, 0).value.strip())], limit=1)

                                    else:
                                        product_obj = self.env["product.template"]
                                        product_field_nm = 'product_tmpl_id'

                                        search_product_template = product_obj.search(
                                            [(field_nm, '=', sheet.cell(row, 0).value.strip())], limit=1)

                                        search_product = self.env['product.product'].search(
                                            [('product_tmpl_id', '=', search_product_template.id)], limit=1)
                                    if search_product:
                                        search_vendor = self.env['res.partner'].search(
                                            [('name', '=', sheet.cell(row, 1).value.strip())], limit=1)
                                        if search_vendor:
                                            search_seller_id = supplier_info_obj.search(
                                                [('product_id', '=', search_product.name), ('partner_id', '=', search_vendor.id)], limit=1)
                                            if search_seller_id:
                                                if sheet.cell(row, 0).value not in (None, ""):
                                                    vals.update({
                                                        'product_id': search_product.id,
                                                        'product_tmpl_id': search_product.product_tmpl_id.id
                                                    })
                                                if sheet.cell(row, 1).value not in (None, ""):
                                                    vals.update({
                                                        'partner_id': search_vendor.id
                                                    })
                                                if sheet.cell(row, 2).value not in (None, ""):
                                                    vals.update(
                                                        {'product_name': sheet.cell(row, 2).value})
                                                if sheet.cell(row, 3).value not in (None, ""):
                                                    vals.update(
                                                        {'product_code': sheet.cell(row, 3).value})
                                                if sheet.cell(row, 4).value not in (None, ""):
                                                    vals.update(
                                                        {'delay': sheet.cell(row, 4).value})
                                                if sheet.cell(row, 5).value not in (None, ""):
                                                    vals.update(
                                                        {'min_qty': sheet.cell(row, 5).value})
                                                if sheet.cell(row, 6).value not in (None, ""):
                                                    vals.update(
                                                        {'price': sheet.cell(row, 6).value})
                                                if sheet.cell(row, 7).value not in (None, ""):
                                                    cd = sheet.cell(
                                                        row, 7).value
                                                    vals.update({
                                                        'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                if sheet.cell(row, 8).value not in (None, ""):
                                                    cd = sheet.cell(
                                                        row, 8).value
                                                    vals.update({
                                                        'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                vals.update({
                                                    'company_id': self.sh_company_id_supplier.id,
                                                })
                                                is_any_error_in_dynamic_field = False
                                                for k_row_index, v_field_dic in row_field_dic.items():

                                                    field_name = v_field_dic.get(
                                                        "name")
                                                    field_ttype = v_field_dic.get(
                                                        "ttype")
                                                    field_value = sheet.cell(
                                                        row, k_row_index).value
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
                                                search_seller_id.write(
                                                    vals)
                                            else:
                                                if sheet.cell(row, 0).value not in (None, ""):
                                                    vals.update({
                                                        'product_id': search_product.id,
                                                        'product_tmpl_id': search_product.product_tmpl_id.id
                                                    })
                                                if sheet.cell(row, 1).value not in (None, ""):
                                                    vals.update({
                                                        'partner_id': search_vendor.id
                                                    })
                                                if sheet.cell(row, 2).value not in (None, ""):
                                                    vals.update(
                                                        {'product_name': sheet.cell(row, 2).value})
                                                if sheet.cell(row, 3).value not in (None, ""):
                                                    vals.update(
                                                        {'product_code': sheet.cell(row, 3).value})
                                                if sheet.cell(row, 4).value not in (None, ""):
                                                    vals.update(
                                                        {'delay': sheet.cell(row, 4).value})
                                                else:
                                                    vals.update({'delay': 1})
                                                if sheet.cell(row, 5).value not in (None, ""):
                                                    vals.update(
                                                        {'min_qty': sheet.cell(row, 5).value})
                                                else:
                                                    vals.update(
                                                        {'min_qty': 0.00})
                                                if sheet.cell(row, 6).value not in (None, ""):
                                                    vals.update(
                                                        {'price': sheet.cell(row, 6).value})
                                                else:
                                                    vals.update(
                                                        {'price': 0.00})
                                                if sheet.cell(row, 7).value not in (None, ""):
                                                    cd = sheet.cell(
                                                        row, 7).value
                                                    vals.update({
                                                        'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                    cd = sheet.cell(
                                                        row, 8).value
                                                    vals.update({
                                                        'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                                    })
                                                vals.update({
                                                    'company_id': self.sh_company_id_supplier.id,
                                                })
                                                is_any_error_in_dynamic_field = False
                                                for k_row_index, v_field_dic in row_field_dic.items():

                                                    field_name = v_field_dic.get(
                                                        "name")
                                                    field_ttype = v_field_dic.get(
                                                        "ttype")
                                                    field_value = sheet.cell(
                                                        row, k_row_index).value
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
                                                supplier_info_obj.create(
                                                    vals)
                                                counter = counter + 1
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Vendor not found in the Product "
                                            counter = counter + 1
                                            continue
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product or Vendor is empty. "
                                    counter = counter + 1
                                    continue
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue
                        count += 1
                        self.current_count += 1
                        if count == self.import_limit:
                            self.count_start_from += self.import_limit
                            break
                    if self.current_count >= (sheet.nrows-1):
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done'
                        self.count_start_from = 1
                        self.current_count = 0
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your excel file does not match with our format " + ustr(e)))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
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