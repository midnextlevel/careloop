# Encrypted backups

Back up the PostgreSQL database **and** deployment settings. The database contains entries, photos, history, memberships and browser-configured OAuth credentials; `.env` contains application/database secrets and may contain environment-configured Google credentials.

`tools/backups.py` creates a compressed PostgreSQL dump, restores it into a uniquely named temporary database, checks migrations, and removes that verification database. It packages the dump with `.env`, Compose files and a source-revision manifest, then encrypts everything using [age](https://github.com/FiloSottile/age). Plaintext temporary files are private and removed when the command finishes. An interrupted process or host crash may require cleanup of its private temporary directory or verification database.

## Keep the recovery key off the VM

Install age on your own computer. Generate the key **there**, and keep a second protected copy in your password manager or another secure location:

```sh
age-keygen -o recovery-key.txt
age-keygen -y recovery-key.txt
```

Only copy the resulting public `age1...` recipient to the VM. The private recovery key is required for decryption; it grants no SSH access. Keep it out of Git and separate from the backup destination. Windows file ACLs should restrict the key to its owner.

Install the encryption utility on an Ubuntu VM with `sudo apt-get install age`. The backup helper uses Docker Compose from the project checkout and should be run by its administrator.

## Back up to a NAS or mounted remote share

Mount your chosen off-VM destination first, using credentials managed privately by your operating system. Use a dedicated Careloop directory. Replace these example paths and the public recipient:

```sh
sudo python3 tools/backups.py \
  --mount /mnt/backup-share \
  --destination /mnt/backup-share/careloop \
  --recipient age1YOUR_PUBLIC_RECIPIENT \
  --keep-days 30
```

`--mount` must be an existing mount point and the destination must be inside it. If the mount is missing, the command fails rather than writing to a directory on the VM. This guard cannot determine where a disk is physically located: select a genuine remote/off-VM mount yourself. Backups are encrypted before being written to that destination. Final names are published atomically with a SHA-256 sidecar; incomplete files are not treated as successful backups. Retention only removes correctly named old Careloop archives/checksums after a new verified backup succeeds.

Add `--install-timer` to run a successful initial backup and install daily systemd scheduling at approximately 02:00 in the VM's local timezone. Automatic scheduling requires `--mount`:

```sh
sudo python3 tools/backups.py --mount /mnt/backup-share \
  --destination /mnt/backup-share/careloop --recipient age1YOUR_PUBLIC_RECIPIENT \
  --keep-days 30 --install-timer
systemctl list-timers careloop-backup.timer
sudo journalctl -u careloop-backup.service
```

Persistent timers catch up after downtime. Check for failed jobs and available storage; a timer alone is not a backup-failure notification system. These VM units must be installed again after rebuilding the VM. No remote share is mounted automatically and no credentials are saved by the helper.

## Pull a one-time backup to another computer

The administrator can stream encrypted bytes directly over their own SSH connection. The VM only needs the public recipient. Use a binary-safe stdout redirection, such as a POSIX shell or Python `subprocess` writing to an opened binary file:

```sh
ssh YOUR_VM 'sudo python3 /path/to/careloop/tools/backups.py --stream --recipient age1YOUR_PUBLIC_RECIPIENT' > recovery.tar.gz.age
```

Progress messages use stderr; stdout contains only encrypted bytes. The VM stores only private, temporary plaintext working files during creation; the encrypted recovery archive is written on the receiving computer. This mode does not require a destination mount and does not install a timer or retain SSH credentials.

## Verify and recover

Verify the checksum sidecar, then decrypt on a protected computer:

```sh
age --decrypt -i recovery-key.txt -o recovery.tar.gz recovery.tar.gz.age
tar -tzf recovery.tar.gz
```

The archive contains `journal.dump`, `.env`, `compose.yaml`, optional `compose.override.yaml` and `manifest.json`. Decrypted files contain private records and credentials: extract only into a protected directory and remove working copies after verification.

Follow the [database restore procedure](deployment.md#backup-and-recovery), using the archived source revision/configuration and dump. Preserve the existing database before an actual recovery, clear restored sessions, review memberships, and verify Google sign-in and entry/photo visibility before reopening access. A restore recovers the existing journal and owner; it is **not** a fresh-install wizard test. For that test, use a separate empty installation and keep the backup safely off the VM.
