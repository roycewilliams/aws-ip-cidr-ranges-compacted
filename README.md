Pulls AWS IP ranges, and provides a CIDR-summarized list. Runs daily.

This usually cuts the CIDR range count down to less than half of its published size.

NOTE: this is *not* a drop-in replacement for the existing format. The resulting format is significantly simpler, because merging CIDR blocks is destructive to the other fields (region, service, network_border_group).
