# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import requests
import codecs
import logging
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime

_logger = logging.getLogger(__name__)


class ImportProductTmplMbWizard(models.TransientModel):
    _name = "import.product.tmpl.mb.wizard"
    _description = "Import product template wizard"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    method = fields.Selection([
        ('create', 'Create Product'),
        ('write', 'Create or Update Product')
    ], default="create", string="Method", required=True)

    product_update_by = fields.Selection([
        ('barcode', 'Barcode'),
        ('int_ref', 'Internal Reference'),
    ], default='barcode', string="Product Update By", required=True)

    update_existing = fields.Boolean(string="Remove Existing")

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
            name_relational_model = self.env['product.template'].fields_get()[
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
            name_relational_model = self.env['product.template'].fields_get()[
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
        selection_key_value_list = self.env['product.template'].sudo(
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

    def import_product_tmpl_apply(self):
        ''' .................. Import Product Template Using CSV and EXCEL......................'''
        product_tmpl_obj = self.env['product.template']
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

                                for i in range(20, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "product.template"),
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

                            if row[0].strip() not in (None, ""):
                                vals = {}
                                if row[1] not in ("",None) and row[1].strip() == 'FALSE':
                                    vals.update({
                                        'sale_ok':False
                                    })
                                elif row[1] not in ("",None) and row[1].strip() == 'TRUE':
                                    vals.update({
                                        'sale_ok':True
                                    })
                                if row[2] not in ("",None) and row[2].strip() == 'FALSE':
                                    vals.update({
                                        'purchase_ok':False
                                    })
                                elif row[2] not in ("",None) and row[2].strip() == 'TRUE':
                                    vals.update({
                                        'purchase_ok':True
                                    })
                                if row[3].strip() not in ("",False,None) and row[3].strip() == 'Service':
                                    vals.update({
                                        'type': 'service',
                                    })
                                elif row[3].strip() not in ("",False,None) and row[3].strip() == 'Storable Product' or row[3].strip() == 'Stockable Product':
                                    vals.update({
                                        'type': 'product',
                                    })
                                elif row[3].strip() not in ("",False,None) and row[3].strip() == 'Consumable':
                                    vals.update({
                                        'type': 'consu',
                                    })

                                categ_id = False
                                if row[4].strip() in (None, ""):
                                    search_category = self.env['product.category'].search(
                                        [('complete_name', '=', 'All')], limit=1)
                                    if search_category:
                                        categ_id = search_category.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Category - All not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_category = self.env['product.category'].search(
                                        [('complete_name', '=', row[4].strip())], limit=1)
                                    if search_category:
                                        categ_id = search_category.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Category not found. "
                                        counter = counter + 1
                                        continue

                                uom_id = False
                                if row[9].strip() in (None, ""):
                                    search_uom = self.env['uom.uom'].search(
                                        [('name', '=', 'Units')], limit=1)
                                    if search_uom:
                                        uom_id = search_uom.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Unit of Measure - Units not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_uom = self.env['uom.uom'].search(
                                        [('name', '=', row[9].strip())], limit=1)
                                    if search_uom:
                                        uom_id = search_uom.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Unit of Measure not found. "
                                        counter = counter + 1
                                        continue

                                uom_po_id = False
                                if row[10].strip() in (None, ""):
                                    search_uom_po = self.env['uom.uom'].search(
                                        [('name', '=', 'Units')], limit=1)
                                    if search_uom_po:
                                        uom_po_id = search_uom_po.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Purchase Unit of Measure - Units not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_uom_po = self.env['uom.uom'].search(
                                        [('name', '=', row[10].strip())], limit=1)
                                    if search_uom_po:
                                        uom_po_id = search_uom_po.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Purchase Unit of Measure not found. "
                                        counter = counter + 1
                                        continue

                                customer_taxes_ids_list = []
                                some_taxes_not_found = False
                                if row[13].strip() not in (None, ""):
                                    for x in row[13].split(','):
                                        x = x.strip()
                                        if x != '':
                                            search_customer_tax = self.env['account.tax'].search(
                                                [('name', '=', x)], limit=1)
                                            if search_customer_tax:
                                                customer_taxes_ids_list.append(
                                                    search_customer_tax.id)
                                            else:
                                                some_taxes_not_found = True
                                                skipped_line_no[str(
                                                    counter)] = " - Customer Taxes " + x + " not found. "
                                                break
                                if some_taxes_not_found:
                                    counter = counter + 1
                                    continue

                                vendor_taxes_ids_list = []

                                some_taxes_not_found = False
                                if row[14].strip() not in (None, ""):
                                    for x in row[14].split(','):
                                        x = x.strip()
                                        if x != '':
                                            search_vendor_tax = self.env['account.tax'].search(
                                                [('name', '=', x)], limit=1)
                                            if search_vendor_tax:
                                                vendor_taxes_ids_list.append(
                                                    search_vendor_tax.id)
                                            else:
                                                some_taxes_not_found = True
                                                skipped_line_no[str(
                                                    counter)] = " - Vendor Taxes " + x + " not found. "
                                                break

                                if some_taxes_not_found:
                                    counter = counter + 1
                                    continue

                                invoicing_policy = 'order'
                                if row[15].strip() == 'Delivered quantities':
                                    invoicing_policy = 'delivery'
                                if customer_taxes_ids_list:
                                    vals.update({
                                        'taxes_id': [(6, 0, customer_taxes_ids_list)],
                                    })
                                if vendor_taxes_ids_list:
                                    vals.update({
                                        'supplier_taxes_id': [(6, 0, vendor_taxes_ids_list)],
                                    })
                                if row[7] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'list_price': row[7],
                                    })
                                if row[8] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'standard_price': row[8],
                                    })
                                if row[11] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'weight': row[11],
                                    })
                                if row[12] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'volume': row[12],
                                    })
                                if row[16] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'description_sale': row[16],
                                    })
                                vals = {
                                    'name': row[0].strip(),
                                    'categ_id': categ_id,
                                    'uom_id': uom_id,
                                    'uom_po_id': uom_po_id,
                                    'invoice_policy': invoicing_policy,
                                }

                                if row[6].strip() not in (None, ""):
                                    barcode = row[6].strip()
                                    vals.update({'barcode': barcode})

                                if row[5].strip() not in (None, ""):
                                    default_code = row[5].strip()
                                    vals.update({'default_code': default_code})

                                if row[18].strip() not in (None, ""):
                                    image_path = row[18].strip()
                                    if "http://" in image_path or "https://" in image_path:
                                        try:
                                            r = requests.get(image_path)
                                            if r and r.content:
                                                image_base64 = base64.encodebytes(
                                                    r.content)
                                                vals.update(
                                                    {'image_1920': image_base64})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - URL not correct or check your image size. "
                                                counter = counter + 1
                                                continue
                                        except Exception as e:
                                            skipped_line_no[str(
                                                counter)] = " - URL not correct or check your image size " + ustr(e)
                                            counter = counter + 1
                                            continue
                                    else:
                                        try:
                                            with open(image_path, 'rb') as image:
                                                image.seek(0)
                                                binary_data = image.read()
                                                image_base64 = codecs.encode(
                                                    binary_data, 'base64')
                                                if image_base64:
                                                    vals.update(
                                                        {'image_1920': image_base64})
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Could not find the image or please make sure it is accessible to this user. "
                                                    counter = counter + 1
                                                    continue
                                        except Exception as e:
                                            skipped_line_no[str(
                                                counter)] = " - Could not find the image or please make sure it is accessible to this user " + ustr(e)
                                            counter = counter + 1
                                            continue

                                created_product_tmpl = False

                                # ===========================================================
                                # dynamic field logic start here
                                # ===========================================================

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
                                # ===========================================================
                                # dynamic field logic end here
                                # ===========================================================

                                if self.method == 'create':
                                    barcode_list = []
                                    if row[19].strip() not in (None, ""):
                                        exist_barcode=[]
                                        for x in row[19].split(','):
                                            x = x.strip()
                                            search_barcode = self.env['product.product'].search(
                                                ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                            if not search_barcode:
                                                if x != '':
                                                    barcode_vals = {
                                                        'name': x
                                                    }
                                                    barcode_list.append(
                                                        (0, 0, barcode_vals))
                                            else:
                                                exist_barcode.append(x)
                                        if exist_barcode:
                                            skipped_line_no[str(
                                                counter)] = " - Barcode already exist."
                                            counter = counter + 1
                                            continue
                                    if row[6].strip() in (None, ""):
                                        created_product_tmpl = product_tmpl_obj.create(
                                            vals)
                                        created_product_tmpl.barcode_line_ids = barcode_list
                                        counter = counter + 1
                                    else:
                                        search_product_tmpl = product_tmpl_obj.search(
                                            [('barcode', '=', row[6].strip())], limit=1)
                                        if search_product_tmpl:
                                            skipped_line_no[str(
                                                counter)] = " - Barcode already exist. "
                                            counter = counter + 1
                                            continue
                                        else:
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            created_product_tmpl.barcode_line_ids = barcode_list
                                            counter = counter + 1
                                elif self.method == 'write' and self.product_update_by == 'barcode':
                                    if row[6].strip() in (None, ""):
                                        created_product_tmpl = product_tmpl_obj.create(
                                            vals)
                                        counter = counter + 1
                                    else:
                                        search_product_tmpl = product_tmpl_obj.search(
                                            [('barcode', '=', row[6].strip())], limit=1)
                                        if search_product_tmpl:
                                            created_product_tmpl = search_product_tmpl
                                            search_product_tmpl.write(vals)
                                            counter = counter + 1
                                        else:
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            counter = counter + 1
                                elif self.method == 'write' and self.product_update_by == 'int_ref':
                                    search_product_tmpl = product_tmpl_obj.search(
                                        [('default_code', '=', row[5].strip())], limit=1)
                                    if search_product_tmpl:
                                        if row[6].strip() in (None, ""):
                                            created_product_tmpl = search_product_tmpl
                                            search_product_tmpl.write(vals)
                                            counter = counter + 1
                                        else:
                                            search_product_tmpl_bar = product_tmpl_obj.search(
                                                [('barcode', '=', row[6].strip())], limit=1)
                                            if search_product_tmpl_bar:
                                                skipped_line_no[str(
                                                    counter)] = " - Barcode already exist. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                created_product_tmpl = search_product_tmpl
                                                search_product_tmpl.write(vals)
                                                counter = counter + 1
                                    else:
                                        if row[6].strip() in (None, ""):
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            counter = counter + 1
                                        else:
                                            search_product_tmpl_bar = product_tmpl_obj.search(
                                                [('barcode', '=', row[6].strip())], limit=1)
                                            if search_product_tmpl_bar:
                                                skipped_line_no[str(
                                                    counter)] = " - Barcode already exist. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                created_product_tmpl = product_tmpl_obj.create(
                                                    vals)
                                                counter = counter + 1

                                if created_product_tmpl and self.method == 'write':
                                    barcode_list = []
                                    if not self.update_existing:
                                        if row[19].strip() not in (None, ""):
                                            for x in row[19].split(','):
                                                x = x.strip()
                                                if x != '':
                                                    search_barcode = self.env['product.product'].search(
                                                        ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                                    if not search_barcode:
                                                        self.env['product.template.barcode'].sudo().create({
                                                            'name': x,
                                                            'product_id': created_product_tmpl.product_variant_id.id,
                                                        })
                                    else:
                                        created_product_tmpl.barcode_line_ids = False
                                        if row[19].strip() not in (None, ""):
                                            for x in row[19].split(','):
                                                x = x.strip()
                                                search_barcode = self.env['product.product'].search(
                                                    ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                                if not search_barcode:
                                                    if x != '':
                                                        barcode_vals = {
                                                            'name': x
                                                        }
                                                        barcode_list.append(
                                                            (0, 0, barcode_vals))
                                    created_product_tmpl.barcode_line_ids = barcode_list
                                if created_product_tmpl and created_product_tmpl.product_variant_id and created_product_tmpl.type == 'product' and row[17] != '':
                                    stock_vals = {'product_tmpl_id': created_product_tmpl.id,
                                                  'new_quantity': row[17],
                                                  'product_id': created_product_tmpl.product_variant_id.id
                                                  }
                                    created_qty_on_hand = self.env['stock.change.product.qty'].create(
                                        stock_vals)
                                    if created_qty_on_hand:
                                        created_qty_on_hand.change_product_qty()

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Name is empty. "
                                counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception:
                    raise UserError(
                        _("Sorry, Your file does not match with our format"))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
