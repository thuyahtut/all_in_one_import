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
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import codecs
import requests
import logging
_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_journal_entry(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_journal_entry':
            value = True
        return value

    sh_import_entry_accounting_date = fields.Date(related='base_id.sh_import_entry_accounting_date',readonly=False,string='Accounting Date')
    sh_import_entry_journal_id = fields.Many2one(
        'account.journal', 'Journal',related='base_id.sh_import_entry_journal_id',readonly=False)
    sh_import_entry_type = fields.Selection(related='base_id.sh_import_entry_type',readonly=False, string="Import File Type", required=True)

    sh_import_entry_partner_by = fields.Selection(related='base_id.sh_import_entry_partner_by',readonly=False, string="Customer By")
    sh_import_journal_entry_boolean = fields.Boolean(
        "Import Journal Entry Boolean", default=check_sh_import_journal_entry)
    sh_company_id_journal_entry = fields.Many2one(
        related="base_id.sh_company_id_journal_entry", readonly=False, string="Company", required=True)
    running_journal_entry = fields.Char(string='Running Journal Entry')
    total_done_journal_entry = fields.Integer("Total Done Journal Entry")

    def create_journal_logs(self, counter, skipped_line_no,confirm_records):
        # dic_msg = str(counter) + " Records imported successfully"
        dic_msg = str(confirm_records) + " Rows imported successfully"
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
        if record.base_id.sh_technical_name == 'sh_import_journal_entry':
            self.import_journal_entry(record)
        return res

    def import_journal_entry(self,record):
        self = record
        account_move_obj = self.env['account.move']

        # # perform import Lead
        if self and self.sh_file:

            if self.sh_import_entry_type == 'csv' or self.sh_import_entry_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                created_moves = []
                line_list = []
                imported_lines = 0
                try:
                    if self.sh_import_entry_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_entry_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    # running_move = None
                    # created_move = False
                    till = length_reader
                    
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit

                    self.total_done_journal_entry = till

                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_move = account_move_obj.sudo().search([('name','=',self.running_journal_entry)],limit=1)
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False
                                continue
                            if row[0] not in (None, "") and row[2] not in (None, ""):
                                vals = {}

                                if row[0] != self.running_journal_entry:

                                    self.running_journal_entry = row[0]
                                    move_vals = {}
                                    if row[1] not in [None, ""]:
                                        move_vals.update({
                                            'ref': row[1],
                                        })
                                    if row[9] not in [None, ""]:
                                        datetime_obj = datetime.strptime(
                                            row[9], DEFAULT_SERVER_DATE_FORMAT)
                                        move_vals.update({
                                            'date': datetime_obj,
                                        })
                                    else:
                                        if self.sh_import_entry_accounting_date:
                                            move_vals.update({
                                                'date': self.sh_import_entry_accounting_date,
                                            })
                                        else:
                                            move_vals.update({
                                                'date': fields.Date.today(),
                                            })
                                    move_vals.update({
                                        'journal_id': self.sh_import_entry_journal_id.id,
                                        'currency_id': self.env.company.currency_id.id,
                                        'move_type': 'entry',
                                        'company_id': self.sh_company_id_journal_entry.id,
                                    })
                                    if move_vals:
                                        created_move = account_move_obj.sudo().create(move_vals)
                                        created_moves.append(
                                            created_move.id)
                                if created_move:
                                    vals = {}
                                    domain = []
                                    if row[2] not in [None, ""]:
                                        search_account = self.env['account.account'].sudo().search(
                                            [('code', '=', row[2]), ('company_id', '=', self.sh_company_id_journal_entry.id)], limit=1)
                                        if search_account:
                                            vals.update(
                                                {'account_id': search_account.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Account not found. "
                                            counter = counter + 1
                                            continue
                                    if row[3] not in [None, ""]:
                                        search_partner = self.env["res.partner"]

                                        if self.sh_import_entry_partner_by == 'name':
                                            domain += [('name',
                                                        '=', row[3])]
                                        if self.sh_import_entry_partner_by == 'ref':
                                            domain += [('ref',
                                                        '=', row[3])]
                                        if self.sh_import_entry_partner_by == 'id':
                                            domain += [('id', '=', row[3])]

                                        search_partner = search_partner.search(
                                            domain, limit=1)

                                        if search_partner:
                                            vals.update({
                                                'partner_id': search_partner.id,
                                            })
                                    if row[4] not in [None, ""]:
                                        vals.update({
                                            'name': row[4]
                                        })
                                    if row[5] not in [None, ""]:
                                        analytic_dic = {}
                                        for x in row[5].split(','):
                                            x = x.strip()
                                            if x != '':
                                                search_analytic_acccount = self.env['account.analytic.account'].sudo().search([
                                                    ('name', '=', x)], limit=1)
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
                                    if row[6] not in [None, ""]:
                                        vals.update({
                                            'debit': float(row[6])
                                        })
                                    if row[7] not in [None, ""]:
                                        vals.update({
                                            'credit': float(row[7])
                                        })
                                    if row[8] not in [None, ""]:
                                        tax_list = []
                                        for x in row[8].split(','):
                                            x = x.strip()
                                            if x != '':
                                                search_tax = self.env['account.tax'].search(
                                                    [('name', '=', x)], limit=1)
                                                if search_tax:
                                                    tax_list.append(
                                                        search_tax.id)
                                        if len(tax_list) > 0:
                                            vals.update(
                                                {'tax_ids': [(6, 0, tax_list)]})
                                    vals.update({
                                        'move_id': created_move.id,
                                        'currency_id': self.env.company.currency_id.id,
                                    })
                                    line_list.append(vals)
                                    counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                    for move in created_moves:
                        final_list = []
                        for line in line_list:
                            if move == line.get('move_id'):
                                del line['move_id']
                                final_list.append((0, 0, line))
                        move_id = self.env['account.move'].sudo().browse(
                            move)
                        if move_id:
                            move_id.sudo().write({
                                'line_ids': final_list
                            })
                    imported_lines += 1        
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                # if length_reader == self.total_done_journal_entry:
                    # if not skipped_line_no:
                    #     self.create_logs(
                    #         self.total_done_journal_entry, skipped_line_no,0)
                    #     self.state = 'done'
                if counter > 1:
                    completed_records = len(created_moves)
                    # if not skipped_line_no:
                    #     self.create_store_logs(
                    #         completed_records, skipped_line_no)
                    #     self.state = 'done'
                    # else:
                    #     self.received_error = True
                    #     self.create_store_logs(
                    #         completed_records, skipped_line_no)
                    #     if self.on_error == 'break':
                    #         self.state = 'error'
                    #     elif self.import_limit == 0:
                    #         if self.received_error:
                    #             self.state = 'partial_done'
                    #         else:
                    #             self.state = 'done'
                    if not skipped_line_no:
                        self.create_journal_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done' if length_reader == self.total_done_journal_entry else 'running'
                    else:
                        self.received_error = True
                        self.create_journal_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_journal_entry else None
