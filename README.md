Pulls Amazon's published JSON list of AWS IP ranges once a day, and converts them to a CIDR-summarized list.

This usually cuts the CIDR range count down to less than half of the upstream size.

Simple example:

```
$ grep '"3.4.8' *json
ip-ranges-compacted.json:      "ip_prefix": "3.4.8.0/23",
ip-ranges-merged.json:      "ip_prefix": "3.4.8.0/24",
ip-ranges-original.json:      "ip_prefix": "3.4.8.0/24",
ip-ranges-original.json:      "ip_prefix": "3.4.8.0/24",
```

NOTE: this is *not* a drop-in replacement for the existing data, _if you depend on other field values_. Merging CIDR blocks is destructive to the other fields (region, service, network_border_group).

The generated files use two different merge strategies:

* -merged: metadata is preserved when it matches; otherwise "other"
* -compacted: **all** other metadata is ignored and replaced with "other"
