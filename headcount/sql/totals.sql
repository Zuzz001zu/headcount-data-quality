SELECT
    COUNT(*) AS headcount,
    ROUND(SUM(fte) / 100.0, 1) AS fte,
    ROUND(AVG(fte), 1) AS average_activity_rate,
    ROUND(SUM(gross_salary), 2) AS payroll_total
FROM active_staff;
