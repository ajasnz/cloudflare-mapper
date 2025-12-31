#!/usr/bin/env python3
"""
Cloudflare DNS Record Mapper
Creates a hierarchical mindmap of DNS records based on their relationships.
"""

import sys
import json
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Dict, List, Set


class CloudflareDNSMapper:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, endpoint: str) -> dict:
        """Make a request to the Cloudflare API."""
        url = f"{self.base_url}{endpoint}"
        request = Request(url, headers=self.headers)
        
        try:
            with urlopen(request) as response:
                data = response.read()
                return json.loads(data)
        except HTTPError as e:
            error_body = e.read().decode()
            print(f"HTTP Error {e.code}: {error_body}", file=sys.stderr)
            sys.exit(1)
        except URLError as e:
            print(f"URL Error: {e.reason}", file=sys.stderr)
            sys.exit(1)
    
    def get_zones(self) -> List[dict]:
        """Fetch all zones accessible with the API token."""
        zones = []
        page = 1
        per_page = 50
        
        while True:
            response = self._make_request(f"/zones?page={page}&per_page={per_page}")
            
            if not response.get("success"):
                print(f"Error fetching zones: {response.get('errors')}", file=sys.stderr)
                break
            
            zones.extend(response.get("result", []))
            
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            if page >= total_pages:
                break
            page += 1
        
        return zones
    
    def get_dns_records(self, zone_id: str) -> List[dict]:
        """Fetch all DNS records for a given zone."""
        records = []
        page = 1
        per_page = 100
        
        while True:
            response = self._make_request(f"/zones/{zone_id}/dns_records?page={page}&per_page={per_page}")
            
            if not response.get("success"):
                print(f"Error fetching DNS records: {response.get('errors')}", file=sys.stderr)
                break
            
            records.extend(response.get("result", []))
            
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            if page >= total_pages:
                break
            page += 1
        
        return records
    
    def build_hierarchy(self, all_records: List[dict]) -> Dict[str, List[str]]:
        """Build a parent-child relationship map based on DNS record values."""
        # Create a map of record name to record info
        record_map = {}
        for record in all_records:
            name = record["name"].lower().strip().rstrip('.')
            record_map[name] = record
        
        # Build parent-child relationships
        children_map = {}  # parent -> list of children
        
        for record in all_records:
            name = record["name"].lower().strip().rstrip('.')
            content = record.get("content", "").lower().strip().rstrip('.')
            record_type = record["type"]
            
            # Skip empty content
            if not content:
                continue
            
            # For CNAME, ALIAS, and similar records, the content is the parent
            if record_type in ["CNAME", "ALIAS", "DNAME"]:
                # The content (what this record points to) is the parent
                # Check if target exists in our records
                if content in record_map:
                    if content not in children_map:
                        children_map[content] = []
                    if name not in children_map[content]:  # Avoid duplicates
                        children_map[content].append(name)
            
            # For MX records, the content contains priority and hostname
            elif record_type == "MX":
                # MX content is like "10 mail.example.com"
                parts = content.split()
                if len(parts) >= 2:
                    mx_target = parts[1].strip().rstrip('.')
                    if mx_target in record_map:
                        if mx_target not in children_map:
                            children_map[mx_target] = []
                        if name not in children_map[mx_target]:
                            children_map[mx_target].append(name)
            
            # For SRV records
            elif record_type == "SRV":
                # SRV content is like "10 20 5060 sipserver.example.com"
                parts = content.split()
                if len(parts) >= 4:
                    srv_target = parts[3].strip().rstrip('.')
                    if srv_target in record_map:
                        if srv_target not in children_map:
                            children_map[srv_target] = []
                        if name not in children_map[srv_target]:
                            children_map[srv_target].append(name)
        
        return children_map, record_map
    
    def find_root_records(self, all_records: List[dict], children_map: Dict[str, List[str]], 
                         record_map: Dict[str, dict]) -> List[str]:
        """Find records that are not children of any other record (root nodes)."""
        all_children = set()
        for children in children_map.values():
            all_children.update(children)
        
        roots = set()  # Use set to avoid duplicates
        for record in all_records:
            name = record["name"].lower().rstrip('.')
            if name not in all_children:
                roots.add(name)
        
        return sorted(list(roots))
    
    def write_hierarchy(self, name: str, children_map: Dict[str, List[str]], 
                       record_map: Dict[str, dict], output: List[str], 
                       level: int = 0, visited: Set[str] = None):
        """Recursively write the hierarchy to output."""
        if visited is None:
            visited = set()
        
        # Avoid infinite loops
        if name in visited:
            return
        visited.add(name)
        
        # Write current node with proper markdown indentation
        indent = '  ' * level  # 2 spaces per level
        line = f"{indent}- {name}"
        output.append(line)
        
        # Write children recursively
        if name in children_map:
            for child in sorted(children_map[name]):
                self.write_hierarchy(child, children_map, record_map, output, 
                                   level + 1, visited)
    
    def generate_mindmap(self, output_file: str = "dns_hierarchy.md", exclude_txt: bool = False):
        """Generate the DNS hierarchy mindmap."""
        print("Fetching zones...")
        zones = self.get_zones()
        print(f"Found {len(zones)} zone(s)")
        
        all_records = []
        for zone in zones:
            zone_name = zone["name"]
            zone_id = zone["id"]
            print(f"Fetching DNS records for {zone_name}...")
            records = self.get_dns_records(zone_id)
            all_records.extend(records)
            print(f"  Found {len(records)} record(s)")
        
        # Filter out TXT records and related verification records if requested
        if exclude_txt:
            txt_types = ["TXT", "SPF", "DKIM", "DMARC"]
            original_count = len(all_records)
            all_records = [r for r in all_records if r["type"] not in txt_types]
            # Also filter out common verification/key subdomains
            all_records = [r for r in all_records if not any(
                prefix in r["name"].lower() for prefix in ["_dmarc", "_domainkey", "_acme", "_verification"]
            )]
            filtered_count = original_count - len(all_records)
            if filtered_count > 0:
                print(f"  Filtered out {filtered_count} TXT/verification record(s)")
        
        print(f"\nTotal records: {len(all_records)}")
        print("Building hierarchy...")
        
        children_map, record_map = self.build_hierarchy(all_records)
        
        # For root-level A/AAAA/CNAME records, make their IPs/targets the actual root
        # and the domains become children of those IPs/targets
        ip_parent_map = {}  # IP/target -> list of domains pointing to it
        domains_with_ip_parents = set()  # domains that have been moved under IPs
        
        for record in all_records:
            name = record["name"].lower().strip().rstrip('.')
            content = record.get("content", "").lower().strip().rstrip('.')
            record_type = record["type"]
            
            # Check if this is a root node (not a child of another domain)
            is_root = True
            for parent, children in children_map.items():
                if name in children:
                    is_root = False
                    break
            
            # For root-level A/AAAA/CNAME records, add IP/target as parent
            if is_root and content and record_type in ["A", "AAAA", "CNAME", "ALIAS", "DNAME"]:
                if content not in ip_parent_map:
                    ip_parent_map[content] = []
                ip_parent_map[content].append(name)
                domains_with_ip_parents.add(name)
        
        roots = self.find_root_records(all_records, children_map, record_map)
        
        # Remove domains that now have IP parents from the root list
        roots = [r for r in roots if r not in domains_with_ip_parents]
        
        # Add IPs/targets as new roots
        roots.extend(sorted(ip_parent_map.keys()))
        roots = sorted(set(roots))
        
        print(f"Found {len(roots)} root record(s)")
        print(f"Writing to {output_file}...")
        
        output_lines = ["# DNS Record Hierarchy", ""]
        
        for root in roots:
            # Check if this root is an IP/target with domains under it
            if root in ip_parent_map:
                # Write the IP/target as root
                output_lines.append(f"- {root}")
                # Write its domains as children
                for domain in sorted(ip_parent_map[root]):
                    self.write_hierarchy(domain, children_map, record_map, output_lines, level=1)
            else:
                self.write_hierarchy(root, children_map, record_map, output_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        
        print(f"✓ Mindmap generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a hierarchical mindmap of Cloudflare DNS records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cloudflare_dns_mapper.py your_api_token_here
  python cloudflare_dns_mapper.py your_api_token_here dns_map.md
  python cloudflare_dns_mapper.py your_api_token_here --notxt
  python cloudflare_dns_mapper.py your_api_token_here dns_map.md --notxt
        """
    )
    
    parser.add_argument("api_token", help="Cloudflare API token")
    parser.add_argument("output_file", nargs="?", default="dns_hierarchy.md",
                       help="Output markdown file (default: dns_hierarchy.md)")
    parser.add_argument("--notxt", action="store_true",
                       help="Exclude TXT records and verification records (_dmarc, _domainkey, etc.)")
    
    args = parser.parse_args()
    
    mapper = CloudflareDNSMapper(args.api_token)
    mapper.generate_mindmap(args.output_file, exclude_txt=args.notxt)


if __name__ == "__main__":
    main()
