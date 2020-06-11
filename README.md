# ldap2float
A tool for syncing data available via LDAP with the project management service Float at float.com.
No data is written to the LDAP server.

# Run locally

* Clone repository
* Install Pythob packages: `pip3 install -r requirements.txt`
* Copy *ldap2float.conf* to *ldap2float.local.conf*
* Update *ldap2float.local.conf* with your configuration.
* Run ldap2float: `./ldap2float ./ldap2float.local.conf`

# Run in Docker

* Clone repository
* Copy *ldap2float.conf* to */example/path/ldap2float.conf* (An example path).
* Update */example/path/ldap2float.conf* with your configuration.
* Build the image: `docker build --tag ldap2float .`
* Run a container to test: `docker run --rm -v /example/path/ldap2float.conf:/etc/ldap2float.conf ldap2float`
* You should see the log from ldap2float confirming a successful run.
* Set up a cron job to run the container as in the example above.

Using the flag *--rm* removes the container after each run of ldap2float.
If you don't do that, you will end up with a lot of unused containers.

# Run with Kubernetes
This section assumes you have a Kubernetes cluster up and running.
Files mentioned in this section are in the directory called *k8s*.

* Clone repository
* Copy *ldap2float-config.yml* to *ldap2float-config.local.yml* and edit it to match your configuration.
* Create new namespace *automation* in Kubernetes: `kubectl create -f ldap2float-namespace.yml`
* Add your ldap2float configuration to Kubernetes: `kubectl create -f ldap2float-config.yml`
* Add cronjob to Kubernetes: `kubectl create -f ldap2float-cronjob.yml`

Let's see what's in the namespace *automation*: `kubectl get all -n automation`

You should see something like this:
```
NAME                       SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/ldap2float   */5 * * * *   False     0        <none>          4m29s
```

After the cron job has run successfully, you should see something like this:
```
NAME                              READY   STATUS      RESTARTS   AGE
pod/ldap2float-1591876800-6jwkj   0/1     Completed   0          110s

NAME                              COMPLETIONS   DURATION   AGE
job.batch/ldap2float-1591876800   1/1           24s        110s

NAME                       SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/ldap2float   */5 * * * *   False     0        111s            6m20s
``` 


Let's list all the pods in the namespace: `kubect get pods -n automation`
```
NAME                          READY   STATUS      RESTARTS   AGE
ldap2float-1591877400-f4wf8   0/1     Completed   0          11m
ldap2float-1591877700-p9h4f   0/1     Completed   0          6m44s
ldap2float-1591878000-p5wsk   0/1     Completed   0          102s
```

See the log for a pod: `kubectl logs -n automation ldap2float-1591878000-p5wsk`
```
2020-06-11 12:00:22,440:INFO:Running ldap2float.py
...
...
2020-06-11 12:00:23,596:INFO:Done running ldap2float.py
```

Kubernes will keep the pods for the last 3 runs of ldap2float. Older pods will be deleted automatically.
Since the logs are a part of the completed jobs, you will only be able to see the logs for the last
3 jobs (In the default configuration) 

# To do
- [X] Format of expected date string must be configurable.
- [ ] Mapping of LDAP fields to Float fields must be configurable.
- [X] Raise an exception if date from ldap could not be converted to valid Float date YYYY-MM-DD. 
- [ ] Add support for sending events via WebHook.
- [ ] Add dry-run option from CLI. Should be default.
- [ ] Option for creating departmens in Float based on LDAP structure.
- [X] Add configuration files for running with Docker.
- [X] Add configuration files for running with Kubernetes as a cron job.
- [ ] If no LDAP group is specified, all users found beneath the LDAP base should be added to Float
- [ ] Run flake (or similar) to check code
- [ ] Accept configuration parameters as environment variables
- [ ] Allow for logging to stdout and file at the same time
