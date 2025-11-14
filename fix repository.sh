#/bin/bash
cat airootfs/usr/share/boot/kernel_part_* > airootfs/usr/share/boot/initramfs-linux.img
rm -f airootfs/usr/share/boot/kernel_part_*
cat local/repo/lightix-repository-local/zen_browser_part_* > local/repo/lightix-repository-local/zen-browser-bin-1.15.5b-1-x86_64.pkg.tar.zst
rm -f local/repo/lightix-repository-local/zen_browser_part_*
