WITH banded AS (
    SELECT
        CASE
            WHEN age < 25 THEN '< 25'
            WHEN age < 35 THEN '25-34'
            WHEN age < 45 THEN '35-44'
            WHEN age < 55 THEN '45-54'
            ELSE '55+'
        END AS age_band,
        gender
    FROM active_staff
)
SELECT
    age_band,
    SUM(gender = 'F') AS women,
    SUM(gender = 'M') AS men,
    COUNT(*) AS headcount
FROM banded
GROUP BY age_band
ORDER BY CASE age_band WHEN '< 25' THEN 0 ELSE 1 END, age_band;
