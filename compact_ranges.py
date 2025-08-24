#!/usr/bin/env python3

import json
import requests
import sys
from ipaddress import IPv4Network, IPv6Network, collapse_addresses

# This script fetches the AWS IP ranges, extracts the IPv4 and IPv6 prefixes,
# and then coalesces them into the most compact representation possible.
# The coalescing process merges adjacent or overlapping CIDR blocks where
# possible, reducing the total number of entries.
#
# The script is designed to be run as part of a GitHub Actions workflow.
# It takes the input JSON and produces a new, compacted JSON file.
#
# Co-written with Google Gemini (1.5 Pro, 2025-08-24)

# Define the URL for the AWS IP ranges JSON file.
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"

def get_ip_ranges():
    """
    Fetches the AWS IP ranges JSON from the specified URL.

    Args:
        None

    Returns:
        dict: A dictionary containing the parsed JSON data, or None on error.
    """
    try:
        # Use requests to get the data from the URL.
        response = requests.get(AWS_IP_RANGES_URL, timeout=10)
        # Raise an HTTPError for bad responses (4xx or 5xx).
        response.raise_for_status()
        # Parse the JSON and return the data.
        return response.json()
    except requests.RequestException as e:
        # If there's a request error, print it to stderr and exit.
        print(f"Error fetching IP ranges: {e}", file=sys.stderr)
        sys.exit(1)

def coalesce_prefixes(prefixes, ip_version):
    """
    Coalesces a list of IP prefixes.

    Args:
        prefixes (list): A list of IP prefix strings (e.g., '1.2.3.0/24').
        ip_version (int): The IP version to use (4 for IPv4, 6 for IPv6).

    Returns:
        list: A sorted list of coalesced IP network objects.
    """
    if ip_version == 4:
        # Create IPv4Network objects for each prefix.
        networks = [IPv4Network(p) for p in prefixes]
    elif ip_version == 6:
        # Create IPv6Network objects.
        networks = [IPv6Network(p) for p in prefixes]
    else:
        # Exit with an error for an invalid IP version.
        print("Invalid IP version specified.", file=sys.stderr)
        sys.exit(1)

    # Use the collapse_addresses function to merge the networks.
    return list(collapse_addresses(networks))

def main():
    """
    Main function to orchestrate the fetching, processing, and output.
    """
    # Get the raw data from the AWS URL.
    raw_data = get_ip_ranges()

    # If data fetching failed, exit.
    if not raw_data:
        sys.exit(1)

    # Extract IPv4 prefixes from the 'prefixes' key.
    ipv4_prefixes = [p['ip_prefix'] for p in raw_data.get('prefixes', [])]

    # Extract IPv6 prefixes from the 'ipv6_prefixes' key.
    ipv6_prefixes = [p['ipv6_prefix'] for p in raw_data.get('ipv6_prefixes', [])]

    # Coalesce the IPv4 prefixes.
    coalesced_ipv4 = coalesce_prefixes(ipv4_prefixes, 4)
    # Coalesce the IPv6 prefixes.
    coalesced_ipv6 = coalesce_prefixes(ipv6_prefixes, 6)

    # Prepare the output dictionary.
    output_data = {
        'creationDate': raw_data.get('createDate'),
        'syncToken': raw_data.get('syncToken'),
        'ipv4_prefixes': sorted([str(n) for n in coalesced_ipv4]),
        'ipv6_prefixes': sorted([str(n) for n in coalesced_ipv6])
    }

    # Write the compacted data to a JSON file.
    # The file is saved with the name 'ip-ranges-compacted.json'.
    with open("ip-ranges-compacted.json", "w") as f:
        # Use indentation for readability in the output file.
        json.dump(output_data, f, indent=2)

    print("Successfully created ip-ranges-compacted.json")


if __name__ == "__main__":
    main()
