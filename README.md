# ldap2float
A tool for syncing data available via LDAP with the project management service Float.com

# To do
- [X] Format of expected date string must be configurable.
- [ ] Mapping of LDAP fields to Float fields must be configurable.
- [X] Raise an exception if date from ldap could not be converted to valid Float date YYYY-MM-DD. 
- [ ] Add support for sending events via WebHook.
- [ ] Add dry-run option from CLI. Should be default.
- [ ] Option for creating departmens in Float based on LDAP structure.
- [ ] Add dockerfile and configuration files for running with Docker and as k8s cron job.
- [ ] If no LDAP group is specified, all users found beneath the LDAP base should be added to FLOAT
- [ ] Run flake (or similar) to check code
