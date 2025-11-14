#!/usr/bin/env python3
"""
Minimalny, względnie bezpieczny Pythonowy "instalator" (kopiuje live -> /mnt i instaluje systemd-boot).
Przemyśl każdą linię przed uruchomieniem.
Uruchom jako root.
"""

import os
import subprocess
import shutil
import sys
import traceback

def run(cmd, input=None):
    """Uruchom polecenie, pokaż stdout/stderr, przerwij przy błędzie."""
    print(f"+ {' '.join(cmd)}")
    try:
        # capture_output żeby mieć stdout/stderr w wyjątku (i wydrukować je)
        res = subprocess.run(cmd, check=True, text=True, input=input,
                             capture_output=True)
        if res.stdout:
            print(res.stdout.strip())
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
        return res
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: {' '.join(cmd)} zwróciło {e.returncode}")
        if e.stdout:
            print("stdout:\n", e.stdout)
        if e.stderr:
            print("stderr:\n", e.stderr, file=sys.stderr)
        raise

def backup_if_exists(path):
    if os.path.exists(path):
        bak = path + ".bak"
        print(f"backup {path} -> {bak}")
        os.replace(path, bak)

def is_root():
    return os.geteuid() == 0

def safe_mkdir(p):
    os.makedirs(p, exist_ok=True)

def safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print("Nie udało się usunąć", path, "->", e)

def copy_directory(src, dest):
    if not os.path.exists(src):
        print(f"Skip: {src} nie istnieje, nie kopiuję.")
        return
    safe_mkdir(dest)
    run(["cp", "-a", f"{src}/.", dest])

def copy_kernel_and_initramfs(src_boot="/boot", dest_boot="/mnt/boot"):
    print("== debug zawartości źródłowego /boot ==")
    try:
        run(["ls", "-l", src_boot])
    except Exception:
        print("Uwaga: ls /boot nie udało się (może brak uprawnień / brak katalogu).")

    if not os.path.exists(src_boot):
        raise FileNotFoundError(f"Źródłowy katalog {src_boot} nie istnieje.")

    safe_mkdir(dest_boot)

    candidates = [
        ("vmlinuz-linux", "initramfs-linux.img"),
        ("vmlinuz-linux-lts", "initramfs-linux-lts.img"),
        ("vmlinuz", "initramfs.img"),
        ("vmlinuz-arch", "initramfs-arch.img"),
    ]

    for vmlinuz, initrd in candidates:
        sv = os.path.join(src_boot, vmlinuz)
        si = os.path.join(src_boot, initrd)
        if os.path.exists(sv) and os.path.exists(si):
            try:
                print(f"Kopiuję {sv} -> {dest_boot}/{vmlinuz}")
                shutil.copy2(sv, os.path.join(dest_boot, vmlinuz))
                print(f"Kopiuję {si} -> {dest_boot}/{initrd}")
                shutil.copy2(si, os.path.join(dest_boot, initrd))
                return (vmlinuz, initrd)
            except PermissionError as e:
                raise PermissionError(f"Brak praw do zapisu w {dest_boot}: {e}")
            except Exception as e:
                print("shutil.copy2 nie zadziałał:", e)
                # spróbujemy fallback

    # fallback: skopiuj wszystko z /boot (cp -a)
    boot_files = os.listdir(src_boot)
    print("Nie znaleziono typowych par kernela. /boot zawiera:", boot_files)
    try:
        run(["cp", "-a", f"{src_boot}/.", dest_boot])
        return (None, None)
    except Exception as e:
        print("Fallback cp -a nie powiódł się:", e)
        raise RuntimeError("Nie udało się skopiować plików z /boot.")

def unmount_lazy(paths):
    for p in paths:
        try:
            if os.path.ismount(p) or os.path.exists(p):
                print(f"umount -l {p}")
                subprocess.run(["umount", "-l", p], check=False)
        except Exception as e:
            print("ignore unmount error:", p, e)

def main():
    if not is_root():
        print("Uruchom jako root (sudo).")
        sys.exit(2)

    try:
        boot_partition = input("boot partition (np /dev/sda1): ").strip()
        root_partition = input("root partition (np /dev/sda2): ").strip()
        swap_partition = input("swap partition (ENTER żeby pominąć): ").strip()

        root_password = input("root password: ").strip()
        user = input("user: ").strip()
        user_password = input("user password: ").strip()

        if not boot_partition or not root_partition:
            print("Musisz podać partycje boot i root.")
            sys.exit(1)
        if boot_partition == root_partition:
            print("boot i root nie mogą być tą samą partycją.")
            sys.exit(1)

        # sprawdź czy urządzenia istnieją
        if not os.path.exists(boot_partition):
            print(f"Urządzenie {boot_partition} nie istnieje (sprawdź ścieżkę).")
            sys.exit(1)
        if not os.path.exists(root_partition):
            print(f"Urządzenie {root_partition} nie istnieje (sprawdź ścieżkę).")
            sys.exit(1)

        MNT = "/mnt"
        BOOT_MNT = "/mnt/boot"
        safe_mkdir(MNT)
        safe_mkdir(BOOT_MNT)

        # formatowanie
        print("Formatuję boot -> FAT32 (etykieta BOOT)")
        run(["mkfs.fat", "-F", "32", "-n", "BOOT", boot_partition])

        print("Formatuję root -> ext4 (etykieta ROOT)")
        run(["mkfs.ext4", "-F", "-L", "ROOT", root_partition])

        if swap_partition:
            if not os.path.exists(swap_partition):
                print(f"Swap {swap_partition} nie istnieje, pomijam.")
            else:
                print("Ustawiam swap")
                run(["mkswap", swap_partition])
                run(["swapon", swap_partition])

        # montowanie root i boot
        print("Mountuję root i boot")
        run(["mount", root_partition, MNT])
        run(["mount", boot_partition, BOOT_MNT])

        # kopiowanie katalogów (tylko istniejące)
        dirs = ["/usr","/lib","/lib64","/bin","/sbin","/etc","/var","/opt","/root","/home"]
        for d in dirs:
            copy_directory(d, os.path.join(MNT, d.lstrip("/")))

        # minimalne etc — backup jeśli istnieje
        safe_mkdir(os.path.join(MNT, "etc"))
        backup_if_exists(os.path.join(MNT, "etc", "passwd"))
        backup_if_exists(os.path.join(MNT, "etc", "group"))
        backup_if_exists(os.path.join(MNT, "etc", "shadow"))

        with open(os.path.join(MNT, "etc", "passwd"), "w") as f:
            f.write("root:x:0:0:root:/root:/bin/bash\n")

        with open(os.path.join(MNT, "etc", "group"), "w") as f:
            f.write("root:x:0:root\n")
            f.write("wheel:x:10:root\n")

        with open(os.path.join(MNT, "etc", "shadow"), "w") as f:
            f.write("root:!:0:0:99999:7:::\n")
        os.chmod(os.path.join(MNT, "etc", "shadow"), 0o600)

        # fstab (upewnij się, że boot jest zamontowane przed genfstab)
        print("Generuję /etc/fstab")
        with open(os.path.join(MNT, "etc", "fstab"), "w") as f:
            subprocess.run(["genfstab", "-U", MNT], stdout=f, check=True, text=True)

        # mount pseudo-fs do chroot
        print("Mountuję pseudo-filesystems (proc/sys/dev/run) do chroot")
        safe_mkdir(os.path.join(MNT, "proc"))
        safe_mkdir(os.path.join(MNT, "sys"))
        safe_mkdir(os.path.join(MNT, "dev"))
        safe_mkdir(os.path.join(MNT, "run"))
        run(["mount", "-t", "proc", "/proc", os.path.join(MNT, "proc")])
        run(["mount", "--rbind", "/sys", os.path.join(MNT, "sys")])
        run(["mount", "--rbind", "/dev", os.path.join(MNT, "dev")])
        run(["mount", "--rbind", "/run", os.path.join(MNT, "run")])

        # kernel/initramfs
        print("Kopiowanie kernela i initramfs")
        vmlinuz, initrd = copy_kernel_and_initramfs("/boot", "/mnt/boot")

        # ustawienia systemowe (hostname / locale / vconsole)
        hostname = "Leaf"
        timezone = "Europe/Warsaw"
        locale = "en_US.UTF-8"

        with open(os.path.join(MNT, "etc", "hostname"), "w") as f:
            f.write(hostname + "\n")

        # Poprawne wpisy do locale.gen (dokładny format)
        with open(os.path.join(MNT, "etc", "locale.gen"), "w") as f:
            f.write(f"{locale} UTF-8\n")

        with open(os.path.join(MNT, "etc", "locale.conf"), "w") as f:
            f.write(f"LANG={locale}\n")

        with open(os.path.join(MNT, "etc", "vconsole.conf"), "w") as f:
            f.write("KEYMAP=us\n")

        # ustaw timezone w chroot (link)
        run(["arch-chroot", MNT, "ln", "-sf", f"/usr/share/zoneinfo/{timezone}", "/etc/localtime"])
        run(["arch-chroot", MNT, "locale-gen"])
        run(["arch-chroot", MNT, "hwclock", "--systohc"])

        # ustawienie haseł i użytkownika (bez interactive)
        print("Ustawiam hasło root (chpasswd w chroot)")
        run(["arch-chroot", MNT, "chpasswd"], input=f"root:{root_password}\n")

        print("Tworzę użytkownika i ustawiam hasło")
        run(["arch-chroot", MNT, "useradd", "-m", "-G", "wheel", "-s", "/bin/bash", user])
        run(["arch-chroot", MNT, "chpasswd"], input=f"{user}:{user_password}\n")

        # sudoers: pozwól wheel
        sudoers_d = os.path.join(MNT, "etc", "sudoers.d")
        safe_mkdir(sudoers_d)
        wheel_path = os.path.join(sudoers_d, "wheel")
        with open(wheel_path, "w") as f:
            f.write("%wheel ALL=(ALL) ALL\n")
        os.chmod(wheel_path, 0o440)

        # ensure /etc/skel is present inside target; jeśli nie - utwórz minimalne
        skel = os.path.join(MNT, "etc", "skel")
        if not os.path.exists(skel):
            print("Brak /etc/skel w obrazie -- tworzę minimalne /etc/skel")
            safe_mkdir(skel)
            with open(os.path.join(skel, ".profile"), "w") as f:
                f.write("# minimal profile\n")
        # skopiuj skel do home (useradd zwykle to zrobił, ale dla pewności)
        run(["arch-chroot", MNT, "cp", "-a", "/etc/skel/.", f"/home/{user}"])
        run(["arch-chroot", MNT, "chown", "-R", f"{user}:{user}", f"/home/{user}"])
        run(["arch-chroot", MNT, "chmod", "755", f"/home/{user}"])

        # instalacja systemd-boot (zakładamy UEFI + FAT32 boot)
        print("Instaluję systemd-boot (bootctl)")
        run(["arch-chroot", MNT, "bootctl", "install"])

        # tworzenie loader entry — użyj nazwy plików wykrytych wcześniej jeśli możliwe
        safe_mkdir(os.path.join(MNT, "boot", "loader", "entries"))
        if vmlinuz and initrd:
            vmlinuz_path = "/" + vmlinuz
            initrd_path = "/" + initrd
        else:
            # heurystyka: znajdź najbliższe pliki w /mnt/boot
            files = os.listdir(os.path.join(MNT, "boot"))
            vmlinuz_candidates = [f for f in files if f.startswith("vmlinuz")]
            initrd_candidates = [f for f in files if f.startswith("initramfs") or f.startswith("initrd")]
            vmlinuz_path = "/" + vmlinuz_candidates[0] if vmlinuz_candidates else "/vmlinuz-linux"
            initrd_path = "/" + initrd_candidates[0] if initrd_candidates else "/initramfs-linux.img"

        loader_entry = f"""title   Arch Linux
linux   {vmlinuz_path}
initrd  {initrd_path}
options root=LABEL=ROOT rw
"""
        with open(os.path.join(MNT, "boot", "loader", "entries", "arch.conf"), "w") as f:
            f.write(loader_entry)

        print("\n=> Instalacja zakończona pomyślnie (najprawdopodobniej).")
        print("Sprawdź /mnt/boot, /mnt/etc/fstab i wpis w /mnt/boot/loader/entries/arch.conf")
        print("Aby dokończyć: umount -R /mnt && reboot (albo wykonaj ręcznie testy przed restartem).")

    except Exception:
        print("\nPojawił się błąd — wypisuję trace i próbuję posprzątać (lazy umount).")
        traceback.print_exc()
        try:
            unmount_lazy([os.path.join(MNT, "proc"), os.path.join(MNT, "sys"),
                          os.path.join(MNT, "dev"), os.path.join(MNT, "run")])
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
