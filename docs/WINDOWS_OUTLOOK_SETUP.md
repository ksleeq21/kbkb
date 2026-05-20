# Windows Outlook 설정

이 guide는 Outlook folder 선택, 첫 수동 import, Task Scheduler 등록을 다룬다.

## 사전 요구사항

- New Outlook이 아니라 classic Microsoft Outlook desktop을 사용한다.
- Windows optional dependency를 설치한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
```

- Obsidian vault는 source repository 밖에 둔다.
- `_KB` 같은 전용 Outlook folder를 만들고 선택한 email만 그 folder로 옮긴다.

## Config 생성

repository 밖에 local config를 생성한다.

```powershell
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync list-mailboxes
notepad "$env:USERPROFILE\kb-win-sync\config.yaml"
```

생성된 file은 template이다. `vault_path`, `outlook.folders`, 선택적 `sync`를 수정한다.

## Mailbox 대화형 목록

`outlook.folders`를 손으로 수정하기 전에 mailbox picker를 사용한다.

```powershell
kb-win-sync list-mailboxes
```

이 command는 COM automation으로 classic Outlook을 열고 mailbox와 folder를 numeric index와 함께 출력한 뒤 다음을 묻는다.

```text
동기화 시키고 싶은 메일함 Index(예: 1,2,3,5):
```

쉼표로 구분한 index를 하나 이상 입력한다. command는 `outlook.folders` 아래에 복사할 수 있는 YAML snippet을 출력한다.

Example output shape:

```yaml
    - name: "projecta"
      outlook_path: "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/projecta"
      tags:
        - "email"
        - "mailbox/projecta"
      save_msg: true
      save_attachments: true
```

Import를 실행하기 전에 생성된 `name`, `target_folder`, `tags`를 검토한다.

## Outlook Folder 선택

Outlook folder tree를 왼쪽에서 오른쪽 순서로 확인한다.

1. Classic Outlook desktop을 연다.
2. 왼쪽 folder tree에서 top-level mailbox name을 찾는다.
3. `_KB\ProjectA` 같은 import-only folder를 찾거나 만든다.
4. mailbox root부터 target folder까지 `outlook_path`를 만든다.

Example:

```yaml
outlook_path: "\\Mailbox - Kangsan Lee\\Inbox\\_KB\\ProjectA"
```

Shared mailbox example:

```yaml
outlook_path: "\\Shared Mailbox Name\\Inbox\\Reports"
```

권장 pattern:

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

의도한 경우가 아니라면 전체 Inbox를 import 대상으로 지정하지 않는다. 더 안전한 workflow는 선택한 message를 `_KB` folder로 옮기는 것이다.

## 검증 및 Preview

첫 import 전에 다음을 실행한다.

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

예상 dry-run 동작:

- 설정된 folder만 scan한다.
- import될 message를 출력한다.
- Markdown, state, `.msg`, 첨부파일을 쓰지 않는다.

## 수동 Import 실행

dry-run 결과가 올바르면 다음을 실행한다.

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

확인할 내용:

- Markdown file이 설정된 `vault_path` 아래에 나타난다.
- import를 다시 실행하면 duplicate message가 skip된다.
- 예상하지 않은 Outlook folder가 scan되지 않는다.

## Task Scheduler 등록

수동 import가 동작한 뒤에만 schedule을 등록한다.

### GUI 단계

1. Task Scheduler를 연다.
2. "Create Basic Task"가 아니라 "Create Task"를 선택한다.
3. General tab:
   - Name: `kb-win-sync`
   - Outlook COM이 background session에서 실행되지 않으면 "Run only when user is logged on"을 선택한다.
4. Triggers tab:
   - New trigger
   - Begin the task: On a schedule 선택
   - Daily
   - Outlook을 정상적으로 사용할 수 있는 시간을 선택한다.
5. Actions tab:
   - New action
   - Action: Start a program
   - Program/script: `examples\run-kb-win-sync.bat` 또는 local wrapper `.bat`의 path
   - Start in: repository directory 또는 installed package working directory
6. Conditions tab:
   - 필요한 경우 battery 상태 때문에 task 실행을 막는 설정은 피한다.
7. Settings tab:
   - task를 on demand로 실행할 수 있게 한다.
   - 합리적인 import window보다 오래 실행되면 task를 중지한다.
8. task를 수동으로 한 번 실행하고 Task Scheduler history와 `log_path`를 확인한다.

### schtasks 예시

먼저 path를 조정한다.

```powershell
schtasks /Create /TN "kb-win-sync" /SC DAILY /ST 09:00 /TR "%USERPROFILE%\kb-win-sync\run-kb-win-sync.bat"
```

나중에 삭제한다.

```powershell
schtasks /Delete /TN "kb-win-sync"
```

## 문제 해결

- Folder not found: Outlook folder tree에서 `outlook_path`를 다시 만든다.
- Outlook unavailable: classic Outlook을 사용하고 로그인된 상태에서 실행한다.
- Too many messages in dry-run: `outlook.folders`를 `_KB` subfolder로 좁힌다.
- Duplicate messages skipped: 성공적인 import 이후에는 정상이다. 의도한 경우에만 `--force`를 사용한다.
- SFTP failure: SSH preflight가 성공할 때까지 `sync.enabled: false`를 유지한다.
