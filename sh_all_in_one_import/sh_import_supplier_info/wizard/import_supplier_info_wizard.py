# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import logging
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


_logger = logging.getLogger(__name__)


class ImportSupplierInforWizard(models.TransientModel):
    _name = "import.supplier.info.wizard"
    _description = "Import Supplier Info Wizard"

    @api.model
    def default_company(self):
        return self.env.company

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)

    product_model = fields.Selection([
        ('pro_var', 'Product Variants'),
        ('pro_tmpl', 'Product Template')
    ], default="pro_var", string="Product Model", required=True)

    product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")
    method = fields.Selection(
        [('create', "Create Supplier Info"), ('update', 'Create or Update Supplier Info')], default="create", string="Method")
    company_id = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)

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
        name_relational_model = self.env['product.supplierinfo'].fields_get()[
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
        name_relational_model = self.env['product.supplierinfo'].fields_get()[
            field_name]['relation']
        record = self.env[name_relational_model].sudo().search([
            (field_name_m2o, '=', field_value)
        ], limit=1)
        return {field_name: record.id if record else False}

    def validate_field_text(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        return {field_name: field_value or False}

    def validate_field_integer(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        return {field_name: field_value or False}

    def validate_field_float(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        return {field_name: field_value or False}

    def validate_field_char(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
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
        selection_key_value_list = self.env['product.supplierinfo'].sudo(
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

    def import_supplier_info_apply(self):
        '''-----------Import Supplier Info Using CSV or EXCEL ---------'''
        supplier_info_obj = self.env['product.supplierinfo']
        ir_model_fields_obj = self.env['ir.model.fields']
        if self and self.file:
            if self.import_type == 'csv' or self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}

                try:
                    values = []
                    if self.import_type == 'csv':
                        # For CSV
                        file = str(
                            base64.decodebytes(self.file).decode('utf-8'))
                        values = csv.reader(file.splitlines())

                    elif self.import_type == 'excel':
                        # For EXCEL
                        values = self.read_xls_book()
                    skip_header = True
                    for row in values:

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

                            if row[0] not in (None, "") and row[1] not in (None, ""):
                                vals = {}

                                field_nm = ''
                                if self.product_model == 'pro_tmpl':
                                    if self.product_by == 'name':
                                        field_nm = 'name'
                                    elif self.product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.product_by == 'barcode':
                                        field_nm = 'barcode'
                                elif self.product_model == 'pro_var':
                                    if self.product_by == 'name':
                                        field_nm = 'sh_display_name'
                                    elif self.product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.product_by == 'barcode':
                                        field_nm = 'barcode'
                                product_obj = False
                                product_field_nm = 'product_id'
                                if self.product_model == 'pro_var':
                                    product_obj = self.env["product.product"]
                                    product_field_nm = 'product_id'
                                else:
                                    product_obj = self.env["product.template"]
                                    product_field_nm = 'product_tmpl_id'
                                search_product = product_obj.search(
                                    [(field_nm, '=', row[0])], limit=1)
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
                                    'company_id': self.company_id.id,
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
                                # if vals:

                                #     # Pricelist Add Or Update Options
                                #     if self.method == 'create':
                                #         supplier_info_obj = supplier_info_obj.sudo().create(vals)

                                #     if self.method == 'update':

                                #         supplier_info_obj = self.env['product.supplierinfo'].search(
                                #             [('product_tmpl_id', '=', search_product.id), ('partner_id', '=', search_vendor.id)])

                                #         if supplier_info_obj:
                                #             supplier_info_obj.write(vals)

                                #         if not supplier_info_obj:
                                #             supplier_info_obj = supplier_info_obj.sudo().create(vals)

                                if supplier_info_obj:
                                    counter = counter + 1

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product or Vendor is empty. "
                                counter = counter + 1

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception as e:
                    raise UserError(
                        _("Sorry, Your file does not match with our format " + ustr(e)))

                if counter > 1:
                    completed_records = (
                        counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
