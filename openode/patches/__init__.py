"""module for monkey patching that is
necessary for interoperability of different
versions of various components used in openode
"""
import django
from openode.patches import django_patches
from openode.deployment import package_utils

def patch_django():
    """earlier versions of Django do not have
    csrf token and function called import_library
    (the latter is needed by coffin)
    """
    (major, minor, micro) = package_utils.get_django_version()
    if major == 1 and minor < 2:
        django_patches.add_import_library_function()
        django_patches.add_csrf_protection()
        django_patches.add_available_attrs_decorator()

def patch_coffin():
    """coffin before version 0.3.4
    does not have csrf_token template tag.
    This patch must be applied after the django patches
    """
    from openode.patches import coffin_patches

    (major, minor, micro) = package_utils.get_coffin_version()
    if major == 0 and minor == 3 and micro < 4:
        coffin_patches.add_csrf_token_tag()
