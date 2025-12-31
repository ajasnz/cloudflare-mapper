# Cloudflare DNS Mapper

A Python script that generates a hierarchical mindmap of DNS records from Cloudflare, showing the relationships between records based on what they point to.

## Features

- Fetches all zones accessible with your Cloudflare API token
- Retrieves all DNS records from each zone
- Builds a hierarchy based on record relationships (CNAME, ALIAS, MX, SRV)
- Outputs a structured markdown file suitable for mindmap visualization
- Zero external dependencies (uses only Python standard library)

## Requirements

- Python 3.6 or higher
- Cloudflare API token with DNS read permissions

## Usage

```bash
python cloudflare_dns_mapper.py <API_TOKEN> [output_file.md]
```

### Example

```bash
python cloudflare_dns_mapper.py your_cloudflare_api_token_here dns_map.md
```

If no output file is specified, it defaults to `dns_hierarchy.md`.

## How It Works

1. **Fetches Zones**: Retrieves all zones your API token has access to
2. **Fetches DNS Records**: Gets all DNS records from each zone
3. **Builds Hierarchy**: Analyzes record values to determine parent-child relationships:
   - CNAME records become children of the domain they point to
   - A/AAAA records are typically root nodes (unless pointed to by CNAMEs)
   - MX and SRV records become children of their target domains
4. **Generates Output**: Creates a markdown file with indented lists showing the hierarchy

## Output Format

The script generates a markdown file with properly formatted hierarchical lists:

```
- root-domain.com
  - subdomain.root-domain.com
    - service.root-domain.com
      - api.service.root-domain.com
```

Each level of indentation (2 spaces) represents a dependency relationship where child records point to their parent.

## Getting a Cloudflare API Token

1. Log in to your Cloudflare account
2. Go to **My Profile** → **API Tokens**
3. Click **Create Token**
4. Use the **Read all resources** template or create a custom token with:
   - Zone → DNS → Read permissions
   - Zone → Zone → Read permissions
5. Copy the generated token

## License

MIT License - Feel free to use and modify as needed.
