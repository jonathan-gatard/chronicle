---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment (please complete the following information):**
 - Home Assistant Version: [e.g. 2023.10.0]
 - Scribe Version: [e.g. 1.11.0]
 - Database: [e.g. PostgreSQL 15 / TimescaleDB 2.11]

**Logs**
Please provide relevant logs from Home Assistant. Ensure debug logging is enabled for `custom_components.scribe`.

```yaml
logger:
  default: info
  logs:
    custom_components.scribe: debug
```

**Additional context**
Add any other context about the problem here.
