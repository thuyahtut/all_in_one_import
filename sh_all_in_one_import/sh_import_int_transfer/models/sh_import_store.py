# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
from odoo.tools import ustr

class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_int_transfer(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_int_transfer':
            value = True
        return value

    sh_import_int_transfer_scheduled_date = fields.Datetime(
        string="Scheduled Date", related='base_id.sh_import_int_transfer_scheduled_date',readonly=False)
    sh_import_int_transfer_location_id = fields.Many2one(
        'stock.location', string="Source Location",
        related='base_id.sh_import_int_transfer_location_id',
        readonly=False)

    sh_import_int_transfer_location_dest_id = fields.Many2one(
        'stock.location', string="Destination Location",
        related='base_id.sh_import_int_transfer_location_dest_id',
        readonly=False)

    sh_import_int_transfer_product_by = fields.Selection(related='base_id.sh_import_int_transfer_product_by', string="Product By", readonly=False)


    sh_import_int_transfer_type = fields.Selection(related='base_id.sh_import_int_transfer_type', string="Import File Type", readonly=False)
    sh_import_int_transfer_boolean = fields.Boolean(
        "Import Internal Transfer Boolean", default=check_sh_import_int_transfer)

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_int_transfer':
            self.import_int_transfer(record)
        return res

    def import_int_transfer(self,record):
        self = record
        # # perform import Internal transfer
        if self and self.sh_file:

            if self.sh_import_int_transfer_type == 'csv' or self.sh_import_int_transfer_type == 'excel' and self.sh_import_int_transfer_location_id and self.sh_import_int_transfer_location_dest_id and self.sh_import_int_transfer_scheduled_date:
                counter = 1
                skipped_line_no = {}
                count=0
                stock_picking_obj = self.env['stock.picking']
                stock_move_obj = self.env['stock.move']
                try:
                    if self.sh_import_int_transfer_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_int_transfer_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    dic = {}
                    till = length_reader
                    created_picking = False
                    search_warehouse = False
                    search_picking_type = False
                    search_warehouse = self.env['stock.warehouse'].search([
                        ('company_id', '=', self.env.company.id)
                    ], limit=1)
                    if search_warehouse:
                        search_picking_type = self.env['stock.picking.type'].search([
                            ('code', '=', 'internal'),
                            ('warehouse_id', '=', search_warehouse.id)
                        ], limit=1)

                    picking_vals = {}
                    if search_picking_type:
                        picking_vals.update({
                            'picking_type_code': 'internal',
                            'location_id': self.sh_import_int_transfer_location_id.id,
                            'location_dest_id': self.sh_import_int_transfer_location_dest_id.id,
                            'scheduled_date': self.sh_import_int_transfer_scheduled_date,
                            'picking_type_id': search_picking_type.id
                        })

                        created_picking = stock_picking_obj.create(
                            picking_vals)
                    
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
                            
                            if row[0] not in (None, ""):
                                vals = {}

                                field_nm = 'name'
                                if self.sh_import_int_transfer_product_by == 'name':
                                    field_nm = 'name'
                                elif self.sh_import_int_transfer_product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.sh_import_int_transfer_product_by == 'barcode':
                                    field_nm = 'barcode'

                                search_product = self.env['product.product'].search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_product and search_product.type in ['product', 'consu']:
                                    search_uom = False
                                    vals.update(
                                        {'product_id': search_product.id})
                                    vals.update({'name': search_product.name})
                                    if row[1] not in (None, ""):
                                        vals.update({'quantity_done': row[1]})
                                    else:
                                        vals.update({'quantity_done': 0.0})

                                    if row[2].strip() not in (None, ""):
                                        search_uom = self.env['uom.uom'].search(
                                            [('name', '=', row[2].strip())], limit=1)
                                        if search_uom:
                                            vals.update(
                                                {'product_uom': search_uom.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Unit of Measure not found. "
                                            counter = counter + 1
                                            continue
                                    elif search_product.uom_id:
                                        vals.update(
                                            {'product_uom': search_product.uom_id.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Unit of Measure not defined for this product. "
                                        counter = counter + 1
                                        continue

                                    if created_picking:
                                        vals.update({
                                            'location_id': created_picking.location_id.id,
                                            'location_dest_id': created_picking.location_dest_id.id,
                                            'picking_id': created_picking.id,
                                            'date_deadline': created_picking.scheduled_date
                                        })
                                        created_stock_move = stock_move_obj.create(
                                            vals)
                                        if created_stock_move:
                                            created_stock_move._onchange_product_id()
                                            if search_uom:
                                                created_stock_move.write(
                                                    {'product_uom': search_uom.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Internal Transfer Could not be created. "
                                        counter = counter + 1
                                        continue
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product not found or it's not a Stockable or Consumable Product. "
                                    counter = counter + 1
                                    continue
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product is empty. "
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
