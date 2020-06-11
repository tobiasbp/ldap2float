FROM python:3-alpine

# The config file
COPY ldap2float.conf /etc/

# The actual script
COPY ldap2float.py /usr/local/bin/

# List of Python libraries to install
COPY requirements.txt .

# Install Python packages
RUN pip install --requirement requirements.txt

# The command to run
ENTRYPOINT [ "python", "/usr/local/bin/ldap2float.py", "/etc/ldap2float.conf"]
