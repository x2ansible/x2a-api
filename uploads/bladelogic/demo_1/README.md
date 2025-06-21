
# BladeLogic Automation Pack for GlobalTech Inc. (Linux/HIPAA)

## Overview

This package provides **starter automation templates** for using BMC BladeLogic (TrueSight Server Automation) to automate HIPAA-compliant patching, compliance scanning, and remediation across Linux servers (Debian, RHEL, SuSE).

**Note:** Due to BladeLogic proprietary object formats, this pack contains _portable scripts and templates_ for manual creation/import into BladeLogic. See below for step-by-step instructions.

---

## File Structure

- `agent-deploy/`: Scripts to install/check BladeLogic agent on Linux servers
- `compliance-templates/`: HIPAA compliance template examples (XML/YAML format for easy reference)
- `patching-packages/`: Linux patch/remediation scripts (to use in BlPackages)
- `jobs/`: Job flow examples in pseudo-XML and step-by-step instructions
- `reporting/`: SQL/report templates for compliance/patch dashboards

---

## Step-by-Step Instructions

### 1. BladeLogic Agent Deployment

- Use `agent-deploy/deploy_agent.sh` to install or check the agent on all target Linux servers.
- This script can be run via SSH, BladeLogic NSH, or wrapped in a BlPackage.

### 2. Creating Patch BlPackages

- In BladeLogic Console, create a new BlPackage for Linux patching.
- Paste the contents of `patching-packages/linux_patch.sh` into a "External Command" step.
- Customize parameters as needed (e.g., patch repository URLs).

### 3. Building HIPAA Compliance Baselines

- Reference `compliance-templates/hipaa_linux_template.yaml` when creating a Component Template in BladeLogic.
- Add rules for accounts, SSH config, file permissions, logging as per sample.

### 4. Setting Up Jobs

- Use the step-by-step guide in `jobs/patch_analysis_and_remediation.md` to build:
  - Patch analysis job
  - Compliance scan job
  - Remediation job
  - Patch deployment job (with staged execution)
- Refer to the pseudo-XML/job flow for job logic.

### 5. Reporting

- Use `reporting/compliance_status_report.sql` and `reporting/patch_status_dashboard.sql` as SQL queries in your BladeLogic Reporting DB, or as references for GUI-based dashboards.

---

## Manual Remediation Required

**What's missing in this package:**
- _Actual exported BladeLogic objects_: You must create BlPackages/Component Templates in your BladeLogic environment, using the provided scripts/templates.
- _Patch Catalog setup_: Define and sync patch catalogs in BladeLogic as per your vendor requirements.
- _Server targeting/grouping_: Create and assign server smart groups as per your infrastructure.

**To Remediate:**
- **Follow the README steps above** to create all necessary objects in your own BladeLogic instance.
- **Customize all scripts/templates** for your exact OS versions, patch sources, compliance nuances.
- **Regularly update** patch catalog and compliance templates as new regulations and vulnerabilities emerge.

---

## Support

If you have questions about any script or template, refer to BladeLogic documentation or reach out to your BMC support representative.
