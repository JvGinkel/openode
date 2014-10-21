# -*- coding: utf-8 -*-

from django.db import connections


def get_invalid_documents_qs():
    """
        return document QuerySet with no OCR bugs
    """
    from openode.document.models import Document

    sql = """SELECT
            latest_revisions.document_id AS document_id
        FROM
            "document_page"
            RIGHT JOIN
            (SELECT
                    dr.id,
                    dr.document_id
                FROM "document_document" d
                JOIN "document_documentrevision" dr ON ( dr."document_id"=d.id )
                WHERE (d.id, dr.revision) = (
                    SELECT document_id, MAX(revision)
                    FROM "document_documentrevision"
                    WHERE
                        "document_documentrevision".document_id=d.id
                        AND
                        "document_documentrevision".suffix NOT IN (%s)
                    GROUP BY "document_id"
                )
            ) latest_revisions
            ON (
                "document_page".document_revision_id=latest_revisions.id
                AND
                NOT "document_page"."plaintext" IN ('', '-- ? --')
            )
        GROUP BY
            latest_revisions.document_id
        HAVING COUNT(document_page.id) = 0
    """

    cursor = connections["default"].cursor()
    cursor.execute(
        # sorry, I have no more time for solving best formatting
        sql % ','.join(["'zip'", "'rar'"])
        )
    ret = cursor.fetchall()

    return Document.objects.filter(pk__in=[r[0] for r in ret])
