#!/usr/bin/env python3

import json
import requests
import sys
from ipaddress import IPv4Network, IPv6Network, collapse_addresses, ip_network
from collections import defaultdict
from datetime import datetime

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

def coalesce_with_metadata(prefixes_data, ip_version):
    """
    Coalesces IP prefixes while preserving metadata where possible.
    
    Args:
        prefixes_data (list): List of dictionaries containing prefix and metadata
        ip_version (int): IP version (4 or 6)
    
    Returns:
        list: List of dictionaries with coalesced prefixes and appropriate metadata
    """
    # Group prefixes by their metadata
    grouped = defaultdict(list)
    prefix_key = 'ip_prefix' if ip_version == 4 else 'ipv6_prefix'
    
    for entry in prefixes_data:
        metadata_key = (
            entry.get('region', 'other'),
            entry.get('service', 'OTHER'),
            entry.get('network_border_group', 'other')
        )
        grouped[metadata_key].append(entry[prefix_key])
    
    # Coalesce within each metadata group
    result = []
    networks_with_metadata = []
    
    for (region, service, nbg), prefixes in grouped.items():
        coalesced = coalesce_prefixes(prefixes, ip_version)
        for network in coalesced:
            networks_with_metadata.append({
                'network': network,
                'region': region,
                'service': service,
                'network_border_group': nbg
            })
    
    # Check for overlaps between different metadata groups
    # and merge with "other" metadata if networks can be combined
    processed = []
    skip_indices = set()
    
    for i, entry1 in enumerate(networks_with_metadata):
        if i in skip_indices:
            continue
            
        can_merge = []
        for j, entry2 in enumerate(networks_with_metadata[i+1:], start=i+1):
            if j in skip_indices:
                continue
            
            # Check if networks are adjacent or overlapping
            if entry1['network'].overlaps(entry2['network']) or \
               entry1['network'].supernet_of(entry2['network']) or \
               entry2['network'].supernet_of(entry1['network']):
                can_merge.append(j)
                skip_indices.add(j)
        
        if can_merge:
            # Merge networks with different metadata
            networks_to_merge = [entry1['network']]
            metadata_matches = True
            
            for idx in can_merge:
                networks_to_merge.append(networks_with_metadata[idx]['network'])
                if (networks_with_metadata[idx]['region'] != entry1['region'] or
                    networks_with_metadata[idx]['service'] != entry1['service'] or
                    networks_with_metadata[idx]['network_border_group'] != entry1['network_border_group']):
                    metadata_matches = False
            
            merged = list(collapse_addresses(networks_to_merge))
            for network in merged:
                if metadata_matches:
                    processed.append({
                        'network': network,
                        'region': entry1['region'],
                        'service': entry1['service'],
                        'network_border_group': entry1['network_border_group']
                    })
                else:
                    processed.append({
                        'network': network,
                        'region': 'other',
                        'service': 'OTHER',
                        'network_border_group': 'other'
                    })
        else:
            processed.append(entry1)
    
    # Convert to final format
    for entry in processed:
        if ip_version == 4:
            result.append({
                'ip_prefix': str(entry['network']),
                'region': entry['region'],
                'service': entry['service'],
                'network_border_group': entry['network_border_group']
            })
        else:
            result.append({
                'ipv6_prefix': str(entry['network']),
                'region': entry['region'],
                'service': entry['service'],
                'network_border_group': entry['network_border_group']
            })
    
    # Sort by network address
    if ip_version == 4:
        result.sort(key=lambda x: IPv4Network(x['ip_prefix']))
    else:
        result.sort(key=lambda x: IPv6Network(x['ipv6_prefix']))
    
    return result

def write_txt_file(data, filename, description):
    """
    Extract all CIDR blocks and write to text file with statistics.
    
    Args:
        data (dict): JSON data containing prefixes
        filename (str): Output filename
        description (str): Description for the header
    """
    ipv4_cidrs = []
    ipv6_cidrs = []
    
    # Extract IPv4 prefixes
    for entry in data.get('prefixes', []):
        ipv4_cidrs.append(entry['ip_prefix'])
    
    # Extract IPv6 prefixes
    for entry in data.get('ipv6_prefixes', []):
        ipv6_cidrs.append(entry['ipv6_prefix'])
    
    # Sort separately
    ipv4_cidrs.sort(key=lambda x: IPv4Network(x))
    ipv6_cidrs.sort(key=lambda x: IPv6Network(x))
    
    # Write to file with header
    with open(filename, 'w') as f:
        # Write header with statistics
        f.write(f"# AWS IP Ranges - {description}\n")
        f.write(f"# Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"# Source: {AWS_IP_RANGES_URL}\n")
        f.write(f"# Creation Date: {data.get('createDate', 'Unknown')}\n")
        f.write(f"# Sync Token: {data.get('syncToken', 'Unknown')}\n")
        f.write(f"#\n")
        f.write(f"# Statistics:\n")
        f.write(f"# Total CIDR blocks: {len(ipv4_cidrs) + len(ipv6_cidrs)}\n")
        f.write(f"# IPv4 blocks: {len(ipv4_cidrs)}\n")
        f.write(f"# IPv6 blocks: {len(ipv6_cidrs)}\n")
        f.write(f"#\n")
        f.write(f"# ========== IPv4 Prefixes ({len(ipv4_cidrs)} entries) ==========\n")
        f.write("#\n")
        
        # Write IPv4 prefixes
        for cidr in ipv4_cidrs:
            f.write(f"{cidr}\n")
        
        # Separator and IPv6 header
        f.write("\n")
        f.write(f"# ========== IPv6 Prefixes ({len(ipv6_cidrs)} entries) ==========\n")
        f.write("#\n")
        
        # Write IPv6 prefixes
        for cidr in ipv6_cidrs:
            f.write(f"{cidr}\n")
    
    print(f"Successfully created {filename} (IPv4: {len(ipv4_cidrs)}, IPv6: {len(ipv6_cidrs)})")

def print_reduction_stats(original_data, compacted_data, merged_data):
    """
    Print reduction statistics comparing the three approaches.
    """
    original_ipv4 = len(original_data.get('prefixes', []))
    original_ipv6 = len(original_data.get('ipv6_prefixes', []))
    original_total = original_ipv4 + original_ipv6
    
    compacted_ipv4 = len(compacted_data.get('prefixes', []))
    compacted_ipv6 = len(compacted_data.get('ipv6_prefixes', []))
    compacted_total = compacted_ipv4 + compacted_ipv6
    
    merged_ipv4 = len(merged_data.get('prefixes', []))
    merged_ipv6 = len(merged_data.get('ipv6_prefixes', []))
    merged_total = merged_ipv4 + merged_ipv6
    
    print("\n========== Reduction Statistics ==========")
    print(f"Original:  {original_total:,} total ({original_ipv4:,} IPv4, {original_ipv6:,} IPv6)")
    print(f"Compacted: {compacted_total:,} total ({compacted_ipv4:,} IPv4, {compacted_ipv6:,} IPv6)")
    print(f"           Reduction: {(1 - compacted_total/original_total)*100:.1f}%")
    print(f"Merged:    {merged_total:,} total ({merged_ipv4:,} IPv4, {merged_ipv6:,} IPv6)")
    print(f"           Reduction: {(1 - merged_total/original_total)*100:.1f}%")
    print("==========================================\n")

def main():
    """
    Main function to orchestrate the fetching, processing, and output.
    """
    # Get the raw data from the AWS URL.
    raw_data = get_ip_ranges()

    # If data fetching failed, exit.
    if not raw_data:
        sys.exit(1)

    # Write the original AWS data to a JSON file.
    with open("ip-ranges-original.json", "w") as f:
        json.dump(raw_data, f, indent=2)
    print("Successfully created ip-ranges-original.json")
    
    # Write original data to text file
    write_txt_file(raw_data, "ip-ranges-original.txt", "Original")

    # Extract IPv4 prefixes from the 'prefixes' key.
    ipv4_prefixes = [p['ip_prefix'] for p in raw_data.get('prefixes', [])]

    # Extract IPv6 prefixes from the 'ipv6_prefixes' key.
    ipv6_prefixes = [p['ipv6_prefix'] for p in raw_data.get('ipv6_prefixes', [])]

    # Coalesce the IPv4 prefixes.
    coalesced_ipv4 = coalesce_prefixes(ipv4_prefixes, 4)
    # Coalesce the IPv6 prefixes.
    coalesced_ipv6 = coalesce_prefixes(ipv6_prefixes, 6)

    # Prepare the output dictionary in the same format as the original.
    compacted_data = {
        'syncToken': raw_data.get('syncToken'),
        'createDate': raw_data.get('createDate'),
        'prefixes': [
            {
                'ip_prefix': str(n),
                'region': 'other',
                'service': 'OTHER',
                'network_border_group': 'other'
            }
            for n in sorted(coalesced_ipv4)
        ],
        'ipv6_prefixes': [
            {
                'ipv6_prefix': str(n),
                'region': 'other',
                'service': 'OTHER',
                'network_border_group': 'other'
            }
            for n in sorted(coalesced_ipv6)
        ]
    }

    # Write the compacted data to a JSON file.
    with open("ip-ranges-compacted.json", "w") as f:
        json.dump(compacted_data, f, indent=2)
    print("Successfully created ip-ranges-compacted.json")
    
    # Write compacted data to text file
    write_txt_file(compacted_data, "ip-ranges-compacted.txt", "Compacted")

    # Create merged version with preserved metadata where possible
    merged_ipv4 = coalesce_with_metadata(raw_data.get('prefixes', []), 4)
    merged_ipv6 = coalesce_with_metadata(raw_data.get('ipv6_prefixes', []), 6)
    
    merged_data = {
        'syncToken': raw_data.get('syncToken'),
        'createDate': raw_data.get('createDate'),
        'prefixes': merged_ipv4,
        'ipv6_prefixes': merged_ipv6
    }
    
    # Write the merged data to a JSON file
    with open("ip-ranges-merged.json", "w") as f:
        json.dump(merged_data, f, indent=2)
    print("Successfully created ip-ranges-merged.json")
    
    # Write merged data to text file
    write_txt_file(merged_data, "ip-ranges-merged.txt", "Merged (Metadata Preserved)")
    
    # Print reduction statistics
    print_reduction_stats(raw_data, compacted_data, merged_data)


if __name__ == "__main__":
    main()
