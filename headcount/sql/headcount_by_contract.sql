SELECT
    contract_type,
    COUNT(*) AS headcount,
    ROUND(SUM(fte) / 100.0, 1) AS fte,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM active_staff), 1) AS share_pct
FROM active_staff
GROUP BY contract_type
ORDER BY headcount DESC;
