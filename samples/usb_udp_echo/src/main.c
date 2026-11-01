/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * UDP echo over USB CDC-NCM (or CDC-ECM with ecm.overlay): the benchmark workload of
 * zephyr-codeplace. The board has the address 192.0.2.1/24 and echoes every UDP datagram
 * that arrives on port 4242. The placement of the code is chosen at build time (README.md).
 */

#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/socket.h>

#define UDP_PORT 4242

int sample_usb_enable(void);

static uint8_t buf[1500];

int main(void)
{
	struct net_sockaddr_in addr = {
		.sin_family = NET_AF_INET,
		.sin_port = net_htons(UDP_PORT),
	};
	struct net_if *iface = net_if_lookup_by_dev(DEVICE_DT_GET(DT_NODELABEL(usb_eth0)));
	struct net_in_addr ip, mask;
	int sock, err;

	net_addr_pton(NET_AF_INET, "192.0.2.1", &ip);
	net_addr_pton(NET_AF_INET, "255.255.255.0", &mask);
	net_if_ipv4_addr_add(iface, &ip, NET_ADDR_MANUAL, 0);
	net_if_ipv4_set_netmask_by_addr(iface, &ip, &mask);

	err = sample_usb_enable();
	if (err != 0) {
		printk("usb enable failed: %d\n", err);
		return 0;
	}

	sock = zsock_socket(NET_AF_INET, NET_SOCK_DGRAM, NET_IPPROTO_UDP);
	if (sock < 0 || zsock_bind(sock, (struct net_sockaddr *)&addr, sizeof(addr)) != 0) {
		printk("socket setup failed\n");
		return 0;
	}
	printk("UDP echo on 192.0.2.1:%d\n", UDP_PORT);

	for (;;) {
		struct net_sockaddr_in from;
		net_socklen_t fromlen = sizeof(from);
		ssize_t n = zsock_recvfrom(sock, buf, sizeof(buf), 0, (struct net_sockaddr *)&from, &fromlen);

		if (n > 0) {
			(void)zsock_sendto(sock, buf, n, 0, (struct net_sockaddr *)&from, fromlen);
		}
	}

	return 0;
}
