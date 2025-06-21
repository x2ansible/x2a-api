
-- Compliance Status Report Example
SELECT
  server_name,
  compliance_policy,
  rule_id,
  rule_description,
  result,
  scan_time
FROM
  bl_compliance_results
WHERE
  compliance_policy LIKE '%HIPAA%'
ORDER BY
  scan_time DESC;
