WITH p AS (SELECT period_start, reference_date FROM params)
SELECT movement, date, employee_id, last_name, first_name, department, unit_name, contract_type
FROM (
    SELECT 'Entrée' AS movement, e.hire_date AS date, e.*
    FROM employees AS e CROSS JOIN p
    WHERE e.hire_date BETWEEN p.period_start AND p.reference_date
    UNION ALL
    SELECT 'Sortie' AS movement, e.exit_date AS date, e.*
    FROM employees AS e CROSS JOIN p
    WHERE e.exit_date BETWEEN p.period_start AND p.reference_date
) AS m
JOIN units USING (unit_code)
ORDER BY date, movement, employee_id;
