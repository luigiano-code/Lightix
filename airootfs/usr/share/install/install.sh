#!/bin/bash

set -euo pipefail

DISK="/dev/vda"
MNT="/mnt"

parted --script "$DISK" mklabel gpt

parted --script "$DISK" mkpart primary fat32 1MiB 2049MiB
parted --script "$DISK" set 1 esp on

parted --script "$DISK" mkpart primary ext4 2049MiB 100%

mkfs.fat -F32 "${DISK}1"
mkfs.ext4 -F "${DISK}2"

mount "${DISK}2" "$MNT"
mkdir -p "$MNT"/boot
mount "${DISK}1" "$MNT"/boot

rsync -aAXHv \
  --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found"} \
  / "$MNT"

mount --bind /dev "$MNT/dev"
mount --bind /proc "$MNT/proc"
mount --bind /sys "$MNT/sys"
mount --bind /run "$MNT/run"

genfstab /mnt -U > /mnt/etc/fstab

arch-chroot "$MNT" /bin/bash <<'EOF'
mv /etc/mkinitcpio.d/linux.preset /etc/mkinitcpio.d/linux.preset.bak
mv /etc/mkinitcpio.d/installedlinux.preset /etc/mkinitcpio.d/linux.preset
cp /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/mkinitcpio.conf
rm -f /etc/mkinitcpio.conf.d/archiso.conf
pacman -Sy linux linux-headers --noconfirm
mkinitcpio -c /etc/mkinitcpio.conf -g /boot/initramfs-linux.img
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=YAVIX
grub-mkconfig -o /boot/grub/grub.cfg
EOF

echo "READY"
