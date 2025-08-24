Pulls Amazon's published JSON list of AWS IP ranges once a day, and converts them to a CIDR-summarized list.

Simple example:

This usually cuts the CIDR range count down to less than half of the upstream size.

```
$ grep '"3.4.8' *json
ip-ranges-compacted.json:      "ip_prefix": "3.4.8.0/23",
ip-ranges-original.json:      "ip_prefix": "3.4.8.0/24",
ip-ranges-original.json:      "ip_prefix": "3.4.8.0/24",
```

NOTE: this is *not* a drop-in replacement for the existing data, _if you depend on other field values_. Merging CIDR blocks is destructive to the other fields (region, service, network_border_group). These fields are represented as "other" in the compacted version.
