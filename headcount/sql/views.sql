-- Staff counted in the headcount: under contract on the reference date
-- (last day of the period) and paid for the period.
CREATE VIEW active_staff AS
WITH ref AS (SELECT reference_date FROM params),
pay AS (
    SELECT employee_id, SUM(fte) AS fte, SUM(gross_salary) AS gross_salary
    FROM payroll
    GROUP BY employee_id
)
SELECT
    e.employee_id,
    e.gender,
    e.contract_type,
    u.department,
    u.unit_code,
    u.unit_name,
    pay.fte,
    pay.gross_salary,
    CAST((julianday(ref.reference_date) - julianday(e.birth_date)) / 365.25 AS INTEGER) AS age
FROM employees AS e
JOIN units AS u ON u.unit_code = e.unit_code
JOIN pay ON pay.employee_id = e.employee_id
CROSS JOIN ref
WHERE e.hire_date <= ref.reference_date
  AND (e.exit_date IS NULL OR e.exit_date >= ref.reference_date);
