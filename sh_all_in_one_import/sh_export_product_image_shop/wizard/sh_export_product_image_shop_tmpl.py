# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import ustr
import os
import base64
import tempfile
import zipfile
from io import BytesIO
from PIL import Image


class ShExportProductImageShopTmpl(models.TransientModel):
    _name = "sh.export.product.image.shop.tmpl"
    _description = "Export Product Image Shop Template"

    file_name = fields.Selection([
        ('barcode', 'Barcode'),
        ('default_code', 'Internal Reference'),
        ('name', 'Name'),
        ('id', 'ID'),
    ], string="Image Name As", required=True, default="name")

    product_tmpl_ids = fields.Many2many(
        'product.template', string='Products', store=True)

    is_export_extra_product_media = fields.Boolean(
        string="Export Extra Product Media?")
    is_export_for_import = fields.Boolean(string="Is export for import?")

    file = fields.Binary(string="Zip")
    zip_file_name = fields.Char(string="File Name")

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

    @api.model
    def default_get(self, fields):
        rec = super(ShExportProductImageShopTmpl,
                    self).default_get(fields)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        if not active_ids:
            raise UserError(
                _("Programming error: wizard action executed without active_ids in context."))

        if not active_ids or active_model != 'product.template':
            return rec

        product_tmpls = self.env['product.template'].browse(active_ids)

        rec.update({
            'product_tmpl_ids': [(6, 0, product_tmpls.ids)],
        })        
        return rec

    def action_export(self):
        if self:
            try:
                mem_zip = BytesIO()
                tmp_dir = tempfile.mkdtemp()
                with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for product in self.product_tmpl_ids:

                        # ====================================================
                        # Define a product name
                        # ====================================================
                        name_product = product.name
                        if self.file_name == 'barcode' and product.barcode:
                            name_product = product.barcode
                        elif self.file_name == 'default_code' and product.default_code:
                            name_product = product.default_code
                        elif self.file_name == 'id':
                            name_product = str(product.id)

                        # ====================================================
                        # take image from product field and write it into zip.
                        # ====================================================
                        if product.image_1920:
                            im = Image.open(
                                BytesIO(base64.b64decode(product.image_1920)))
                            imgext = '.' + Image.MIME[im.format].split('/')[1]
                            name_product = name_product.replace('/', '')
                            file_path = os.path.join(
                                tmp_dir, name_product + imgext)
                            im.save(file_path)
                            zf.write(file_path)

                        # ====================================================
                        # Extra Product Media
                        # ====================================================
                        if self.is_export_extra_product_media and product.product_template_image_ids:
                            main_product_name = name_product
                            for product_image in product.product_template_image_ids:

                                name_product = product_image.name
                                if self.is_export_for_import:
                                    name_product = '&mname=%s&seq=%s&name=%s&id=%s' % (
                                        main_product_name, 0, product_image.name, product_image.id)

                                if product_image.image_1920:
                                    im = Image.open(
                                        BytesIO(base64.b64decode(product_image.image_1920)))
                                    imgext = '.' + \
                                        Image.MIME[im.format].split('/')[1]
                                    name_product = name_product.replace(
                                        '/', '')
                                    file_path = os.path.join(
                                        tmp_dir, name_product + imgext)
                                    im.save(file_path)
                                    zf.write(file_path)

                # ====================================================
                # assign image to wizard field.
                # ====================================================
                self.file = base64.encodebytes(mem_zip.getvalue())
                self.zip_file_name = 'product_images.zip'

            except Exception as e:
                raise UserError(_("Something went wrong! " + ustr(e)))

            # ====================================================
            # Return self object of wizard.
            # ====================================================
            return {
                'name': 'Export Images eCommerce',
                'view_mode': 'form',
                'res_id': self.id,
                'res_model': 'sh.export.product.image.shop.tmpl',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                'context': self.env.context,
                'target': 'new',
            }
