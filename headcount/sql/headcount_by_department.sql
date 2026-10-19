SELECT
    department,
    COUNT(*) AS headcount,
    ROUND(SUM(fte) / 100.0, 1) AS fte,
    SUM(gender = 'F') AS women,
    SUM(gender = 'M') AS men,
    ROUND(100.0 * SUM(gender = 'F') / COUNT(*), 1) AS women_pct,
    ROUND(AVG(age), 1) AS average_age,
    ROUND(SUM(gross_salary), 2) AS payroll_total
FROM active_staff
GROUP BY department
ORDER BY headcount DESC, department;
