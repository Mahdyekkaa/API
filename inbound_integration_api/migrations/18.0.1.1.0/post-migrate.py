# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'integration_order' AND column_name = 'company_name'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        INSERT INTO integration_company (name, active, create_uid, write_uid, create_date, write_date)
        SELECT DISTINCT ON (lower(trim(company_name))) trim(company_name), TRUE, 1, 1,
               now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC'
        FROM integration_order o
        WHERE coalesce(trim(company_name), '') != ''
          AND NOT EXISTS (
              SELECT 1 FROM integration_company c
              WHERE lower(c.name) = lower(trim(o.company_name))
          )
        ORDER BY lower(trim(company_name))
        """
    )
    cr.execute(
        """
        UPDATE integration_order o
        SET integration_company_id = c.id
        FROM integration_company c
        WHERE lower(c.name) = lower(trim(o.company_name))
          AND o.integration_company_id IS NULL
        """
    )
    cr.execute("ALTER TABLE integration_order DROP COLUMN company_name")
