.. openode documentation master file, created by
   sphinx-quickstart on Mon May 13 09:39:17 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Openode's documentation!
========================

Installation instructions
-------------------------

.. toctree::
    :maxdepth: 2

    install_server
    install_localhost

What is OPENode?
----------------

Basic idea
  Our goal is to make a neat web tool to support communication between distinct users and groups within boundaries of a published methodology (Problem domain). Aim is to speed up processes that solves issues of insufficiently described situations in Problem domain. It includes individual problems as well as initial methods defining.

The name Pluto has been chosen for developer’s denomination of project, because it’s far away from “name conflicts” and Pluto the planet is compounded of two smaller intersected objects as well, as our project is. It’s an interesection of projects `Askbot <http://askbot.com/>`_ and `Mayan EDMS <http://www.mayan-edms.com/>`_.


Problem Domain is an environment, where we want to have project Pluto implemented in. It may be an institution providing sophisticated Instructions on a Topic. These instructions are provided as office documents and are in continuous improvement process. Rare situations under Topic, that are not included in Instructions are solved individually. Pluto supports all stages of such scenario:

- publishing documents in revisions
- collecting individual Questions
- finding Answers using crowdsource-like method
- multi-layer access permissions with groups
- notification for both permanent and once-in-a-time users
- tagging and fulltext features
- presenting informations in most open way (users may preview office document on-line even without having any office suite installed)


Whole Problem Domain is divided into Clubs - elements that give certain users permission to manipulate the content made by Q&A and EDMS. Clubs are organized in a tree hierarchy, each Club has a status that represents it’s livecycle stage.

EDMS records are in fact Wiki pages with optional content-made-by-attachment. In a brief: instead of writing a wiki page, you may upload a file with ordinary office content (doc, pptx, odt, pdf, ...). That one is automatically converted using Mayan EDMS to a stream of JPEG pages thumbnails with extracted links and per-page plaintext representation for fulltext referencing.

Source
  As the starting point we have chosen the Askbot project, because it has lots of features implemented, but still there is a lot to add.

Alternatives to our system might be:
- `Askbot <http://askbot.com/>`_
- `Mayan EDMS <http://www.mayan-edms.com/>`_
- sophisticated libarian software called `Kramerius <http://code.google.com/p/kramerius/>`_ written in Java (development activities are mainly in Czech language)

Issues
------
If you find some error, please report issue: https://github.com/openode/openode/issues

Contributing
------------
https://github.com/openode/openode

License
--------
Project OPENode is published under license AGPLv3 <http://www.gnu.org/licenses/agpl-3.0.html>
Documentation is licensed under a CC-BY-SA license <http://creativecommons.org/licenses/by-sa/2.0/>
