
-- Patch Status Dashboard Example
SELECT
  server_name,
  os_type,
  last_patch_status,
  last_patch_time
FROM
  bl_patch_status
ORDER BY
  last_patch_time DESC;
