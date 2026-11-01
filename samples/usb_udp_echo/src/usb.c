/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * USB device: CDC-NCM (or CDC-ECM with ecm.overlay), and CDC ACM when the
 * board puts the console on USB.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/usb/usbd.h>

#define ETH_CLASS COND_CODE_1(DT_HAS_COMPAT_STATUS_OKAY(zephyr_cdc_ecm_ethernet), \
			      ("cdc_ecm_0"), ("cdc_ncm_0"))

USBD_DEVICE_DEFINE(sample_usbd, DEVICE_DT_GET(DT_NODELABEL(zephyr_udc0)), 0x2fe3, 0x0005);

USBD_DESC_LANG_DEFINE(sample_lang);
USBD_DESC_MANUFACTURER_DEFINE(sample_mfr, "Zephyr Project");
USBD_DESC_PRODUCT_DEFINE(sample_product, "codeplace UDP echo");
USBD_DESC_SERIAL_NUMBER_DEFINE(sample_sn);

USBD_CONFIGURATION_DEFINE(sample_fs_config, 0, 125, NULL);
USBD_CONFIGURATION_DEFINE(sample_hs_config, 0, 125, NULL);

static int add_config(struct usbd_context *ctx, enum usbd_speed speed)
{
	struct usbd_config_node *cfg = (speed == USBD_SPEED_HS) ? &sample_hs_config : &sample_fs_config;
	int err;

	err = usbd_add_configuration(ctx, speed, cfg);
	if (err == 0 && DT_HAS_COMPAT_STATUS_OKAY(zephyr_cdc_acm_uart)) {
		err = usbd_register_class(ctx, "cdc_acm_0", speed, 1);
	}
	if (err == 0) {
		err = usbd_register_class(ctx, ETH_CLASS, speed, 1);
	}
	if (err == 0) {
		err = usbd_device_set_code_triple(ctx, speed, USB_BCC_MISCELLANEOUS, 0x02, 0x01);
	}

	return err;
}

int sample_usb_enable(void)
{
	int err;

	err = usbd_add_descriptor(&sample_usbd, &sample_lang);
	err = err ? err : usbd_add_descriptor(&sample_usbd, &sample_mfr);
	err = err ? err : usbd_add_descriptor(&sample_usbd, &sample_product);
	err = err ? err : usbd_add_descriptor(&sample_usbd, &sample_sn);

	if (err == 0 && USBD_SUPPORTS_HIGH_SPEED &&
	    usbd_caps_speed(&sample_usbd) == USBD_SPEED_HS) {
		err = add_config(&sample_usbd, USBD_SPEED_HS);
	}

	err = err ? err : add_config(&sample_usbd, USBD_SPEED_FS);
	err = err ? err : usbd_init(&sample_usbd);
	err = err ? err : usbd_enable(&sample_usbd);

	return err;
}
