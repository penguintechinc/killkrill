#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <linux/tcp.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define MAX_CIDR_RULES 1024
#define MAX_PORT_RULES 64

// CIDR rule structure
struct cidr_rule {
    __u32 network;      // Network address in network byte order
    __u32 mask;         // Subnet mask
    __u16 port;         // Port number (0 = any port)
    __u8 enabled;       // Rule enabled flag
    __u8 reserved;      // Padding
};

// XDP statistics structure
struct xdp_stats {
    __u64 packets_total;
    __u64 packets_allowed;
    __u64 packets_blocked;
    __u64 bytes_total;
    __u64 bytes_allowed;
    __u64 bytes_blocked;
    __u64 tcp_packets;
    __u64 udp_packets;
    __u64 syslog_packets;
    __u64 api_packets;
};

// BPF maps for CIDR rules and statistics
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, MAX_CIDR_RULES);
    __type(key, __u32);
    __type(value, struct cidr_rule);
} cidr_rules SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, MAX_PORT_RULES);
    __type(key, __u32);
    __type(value, __u16);
} allowed_ports SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct xdp_stats);
} xdp_statistics SEC(".maps");

// Helper function to check if IP matches CIDR rule
static __always_inline int check_cidr_match(__u32 ip, struct cidr_rule *rule) {
    if (!rule->enabled) {
        return 0;
    }

    // Apply subnet mask to both IP and network
    __u32 masked_ip = ip & rule->mask;
    __u32 masked_network = rule->network & rule->mask;

    return masked_ip == masked_network;
}

// Helper function to check if port is allowed
static __always_inline int check_port_allowed(__u16 port) {
    for (__u32 i = 0; i < MAX_PORT_RULES; i++) {
        __u16 *allowed_port = bpf_map_lookup_elem(&allowed_ports, &i);
        if (!allowed_port || *allowed_port == 0) {
            break;
        }
        if (*allowed_port == port) {
            return 1;
        }
    }
    return 0;
}

// Helper function to update statistics
static __always_inline void update_stats(__u64 packet_size, int allowed, int is_tcp, int is_udp, int is_syslog, int is_api) {
    __u32 key = 0;
    struct xdp_stats *stats = bpf_map_lookup_elem(&xdp_statistics, &key);
    if (!stats) {
        return;
    }

    __sync_fetch_and_add(&stats->packets_total, 1);
    __sync_fetch_and_add(&stats->bytes_total, packet_size);

    if (allowed) {
        __sync_fetch_and_add(&stats->packets_allowed, 1);
        __sync_fetch_and_add(&stats->bytes_allowed, packet_size);
    } else {
        __sync_fetch_and_add(&stats->packets_blocked, 1);
        __sync_fetch_and_add(&stats->bytes_blocked, packet_size);
    }

    if (is_tcp) {
        __sync_fetch_and_add(&stats->tcp_packets, 1);
        if (is_api) {
            __sync_fetch_and_add(&stats->api_packets, 1);
        }
    } else if (is_udp) {
        __sync_fetch_and_add(&stats->udp_packets, 1);
        if (is_syslog) {
            __sync_fetch_and_add(&stats->syslog_packets, 1);
        }
    }
}

SEC("xdp")
int xdp_filter_func(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // Parse Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) {
        return XDP_PASS;
    }

    // Only process IPv4 packets
    if (eth->h_proto != bpf_htons(ETH_P_IP)) {
        return XDP_PASS;
    }

    // Parse IP header
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) {
        return XDP_PASS;
    }

    // Verify IP header length
    if (ip->ihl < 5) {
        return XDP_DROP;
    }

    __u32 src_ip = ip->saddr;
    __u16 dest_port = 0;
    int is_tcp = 0, is_udp = 0, is_syslog = 0, is_api = 0;
    __u64 packet_size = data_end - data;

    // Parse transport layer
    if (ip->protocol == IPPROTO_TCP) {
        struct tcphdr *tcp = (void *)ip + (ip->ihl * 4);
        if ((void *)(tcp + 1) > data_end) {
            return XDP_DROP;
        }
        dest_port = bpf_ntohs(tcp->dest);
        is_tcp = 1;

        // Check if this is an API request (HTTP/HTTPS/HTTP3)
        if (dest_port == 80 || dest_port == 443 || dest_port == 8081 || dest_port == 8082) {
            is_api = 1;
        }
    } else if (ip->protocol == IPPROTO_UDP) {
        struct udphdr *udp = (void *)ip + (ip->ihl * 4);
        if ((void *)(udp + 1) > data_end) {
            return XDP_DROP;
        }
        dest_port = bpf_ntohs(udp->dest);
        is_udp = 1;

        // Check if this is a syslog packet (port range 10000-11000)
        if (dest_port >= 10000 && dest_port <= 11000) {
            is_syslog = 1;
        }
    } else {
        // Not TCP or UDP, pass through
        return XDP_PASS;
    }

    // Check if port is allowed
    if (!check_port_allowed(dest_port)) {
        update_stats(packet_size, 0, is_tcp, is_udp, is_syslog, is_api);
        return XDP_DROP;
    }

    // Check CIDR rules
    int ip_allowed = 0;
    for (__u32 i = 0; i < MAX_CIDR_RULES; i++) {
        struct cidr_rule *rule = bpf_map_lookup_elem(&cidr_rules, &i);
        if (!rule || !rule->enabled) {
            continue;
        }

        // If rule has a specific port, check if it matches
        if (rule->port != 0 && rule->port != dest_port) {
            continue;
        }

        if (check_cidr_match(src_ip, rule)) {
            ip_allowed = 1;
            break;
        }
    }

    update_stats(packet_size, ip_allowed, is_tcp, is_udp, is_syslog, is_api);

    if (ip_allowed) {
        return XDP_PASS;
    } else {
        return XDP_DROP;
    }
}

char _license[] SEC("license") = "GPL";