"""
.. _openode.deps

:mod:openode.deps - dependency packages for Openode
===================================================

Most openode dependencies are satisfied with setuptools, but some modules
were either too seriously modified - like `django_authopenid` specifically for
openode, while others are not available via PyPI. Yet some other packages
while being listed on PyPI, still do not install reliably - those were also
added to the ``openode.deps`` module.

Some packages included here were modified with hardcoded imports like::

    from openode.deps.somepackage import xyz
    from openode.deps import somepackage

So these cannot be moved around at all.
"""
