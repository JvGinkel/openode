# -*- coding: utf-8 -*-

import os
import errno
from django.template.defaultfilters import slugify

################################################################################
################################################################################


def mkdir_p(path):
    """same as action of the unix command
    mkdir -p
    """
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise e


def extend_file_name(file_path, extension):
    """append file extension to a string that
    represents file name, if the string does not
    already have that same extension"""
    if not file_path.endswith(extension):
        file_path += extension
    return file_path


def create_file_if_does_not_exist(file_path, print_warning=True):
    """if file at file_path does not exist, create it and return
    the file object, otherwise return None"""
    if not os.path.exists(file_path):
        return open(file_path, 'w+')
    else:
        if print_warning:
            print "File %s exists" % file_path
        return None


def sanitize_file_name(original_name):
    """
        @return: sanitized file name
            e.g.: ščřžýáí3456ĚŠČŘ34%^&.PDF => scrzyai3456escr34.pdf
    """
    file_name = slugify(original_name)
    crumb = original_name.split(".")
    ext = crumb[-1]
    name = crumb[:-1]
    if name and ext:
        file_name = "%s.%s" % (slugify("_".join(name)), ext)
        file_name = file_name.lower()
    return file_name
