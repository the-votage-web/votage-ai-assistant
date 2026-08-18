WITH normalized_members AS (
    SELECT
        id,
        CASE
            WHEN department IS NULL OR btrim(department) = '' THEN NULL
            WHEN lower(replace(btrim(department), ' ', '_')) = 'votage_act' THEN 'Votage_Act'
            WHEN lower(replace(btrim(department), ' ', '_')) = 'digital_communication' THEN 'Digital_Communication'
            WHEN lower(btrim(department)) = 'rmg' THEN 'RMG'
            WHEN lower(btrim(department)) = 'vip' THEN 'VIP'
            WHEN lower(btrim(department)) = 'media' THEN 'Media'
            WHEN lower(btrim(department)) = 'technical' THEN 'Technical'
            WHEN lower(btrim(department)) = 'ushering' THEN 'Ushering'
            WHEN lower(btrim(department)) = 'welfare' THEN 'Welfare'
            WHEN lower(btrim(department)) = 'prayer' THEN 'Prayer'
            WHEN lower(btrim(department)) = 'protocol' THEN 'Protocol'
            WHEN lower(btrim(department)) = 'sanitation' THEN 'Sanitation'
            WHEN lower(btrim(department)) = 'pastorate' THEN 'Pastorate'
            WHEN lower(btrim(department)) = 'others' THEN 'Others'
            ELSE btrim(department)
        END AS canonical_name
    FROM "members"
),
distinct_departments AS (
    SELECT DISTINCT canonical_name
    FROM normalized_members
    WHERE canonical_name IS NOT NULL
)
INSERT INTO "department" ("id", "name")
SELECT
    (
        substr(md5(canonical_name), 1, 8) || '-' ||
        substr(md5(canonical_name), 9, 4) || '-' ||
        substr(md5(canonical_name), 13, 4) || '-' ||
        substr(md5(canonical_name), 17, 4) || '-' ||
        substr(md5(canonical_name), 21, 12)
    )::uuid,
    canonical_name
FROM distinct_departments
ON CONFLICT ("name") DO NOTHING;

WITH normalized_members AS (
    SELECT
        id,
        CASE
            WHEN department IS NULL OR btrim(department) = '' THEN NULL
            WHEN lower(replace(btrim(department), ' ', '_')) = 'votage_act' THEN 'Votage_Act'
            WHEN lower(replace(btrim(department), ' ', '_')) = 'digital_communication' THEN 'Digital_Communication'
            WHEN lower(btrim(department)) = 'rmg' THEN 'RMG'
            WHEN lower(btrim(department)) = 'vip' THEN 'VIP'
            WHEN lower(btrim(department)) = 'media' THEN 'Media'
            WHEN lower(btrim(department)) = 'technical' THEN 'Technical'
            WHEN lower(btrim(department)) = 'ushering' THEN 'Ushering'
            WHEN lower(btrim(department)) = 'welfare' THEN 'Welfare'
            WHEN lower(btrim(department)) = 'prayer' THEN 'Prayer'
            WHEN lower(btrim(department)) = 'protocol' THEN 'Protocol'
            WHEN lower(btrim(department)) = 'sanitation' THEN 'Sanitation'
            WHEN lower(btrim(department)) = 'pastorate' THEN 'Pastorate'
            WHEN lower(btrim(department)) = 'others' THEN 'Others'
            ELSE btrim(department)
        END AS canonical_name
    FROM "members"
)
UPDATE "members" AS m
SET
    "department" = normalized_members.canonical_name,
    "department_id" = d."id"
FROM normalized_members
JOIN "department" AS d
    ON d."name" = normalized_members.canonical_name
WHERE m."id" = normalized_members."id"
  AND normalized_members.canonical_name IS NOT NULL;
