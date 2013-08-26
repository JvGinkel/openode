# -*- coding: utf-8 -*-

import logging
import os

import Pyro4

from django.conf import settings

#######################################

Pyro4.config.HMAC_KEY = settings.DOCUMENT_HMAC_KEY
Pyro4.config.HOST = settings.DOCUMENT_SERVER_IP

#######################################


class DocumentAPIClient(object):
    """
        DocumentAPI client
    """
    logger = logging.getLogger('document_api')

    def __init__(self):
        """
            connect to remote document-parser server
        """
        self.uri = "PYRO:%s@%s:%s" % (
            settings.DOCUMENT_URI_ID,
            settings.DOCUMENT_SERVER_IP,
            settings.DOCUMENT_URI_PORT,
            )
        self.connect()

    def connect(self):
        try:
            self.proxy = Pyro4.Proxy(self.uri)
            self.logger.info("Create proxy success: %s" % repr(self.uri))
            return True
        except Pyro4.errors.PyroError, e:
            self.proxy = None
            self.logger.error("Create proxy error: %s" % repr(e.message))
            return False

    def retrive_thumbnails_wrapper(self, uuid, path):
        """
            wrapper for retrive document thumbnails
        """
        pages_count = self.proxy.get_page_count(uuid)
        for page in xrange(1, pages_count + 1):
            file_path = os.path.join(path, "%s_%s" % (uuid, page))
            img = self.proxy.retrive_thumbnails(uuid, page=page)
            f_loc = open(file_path, "w")
            f_loc.write(img)
            f_loc.close()


document_api_client = DocumentAPIClient()
