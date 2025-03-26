#!/usr/bin/env python3

import argparse
import json
import jwt
import logging
import os
import sys
import time
import urllib.request

def parse_args():
  parser = argparse.ArgumentParser(description='Retrieve metrics from the Copilot Usage API using a GitHub App or PAT')
  parser.add_argument('org', help='Organization to query', default=os.environ.get('GH_ORG'))
  parser.add_argument('-v', '--verbose', help='Additional logging of method calls (contains sensitive data)',
                      action='store_true')
  app_group = parser.add_argument_group('GitHub App', 'Arguments for configuring a GitHub App')
  app_group.add_argument('-p', '--pem_file', dest='pem_file', metavar='PATH', help='Path to the PEM file', default=os.environ.get('GH_PEM_PATH'))
  app_group.add_argument('-c', '--client_id', dest='client_id', metavar='ID', help='Client ID (or App ID) for the GitHub App', type=str, default=os.environ.get('GH_APP_ID'))

  pat_group = parser.add_argument_group('Personal Access Token', 'Arguments for configuring a Personal Access Token')
  pat_group.add_argument('-t', '--token', help='Organization name')

  args = parser.parse_args()
  if len(sys.argv)==1:
    parser.print_help(sys.stderr)
    sys.exit(1)

  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

  if args.token and (args.pem_file or args.client_id):
    parser.error('You cannot use both a Personal Access Token and a GitHub App')
    exit(1)

  pem = args.pem_file if args.pem_file else os.getenv('GH_PEM_FILE', None)
  client_id = args.client_id if args.client_id else os.getenv('GH_CLIENT_ID', None)
  token = args.token if args.token and not (pem or client_id) else os.getenv('GH_TOKEN', None)
  
  organization = args.org if args.org else input('Enter organization name: ')

  if not organization or (not token and (not pem or not client_id)):
    parser.print_help(sys.stderr)
    parser.error('You must specify an organization name and either a Personal Access Token or a GitHub App')
    sys.exit(1)
  
  return (pem, client_id, token, organization)

def invoke_json_api(url, token, method='GET'):
  logging.debug(f'Querying URL ({method}): {url}')
  request = urllib.request.Request(url, method=method)
  request.add_header('Authorization', f'Bearer {token}')
  try:
    return urllib.request.urlopen(request)
  except urllib.error.HTTPError as e:
      logging.error(f'HTTP Error: {e.code} - {e.reason}')
      logging.error(e.read().decode('utf-8'))
      raise
  except urllib.error.URLError as e:
      logging.error(f'URL Error: {e.reason}')
      raise

def get_installation_id(encoded_jwt, organization):
  with invoke_json_api('https://api.github.com/app/installations', encoded_jwt, 'GET') as response:
    data = json.load(response)
    for el in data:
      install_id = el['id']
      org_name = el['account']['login']
      logging.debug(f'Installation {install_id}: {org_name}')
      if org_name == organization:
        return install_id
  raise ValueError(f'Installation ID not found for organization: {organization}')

def create_encoded_jwt(pem, client_id):
  # Open PEM
  with open(pem, 'rb') as pem_file:
      signing_key = pem_file.read()
  
  payload = {
      # Issued at time
      'iat': int(time.time()),
      # JWT expiration time (10 minutes maximum)
      'exp': int(time.time()) + 600,
      
      # GitHub App's client ID
      'iss': client_id
  }
  
  # Create JWT
  encoded_jwt = jwt.encode(payload, signing_key, algorithm='RS256')
  
  return encoded_jwt

def get_access_token(encoded_jwt, installation_id):
  with invoke_json_api(f'https://api.github.com/app/installations/{installation_id}/access_tokens', encoded_jwt, 'POST') as response:
    data = json.load(response)
    token = data['token']
    return token
  
def revoke_access_token(token):
  invoke_json_api('https://api.github.com/installation/token', token, 'DELETE')

def get_copilot_metrics(token, organization):
  with invoke_json_api(f'https://api.github.com/orgs/{organization}/copilot/metrics', token, 'GET') as response:
    contents = response.read().decode('utf-8')
    return contents

def main():
  (pem, client_id, pat, organization) = parse_args()
  token = pat
  if not pat:
    encoded_jwt = create_encoded_jwt(pem, client_id)
    installation_id = get_installation_id(encoded_jwt, organization)
    token = get_access_token(encoded_jwt, installation_id)
  print (get_copilot_metrics(token, organization))

  if not pat:
    revoke_access_token(token)

main()
