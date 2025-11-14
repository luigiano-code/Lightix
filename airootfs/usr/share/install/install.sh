#!/bin/bash

set -euo pipefail

DISK="/dev/vda"
MNT="/mnt"

# wyczyść tablicę partycji
parted --script "$DISK" mklabel gpt

# 1. partycja – 2GB na boot
parted --script "$DISK" mkpart primary fat32 1MiB 2049MiB
parted --script "$DISK" set 1 esp on

# 2. partycja – reszta na root
parted --script "$DISK" mkpart primary ext4 2049MiB 100%

# formatuj
mkfs.fat -F32 "${DISK}1"
mkfs.ext4 -F "${DISK}2"

# montowanie
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

genfstab /mnt -u >> /mnt/etc/fstab

cp -rf /usr/share/boot/ /mnt/boot

arch-chroot "$MNT" /bin/bash <<'EOF'
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=MYOS
mkinitcpio -P
grub-mkconfig -o /boot/grub/grub.cfg
EOF

echo "READY"
