
# Patch Analysis and Remediation Job Flows (for BladeLogic)

## Patch Analysis Job
1. Target: All Linux servers (Debian, RHEL, SuSE)
2. Action: Use "Patch Analysis" job type in BladeLogic, select the relevant Patch Catalog.

## Compliance Scan Job
1. Target: All Linux servers
2. Action: Run Compliance Job using Component Template based on `hipaa_linux_template.yaml`

## Remediation Job
1. Target: Any non-compliant server
2. Action: Run BlPackage based on `linux_patch.sh`, or create remediation BlPackages per compliance rule.

## Patch Deployment (Staged)
1. Target: First dev, then test, then production groups.
2. Action: Schedule patch job using BlPackage, with automated reboot as needed.

**Refer to BladeLogic documentation for detailed steps to create and schedule each job.**
