# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportJournalEntryWizard(models.TransientModel):
    _name = "sh.import.journal.entry"
    _description = "Import Journal Entry Wizard"

    @api.model
    def default_company_id(self):
        return self.env.company

    file = fields.Binary(string="File", required=True)
    sh_accounting_date = fields.Date('Accounting Date', required=True)
    sh_journal_id = fields.Many2one(
        'account.journal', 'Journal', required=True)
    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=default_company_id, required=True)

    sh_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")

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

    def import_journal_entry_apply(self):
        ''' ................ Import Journal Entry Using CSV and EXCEL .................'''
        account_move_obj = self.env['account.move']
        if self:
            for rec in self:
                if self.import_type == 'csv' or self.import_type == 'excel':
                    line_list = []
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
                        running_move = None
                        created_move = False
                        created_moves = []
                        for row in values:
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue

                                if row[0] not in (None, "") and row[2] not in (None, ""):
                                    vals = {}

                                    if row[0] != running_move:

                                        running_move = row[0]
                                        move_vals = {}
                                        if row[1] not in [None, ""]:
                                            move_vals.update({
                                                'ref': row[1],
                                            })
                                        if row[9] not in [None, ""]:
                                            datetime_obj = datetime.datetime.strptime(
                                                row[9], DF)
                                            move_vals.update({
                                                'date': datetime_obj,
                                            })
                                        else:
                                            if self.sh_accounting_date:
                                                move_vals.update({
                                                    'date': rec.sh_accounting_date,
                                                })
                                            else:
                                                move_vals.update({
                                                    'date': fields.Date.today(),
                                                })
                                        move_vals.update({
                                            'journal_id': self.sh_journal_id.id,
                                            'currency_id': self.env.company.currency_id.id,
                                            'move_type': 'entry',
                                            'company_id': self.company_id.id,
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
                                                [('code', '=', row[2]), ('company_id', '=', self.company_id.id)], limit=1)
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

                                            if self.sh_partner_by == 'name':
                                                domain += [('name',
                                                            '=', row[3])]
                                            if self.sh_partner_by == 'ref':
                                                domain += [('ref',
                                                            '=', row[3])]
                                            if self.sh_partner_by == 'id':
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
                                    counter)] = " - Value is not valid " + ustr(e)
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
                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your file does not match with our format " + ustr(e)))
                    if counter > 1:
                        completed_records = len(created_moves)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
