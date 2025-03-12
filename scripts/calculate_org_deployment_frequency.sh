#!/bin/bash
# 1. Log in via `gh auth login`
# 2. chmod +x calculate_org_deployment_frequency.sh
# 3. Run ./calculate_org_deployment_frequency.sh

# Variables
ORG=$1

# Fetch repositories
repos=$(gh repo list $ORG --limit 1000 --json name -q '.[].name')

calculate_frequency() {
  local repo=$1
  deployments=$(gh api repos/$ORG/$repo/deployments)
  current_time=$(date +%s)
  thirty_days_ago=$(($current_time - 15768000)) # 6 months in seconds

  successful_deployments=0

	for deployment in $(echo $deployments | jq -r '.[] | select(.created_at | fromdateiso8601 > '$thirty_days_ago') | .id'); do
		statuses=$(gh api repos/$ORG/$repo/deployments/$deployment/statuses | jq -r '.[].state')
		for status in $statuses; do
			if [ "$status" == "success" ]; then
				successful_deployments=$((successful_deployments + 1))
				break
			fi
		done
	done

  echo "$repo: Total successful deployments in the last 30 days: $successful_deployments"
}

# Iterate over repositories and calculate deployment frequency
for repo in $repos; do
  calculate_frequency $repo
done