# -*- coding: utf-8 -*-

# import logging
import os

from django.core.files.storage import FileSystemStorage


class DocumentStorage(FileSystemStorage):
    """
    """
    def delete(self, name):
        name = self.path(name)
        super(DocumentStorage, self).delete(name)

        # logger = logging.getLogger('system.modules.gallery')
        document_dir = os.path.dirname(name)

        try:
            os.rmdir(document_dir)
            # logger.info('empty directory "%s" deleted' % document_dir)
            document_par_dir = os.path.dirname(document_dir)
            os.rmdir(document_par_dir)
            # logger.info('empty directory "%s" deleted' % gallery_par_dir)
        except OSError:
            pass
