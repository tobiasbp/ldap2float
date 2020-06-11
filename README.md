# ldap2float
A tool for syncing data available via LDAP with the project management service Float.com

# Run in Docker

* Clone repository
* Copy `ldap2float.conf` and modify. In this example I assume it's at `/example/path/ldap2float.conf`
* Build the image: `docker build --tag ldap2float .`
* When running the container, we will map our local config file to the file used in the container.
* Run a container to test: `docker run --rm -v /example/path/ldap2float.conf:/etc/ldap2float.conf ldap2float ldap2float`
* Set up a cron job to run (and delete) the container as above

# To do
- [X] Format of expected date string must be configurable.
- [ ] Mapping of LDAP fields to Float fields must be configurable.
- [X] Raise an exception if date from ldap could not be converted to valid Float date YYYY-MM-DD. 
- [ ] Add support for sending events via WebHook.
- [ ] Add dry-run option from CLI. Should be default.
- [ ] Option for creating departmens in Float based on LDAP structure.
- [X] Add configuration files for running with Docker.
- [ ] Add configuration files for running with Kubernetes as a cron job.
- [ ] If no LDAP group is specified, all users found beneath the LDAP base should be added to Float
- [ ] Run flake (or similar) to check code
- [ ] Accept configuration parameters as environment variables
