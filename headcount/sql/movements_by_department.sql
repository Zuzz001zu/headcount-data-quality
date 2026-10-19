-- Entries and exits recorded in the HR system during the period.
-- An exit on the last day is counted both in the headcount and as an exit.
WITH p AS (SELECT period_start, reference_date FROM params),
moves AS (
    SELECT
        u.department,
        SUM(e.hire_date BETWEEN p.period_start AND p.reference_date) AS entries,
        SUM(e.exit_date BETWEEN p.period_start AND p.reference_date) AS exits
    FROM employees AS e
    JOIN units AS u ON u.unit_code = e.unit_code
    CROSS JOIN p
    GROUP BY u.department
),
staff AS (
    SELECT department, COUNT(*) AS headcount FROM active_staff GROUP BY department
)
SELECT
    d.department,
    COALESCE(moves.entries, 0) AS entries,
    COALESCE(moves.exits, 0) AS exits,
    COALESCE(moves.entries, 0) - COALESCE(moves.exits, 0) AS net_change,
    ROUND(100.0 * COALESCE(moves.exits, 0) / NULLIF(staff.headcount, 0), 1) AS exit_rate_pct
FROM (SELECT DISTINCT department FROM units) AS d
LEFT JOIN moves ON moves.department = d.department
LEFT JOIN staff ON staff.department = d.department
ORDER BY d.department;
