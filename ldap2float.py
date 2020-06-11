#!/usr/bin/env python3
import argparse
import os
from datetime import datetime, date , timedelta
import logging
import re

import ldap3
import configparser
import ssl

from float_api import FloatAPI, UnexpectedStatusCode

# The regex to use when checking validity of dates used in Float
FLOAT_DATE_REGEX = "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"

parser = argparse.ArgumentParser(
  allow_abbrev=False,
  description="Sync users from LDAP to Float"
  )

# Config file from command line
parser.add_argument(
  'config',
  metavar='/path/to/config.conf',
  help="Path to the configuration file"
  )

# Parse the command line arguments
args = parser.parse_args()


# Object for parsing config file
# Use raw in order to not do interpolation
config = configparser.RawConfigParser()

# Default config (Applies to ALL sections)
# Do not override domain by default
config['DEFAULT'] = {'email_domain_overrides': []}

# Read the config file
config.read(args.config)

# Handler to use for logging. Use stdout if no file configured
try:
  h = logging.FileHandler(config.get("logging","file"))
except configparser.NoOptionError:
  h = logging.StreamHandler()

# Configure logging
logging.basicConfig(
  level = eval("logging." + config.get("logging","level").upper()),
  format='%(asctime)s:%(levelname)s:%(message)s',
  handlers = [h]
  )

logging.debug("Logging handler: {}".format(h))
logging.info("Running ldap2float.py")

# Float accounts will be deleted if end_date is this many days in the past
delete_after_days = int(config.get('conf', 'delete_after_days'))
if not delete_after_days > 0:
  e = ("Config delete_after_days must be positive. Value is {}."
    .format(delete_after_days))
  raise ValueError(e)

# The maximum numbers of Float users to delete in an invocation
max_users_to_delete = int(config.get('conf', 'max_users_to_delete'))
if not delete_after_days >= 0:
  e = ("Config max_users_to_delete must be non negative. Value is {}."
    .format(max_users_to_delete))
  raise ValueError(e)

# List of valid Float guests (Account with no matching people).
valid_guests = eval(config.get("conf","valid_guests"))
if not isinstance(valid_guests, list):
  e = ("Config valid_guests must be a list. Value is {}."
    .format(valid_guests))
  raise ValueError(e)

# email_domain_overrides
email_domain_overrides = eval(config.get("float","email_domain_overrides"))
if not isinstance(email_domain_overrides, list):
  e = ("Config email_domain_overrides must be a list. Value is {}."
    .format(email_domain_overrides))
  raise ValueError(e)

# Domain overrides must be pairs
for pair in email_domain_overrides:
  if not len(pair) == 2:
    e = ("Config email_domain_overrides must be a list of pairs. Found {}."
      .format(pair))
    raise ValueError(e)

# The string ti use when parsing data strings from LDAP
LDAP_DATE_STRING = config.get("conf","ldap_date_string")


# Create a Float API object
float_api = FloatAPI(
  config.get("float","access_token"),
  config.get("float","application_name"),
  config.get("float","contact_email")
)

# Department from config
# FIXME: Should be optional
#department = config.get("data","department")

'''
print("accounts:")
accounts = float_api.get_all_accounts()
for a in accounts:
  print(a)

print("people:")
people = float_api.get_all_people()
for p in people:
  print(p)
'''


#################################################
# Delete users in Float with no email (Our key) #
#################################################

try:
  for p in float_api.get_all_people():
    # Look for missing email
    if not p['email']:
      # Delete person
      r = float_api.delete_person(p['people_id'])
      logging.warning("Deleted float user '{}' because of missing email"
        .format(p['name']))
except Exception as e:
  message = "Could not get users from Float with error: {}".format(e)
  logging.error(message)
  # Inform the user
  print("Error:", message)
  # Exit programme with error
  exit(1)

# Dict of people in float with email as key
float_people = float_api.get_all_people()
float_people = {data['email']: data for data in float_people if data['email']}

#print(float_people.keys())

# TLS configuration fort the LDAP connection
#tls_configuration = ldap3.Tls(
#  validate=ssl.CERT_NONE,
#  version=ssl.PROTOCOL_TLSv1
#  )


# The LDAP server
ldap_server = ldap3.Server(
  config.get("ldap","url"),
  #tls=tls_configuration,
  #port=389
  )


# Connect to the LDAP server
ldap_connection = ldap3.Connection(
  ldap_server,
  config.get("ldap","user_dn"),
  config.get("ldap","user_pass"),
  auto_bind=False
  )

ldap_connection.open()
ldap_connection.start_tls()
ldap_connection.bind()

# Get the group from LDAP
ldap_connection.search(
  config.get("ldap","group_dn"),
  "(objectClass=*)",
  search_scope=ldap3.BASE,
  attributes=['*']
  )

# Must have a single group
assert len(ldap_connection.entries) == 1, "No of matching groups must be 1"

# UIDs of valid users (Group members)
valid_ldap_users = []

# Get the list of group members
# FIXME: Value holding members should be configurable
# FIXME: Do I really need to loop here?
for x in ldap_connection.entries:
  valid_ldap_users = x.memberUid.value


# Search for people in LDAP
ldap_connection.search(
  config.get("ldap","base"),
  config.get("ldap","filter"),
  attributes=['cn','uid','mail','title','employeeType', 'fdContractStartDate', 'fdContractEndDate']
  )


# FIXME: Add sdictionary which maps LDAP attributes to float fields

def email_override(old_email):
  """
  Input an email. Returns email with overridden domain (If applicable)
  """
  new_email = old_email
  # Look through domains to override
  for old_domain, new_domain in email_domain_overrides:
    new_email = old_email.replace(old_domain, new_domain)

  # Log if mail changed
  if not new_email == old_email:
    #logging.debug("Email override: {} > {}".format(old_email, new_email)) 
    pass
  # Return potentially changed email
  return new_email


def ldap_person2float_person(ldap_person):
  """
  Takes data for an LDAP person and converts to a
  dictionary of Float Person.
  """
  logging.debug("LDAP data to convert to Float data: {}".format(ldap_person))

  # The dict to return
  float_data = {
    'name': None,
    'email': None,
    'job_title': None,
    'start_date': None,
    'end_date': None,
    #'department': None,
    'active': 1,
    'employee_type': 0, # Part time
    'people_type_id': 2, # contractor
    }

  # Person's name
  if ldap_person.cn.value:
    float_data['name'] = ldap_person.cn.value

  # Person's email
  if ldap_person.mail.value:
    float_data['email'] = email_override(ldap_person.mail.value)

  # Person's title
  if ldap_person.title.value:
    if isinstance(ldap_person.title.value, list):
      float_data['job_title'] = ', '.join(ldap_person.title.value)
    else:
      float_data['job_title'] = ldap_person.title.value

  # Person's start date
  if ldap_person.fdContractStartDate.value:
    float_data['start_date'] = ldap_date2string(
      ldap_person.fdContractStartDate.value)

  # Person's end date
  if ldap_person.fdContractEndDate.value:
    float_data['end_date'] = ldap_date2string(
      ldap_person.fdContractEndDate.value)

  # Inactive if last day is in the past
  if float_data['end_date']:
    ed = datetime.strptime(float_data['end_date'],'%Y-%m-%d').date()
    if ed < datetime.today().date():
      float_data['active'] = 0

  # Employee in LDAP is full time in float
  if ldap_person.employeeType.value == 'employee':
    # 1=full time, 0=part time
    float_data['employee_type'] = 1

  # Employee in LDAP is employee in float
  if ldap_person.employeeType.value == 'employee':
    float_data['people_type_id'] = 1

  return float_data


def float_user_needs_update(float_data, latest_data):
  """
  Return False if all values in latest_data matches
  all values in float_data. Return Trues otherwise
  indicating that the data in Float needs to be updated
  """
  # Loop through latest data
  for key, value in latest_data.items():
    # Look for mismatches
    if value != float_data[key]:
      # Found a mismatch. Needs to update
      return True

  # No need to update since all values matched
  return False


def ldap_date2string(ldap_date):
  '''
  Convert LDAP date in to a Float compatible date. YYYY-MM-DD.
  Input can be a string or a date object
  '''

  date_string = None

  # Try to convert the date from a string
  try:
    date_string = datetime.strptime(
      ldap_date,
      LDAP_DATE_STRING,
      ).date().isoformat()
  except Exception as e:
    logging.debug("Could not create date from string: {}".format(e))

  # Try to convert from date object
  try:
    date_string = ldap_date.date().isoformat()
  except Exception as e:
    logging.debug("Could not create date from date object: {}".format(e))

  # We could not parse the date
  if not date_string:
    m = "Could not convert date from LDAP: {}".format(ldap_date)
    logging.error(m)
    raise ValueError(m)

  # Raise exception if converted date is not what we expect
  if not re.match(FLOAT_DATE_REGEX, date_string):
    m = ("Converted date from LDAP '{}' does not match YYYY-MM-DD"
      .format(date_string))
    logging.error(m)
    raise ValueError(m)

  return date_string


# A set of emails of LDAP users
ldap_user_emails = set(
  email_override(user.mail.value) for user in ldap_connection.entries
  )

# Debug
logging.debug('Processing {} users from LDAP'.format(len(ldap_user_emails)))

# Create LDAP users not in Float
for p_ldap in ldap_connection.entries:

  # Make sure user is a member of the LDAP group
  if p_ldap.uid.value in valid_ldap_users:
    logging.debug("User {} is member of LDAP group with Float users"
      .format(p_ldap.cn.value))
  else:
    logging.debug("User {} not member of LDAP group with Float users"
      .format(p_ldap.cn.value))
    # Do not process this user
    continue

  # Convert the curent user's data to a dict with Float keys
  float_data = ldap_person2float_person(p_ldap)

  # If user has an end date
  if float_data['end_date']:

    # Convert end date to date object
    d = float_data['end_date'].split('-')
    e_d = date(int(d[0]), int(d[1]), int(d[2]))

    # Do not create user if end_date is in the past
    if e_d < datetime.today().date():
      logging.debug("Not creating Float user '{}' because end_date is in the past".format(float_data['name']))
      continue

  # Create user not in float based on email
  if email_override(p_ldap.mail.value) not in float_people.keys():

    # Add the LDAP user to Float
    try:
      r = float_api.create_person(**float_data)
    except (UnexpectedStatusCode, DataValidationError) as e:
      logging.error("Could not add user '{}' to Float. Error was: {}"
        .format(float_data['name'], e))
    else:
      logging.info("Added user '{}' to Float"
        .format(float_data['name']))
      continue
  else:
    logging.debug("User '{}' already in Float. Not adding"
      .format(float_data['name']))


# Update Float users with LDAP data
for p_ldap in ldap_connection.entries:

  # Do nothing if LDAP user is not a current Float user
  if email_override(p_ldap.mail.value) not in float_people.keys():
    continue

  # Convert the curent user's data to a dict with Float keys
  float_data = ldap_person2float_person(p_ldap)
 
  # If LDAP user is in Float, but not in LDAP Float group.
  if p_ldap.uid.value not in valid_ldap_users:
    logging.debug("User {} is in Float, but not member of Float access group"
      .format(p_ldap.cn.value))
    try:
      # Look up the Float people_id
      people_id = float_people[float_data['email']]['people_id']

      # Delete the Float person
      r = float_api.delete_person(people_id)

    except (UnexpectedStatusCode, DataValidationError) as e:
      # Log the error
      logging.error("Could not delete user '{}' from Float with error: '{}'"
        .format(float_data['name'], e)
        )
    else:
      # Log the deletion of the person
      logging.info("Deleted LDAP user '{}' from Float. Not a member of LDAP group."
        .format(float_data['name'])
        )
      # Don't process this LDAP user further
      continue

  # Update existing Float person if needed
  if float_user_needs_update(
    float_people[float_data['email']],
    float_data
    ):

    # Add the float people_id to the person data from LDAP
    float_data['people_id'] = float_people[float_data['email']]['people_id']

    # Update person in Float
    try:
      r = float_api.update_person(**float_data)
    except (UnexpectedStatusCode, DataValidationError) as e:
      logging.error("Could not update Float user '{}'. Error was: {}"
        .format(float_data['name'], e))
    else:
      logging.info("Updated Float user '{}'".format(float_data['name']))

  else:
    logging.debug("No need to update Float user '{}'".format(float_data['name']))


# Delete Float users matching expired LDAP users
float_users_deleted = 0
for p_ldap in ldap_connection.entries:

  # Do nothing if LDAP user is not in Float
  if email_override(p_ldap.mail.value) not in float_people.keys():
    continue
  
  # Convert the curent user's LDAP data to a dict with Float keys
  float_data = ldap_person2float_person(p_ldap)

  # Do nothing if user has no end date
  if float_data['end_date'] == None:
    continue

  # Convert end date to date object
  d = float_data['end_date'].split('-')
  e_d = date(int(d[0]), int(d[1]), int(d[2]))

  # Delete if user's end_date is too far in the past
  if e_d + timedelta(days=delete_after_days) < datetime.today().date():

    # Float data for the user to delete
    user_to_delete = float_people[email_override(p_ldap.mail.value)]
    
    # Do not delete if max_users_to_delete reached
    if float_users_deleted >= max_users_to_delete:
      logging.warning("Not deleting float user '{}' because {} users already deleted in this invocation"
        .format(float_data['name'], float_users_deleted))
    else:

      # Delete the user from Float
      try:
          result = float_api.delete_person(user_to_delete['people_id'])
      except (UnexpectedStatusCode, DataValidationError) as e:
        # Log error if we got unexpected status code
        logging.error("Could not delete user '{}' in Float. Error was '{}'"
          .format(float_data['name'], e))
      else:
          # Log the deletion
          logging.info("Deleted Float user '{}' because end_date '{}' is +{} days in the past"
            .format(float_data['name'], float_data['end_date'], delete_after_days))
          float_users_deleted += 1


# A set of emails of float users not matching LDAP users
float_emails_not_in_ldap = float_people.keys() - ldap_user_emails

# Warn about float users with email not matching an LDAP user
for fu_mail in float_emails_not_in_ldap:
  logging.warning("Float user '{}' with email '{}' not in LDAP"
    .format(float_people[fu_mail]['name'], fu_mail))

# Warn about accounts with no matching people (A guest)
try:
  accounts = float_api.get_all_accounts()
except (UnexpectedStatusCode, DataValidationError) as e:
  logging.error("Could not get Float accounts. Error was: {}".format(e))
else:
  for a in accounts:
    # Ignore valid guests
    if a['email'] in valid_guests:
      continue
  
    # Warn about unknown guests
    if a['email'] not in float_people.keys():
      logging.warning("Account with name '{}' and email '{}' has no matching people object"
        .format(a['name'], a['email']))


logging.info("Done running ldap2float.py")
