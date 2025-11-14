#/bin/bash
split -b 50M airootfs/usr/share/boot/initramfs-linux.img airootfs/usr/share/boot/kernel_part_
rm -f airootfs/usr/share/boot/initramfs-linux.img
split -b 50M local/repo/lightix-repository-local/zen-browser-* local/repo/lightix-repository-local/zen_browser_part_
rm -f local/repo/lightix-repository-local/zen-browser-bin*
