SELECT
    department,
    unit_code,
    unit_name,
    COUNT(*) AS headcount,
    ROUND(SUM(fte) / 100.0, 1) AS fte,
    ROUND(AVG(fte), 1) AS average_activity_rate
FROM active_staff
GROUP BY department, unit_code, unit_name
ORDER BY department, unit_code;
