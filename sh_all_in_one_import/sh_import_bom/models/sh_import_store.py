# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
from odoo.tools import ustr


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_bom(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_bom':
            value = True
        return value

    import_bom_type = fields.Selection(related='base_id.import_bom_type',readonly=False, string="  Import File Type")
    bom_type = fields.Selection(related='base_id.bom_type',readonly=False, string="BoM Type")

    sh_import_bom_product_by = fields.Selection(related='base_id.sh_import_bom_product_by',readonly=False, string="Product Variant By  ")
    sh_import_bom_product_template_by = fields.Selection(related='base_id.sh_import_bom_product_template_by',readonly=False, string="Product By  ")
    sh_import_bom_boolean = fields.Boolean(
        "Import BOM Boolean", default=check_sh_import_bom)

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_bom':
            self.import_bom(record)
        return res

    def import_bom(self,record):
        self = record
        bom_obj = self.env['mrp.bom']
        bom_line_obj = self.env['mrp.bom.line']
        # # perform import EMP Image
        if self and self.sh_file:

            if self.import_bom_type == 'csv' or self.import_bom_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                try:
                    if self.import_bom_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.import_bom_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    running_bom = None
                    created_bom = False
                    created_bom_list = []
                    bom_list_for_unlink = []
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
                                continue
                            if row[0] not in (None, "") and row[5] not in (None, ""):
                                vals = {}
                                if row[0] != running_bom:
                                    running_bom = row[0]
                                    bom_vals = {}

                                    if row[1] not in (None, ""):
                                        field_template_nm = 'name'
                                        if self.sh_import_bom_product_template_by == 'name':
                                            field_template_nm = 'name'
                                        elif self.sh_import_bom_product_template_by == 'int_ref':
                                            field_template_nm = 'default_code'
                                        elif self.sh_import_bom_product_template_by == 'barcode':
                                            field_template_nm = 'barcode'

                                        field_nm = 'default_code'
                                        if self.sh_import_bom_product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_import_bom_product_by == 'barcode':
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

                                            if self.bom_type == 'mtp':
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
                                    if self.sh_import_bom_product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.sh_import_bom_product_by == 'barcode':
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
