#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/in.h>

/*
 * SENTINEL XDP Fast-Drop Program
 * Drops packets from blacklisted IPv4 addresses at the NIC level.
 */

// Map to store blacklisted IPv4 addresses
// Key: u32 (IP address), Value: u64 (packet count)
BPF_HASH(blacklist, u32, u64);

int xdp_drop_func(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    u32 src_ip = ip->saddr;
    u64 *value = blacklist.lookup(&src_ip);

    if (value) {
        // Increment dropped packet count for this IP
        lock_xadd(value, 1);
        return XDP_DROP;
    }

    return XDP_PASS;
}
