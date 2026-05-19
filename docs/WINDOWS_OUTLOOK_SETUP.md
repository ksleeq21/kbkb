# Windows Outlook Setup

This guide covers Outlook folder selection, first manual import, and Task Scheduler registration.

## Prerequisites

- Use classic Microsoft Outlook desktop, not New Outlook.
- Install Windows optional dependencies:

```powershell
python -m pip install -e ".[windows]"
```

- Keep the Obsidian vault outside the source repository.
- Create a dedicated Outlook folder such as `_KB` and move only selected emails into that folder.

## Create Config

Generate a local config outside the repository:

```powershell
python -m kb_win_sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
notepad "$env:USERPROFILE\kb-win-sync\config.yaml"
```

The generated file is a template. Edit `vault_path`, `outlook.folders`, and optional `sync`.

## Select Outlook Folders

Use the Outlook folder tree from left to right:

1. Open classic Outlook desktop.
2. Find the top-level mailbox name in the left folder tree.
3. Find or create an import-only folder, for example `_KB\ProjectA`.
4. Build `outlook_path` from mailbox root to target folder.

Example:

```yaml
outlook_path: "\\Mailbox - Kangsan Lee\\Inbox\\_KB\\ProjectA"
```

Shared mailbox example:

```yaml
outlook_path: "\\Shared Mailbox Name\\Inbox\\Reports"
```

Recommended pattern:

```yaml
outlook:
  folders:
    - name: "project-a"
      outlook_path: "\\Mailbox - Kangsan Lee\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/ProjectA"
      tags:
        - "email"
        - "project/project-a"
      save_msg: true
      save_attachments: true
```

Do not point import at the entire Inbox unless that is intentional. The safer workflow is to move selected messages into `_KB` folders.

## Validate and Preview

Run these before the first import:

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

Expected dry-run behavior:

- It scans only configured folders.
- It prints messages that would be imported.
- It does not write Markdown, state, `.msg`, or attachment files.

## Run Manual Import

After dry-run looks correct:

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Check:

- Markdown files appear under the configured `vault_path`.
- Re-running import skips duplicate messages.
- No unexpected Outlook folders are scanned.

## Register Task Scheduler

Register the schedule only after manual import works.

### GUI Steps

1. Open Task Scheduler.
2. Select "Create Task", not "Create Basic Task".
3. General tab:
   - Name: `kb-win-sync`
   - Select "Run only when user is logged on" if Outlook COM cannot run in a background session.
4. Triggers tab:
   - New trigger
   - Begin the task: On a schedule
   - Daily
   - Choose a time when Outlook is normally available.
5. Actions tab:
   - New action
   - Action: Start a program
   - Program/script: path to `examples\run-kb-win-sync.bat` or your local wrapper `.bat`
   - Start in: repository directory or installed package working directory
6. Conditions tab:
   - Avoid settings that prevent the task from running on battery if that matters.
7. Settings tab:
   - Allow task to be run on demand.
   - Stop the task if it runs longer than a reasonable import window.
8. Run the task manually once and inspect Task Scheduler history and `log_path`.

### schtasks Example

Adjust paths first:

```powershell
schtasks /Create /TN "kb-win-sync" /SC DAILY /ST 09:00 /TR "%USERPROFILE%\kb-win-sync\run-kb-win-sync.bat"
```

Delete later:

```powershell
schtasks /Delete /TN "kb-win-sync"
```

## Troubleshooting

- Folder not found: rebuild `outlook_path` from the Outlook folder tree.
- Outlook unavailable: use classic Outlook and run while logged in.
- Too many messages in dry-run: narrow `outlook.folders` to `_KB` subfolders.
- Duplicate messages skipped: expected after successful import; use `--force` only intentionally.
- SFTP failure: keep `sync.enabled: false` until SSH preflight succeeds.
