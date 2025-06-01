# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportBomWizard(models.TransientModel):
    _name = "import.bom.wizard"
    _description = "Import Bill of Materials Wizard"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)

    bom_type = fields.Selection([
        ('mtp', 'Manufacture this product'),
        ('kit', 'Kit')
    ], default="mtp", string="BoM Type", required=True)

    product_by = fields.Selection([
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="int_ref", string="Product Variant By", required=True)
    product_template_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)

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

    def import_bom_apply(self):
        ''' ............ Import Bom Using CSV And EXCEL .....'''
        bom_obj = self.env['mrp.bom']
        bom_line_obj = self.env['mrp.bom.line']
        if self and self.file:
            if self.import_type == 'csv' or self.import_type == 'excel':
                for rec in self:
                    counter = 1
                    skipped_line_no = {}
                    try:
                        values = []
                        if self.import_type == 'csv':
                            file = str(
                                base64.decodebytes(self.file).decode('utf-8'))
                            values = csv.reader(file.splitlines())

                        elif self.import_type == 'excel':
                            values = self.read_xls_book()
                        skip_header = True
                        running_bom = None
                        created_bom = False
                        created_bom_list = []
                        bom_list_for_unlink = []

                        for row in values:
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue
                                if row[0] not in (None, "") and row[5] not in (None, ""):
                                    vals = {}
                                    if row[0] != running_bom:
                                        running_bom = row[0]
                                        bom_vals = {}

                                        if row[1] not in (None, ""):
                                            field_template_nm = 'name'
                                            if rec.product_template_by == 'name':
                                                field_template_nm = 'name'
                                            elif rec.product_template_by == 'int_ref':
                                                field_template_nm = 'default_code'
                                            elif rec.product_template_by == 'barcode':
                                                field_template_nm = 'barcode'

                                            field_nm = 'default_code'
                                            if rec.product_by == 'int_ref':
                                                field_nm = 'default_code'
                                            elif rec.product_by == 'barcode':
                                                field_nm = 'barcode'
                                            search_product_tmpl = self.env['product.template'].search(
                                                [(field_template_nm, '=', row[1])], limit=1)

                                            if search_product_tmpl and search_product_tmpl.type in ['product', 'consu']:
                                                bom_vals.update(
                                                    {'product_tmpl_id': search_product_tmpl.id})

                                                if row[2] not in (None, ""):
                                                    search_product_var = self.env['product.product'].search(
                                                        [(field_nm, '=', row[2])], limit=1)                                                    
                                                    if search_product_var and search_product_var.product_tmpl_id.id == search_product_tmpl.id and search_product_var.type in ['product', 'consu']:
                                                        bom_vals.update(
                                                            {'product_id': search_product_var.id})
                                                    else:
                                                        skipped_line_no[str(
                                                            counter)] = " - Product Variant is invalid. "
                                                        counter = counter + 1
                                                        continue
                                                if row[3] not in (None, ""):
                                                    bom_vals.update(
                                                        {'product_qty': row[3]})
                                                else:
                                                    bom_vals.update(
                                                        {'product_qty': 1})

                                                if row[4] not in (None, ""):
                                                    search_uom = self.env['uom.uom'].search(
                                                        [('name', '=', row[4])], limit=1)
                                                    if search_uom:
                                                        bom_vals.update(
                                                            {'product_uom_id': search_uom.id})
                                                    else:
                                                        skipped_line_no[str(
                                                            counter)] = " - Unit of Measure not found. "
                                                        counter = counter + 1
                                                        continue
                                                elif search_product_tmpl.uom_id:
                                                    bom_vals.update(
                                                        {'product_uom_id': search_product_tmpl.uom_id.id})
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Unit of Measure not defined. "
                                                    counter = counter + 1
                                                    continue

                                                if rec.bom_type == 'mtp':
                                                    bom_vals.update(
                                                        {'type': 'normal'})
                                                else:
                                                    bom_vals.update(
                                                        {'type': 'phantom'})                                                
                                                bom_vals.update(
                                                    {'code': row[0]})                                                
                                                created_bom = bom_obj.create(
                                                    bom_vals)                                                
                                                if created_bom:
                                                    obj = created_bom_list.append(
                                                        created_bom.id)                                                    

                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Finished Product not found or it's type is invalid. "
                                                counter = counter + 1
                                                continue

                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Finished Product field is empty. "
                                            counter = counter + 1
                                            continue                                    
                                    if created_bom:
                                        field_nm = 'default_code'
                                        if rec.product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif rec.product_by == 'barcode':
                                            field_nm = 'barcode'
                                        search_material_product = self.env['product.product'].search(
                                            [(field_nm, '=', row[5])], limit=1)                                        
                                        if search_material_product:
                                            vals.update(
                                                {'product_id': search_material_product.id})

                                            if row[6] not in (None, ""):
                                                vals.update(
                                                    {'product_qty': row[6]})
                                            else:
                                                vals.update({'product_qty': 1})

                                            if row[7] not in (None, ""):
                                                search_uom = self.env['uom.uom'].search(
                                                    [('name', '=', row[7])], limit=1)
                                                if search_uom:
                                                    vals.update(
                                                        {'product_uom_id': search_uom.id})
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Material product Unit of Measure not found. "
                                                    counter = counter + 1
                                                    bom_list_for_unlink.append(
                                                        created_bom.id)
                                                    continue
                                            elif search_material_product.uom_id:
                                                vals.update(
                                                    {'product_uom_id': search_material_product.uom_id.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Material product Unit of Measure not defined. "
                                                counter = counter + 1
                                                bom_list_for_unlink.append(
                                                    created_bom.id)
                                                continue

                                            vals.update(
                                                {'bom_id': created_bom.id})
                                            bom_line_obj.create(vals)
                                            counter = counter + 1

                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Material product not found. "
                                            bom_list_for_unlink.append(
                                                created_bom.id)
                                            counter = counter + 1

                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - BoM not created. "
                                        counter = counter + 1

                                else:
                                    if created_bom:
                                        bom_list_for_unlink.append(
                                            created_bom.id)
                                    skipped_line_no[str(
                                        counter)] = " - Reference or Material product is empty. "
                                    counter = counter + 1

                            except Exception as e:
                                if created_bom:
                                    bom_list_for_unlink.append(created_bom.id)
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue

                        if bom_list_for_unlink:
                            search_boms = bom_obj.search(
                                [('id', 'in', bom_list_for_unlink)])
                            if search_boms:
                                search_boms.unlink()

                            for item in bom_list_for_unlink:
                                if item in created_bom_list:
                                    created_bom_list.remove(item)

                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your file does not match with our format" + ustr(e)))

                    if counter > 1:
                        completed_records = len(created_bom_list)
                        res = rec.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
