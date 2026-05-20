# Windows SSH Key 설정

이 문서는 Windows의 `kb-win-sync`가 Linux raw vault로 SFTP sync를 수행할 때 필요한 `sync.key_path` 값을 설정하는 방법을 설명한다.

## 핵심 개념

`sync.key_path`는 Windows에서 Linux로 SSH/SFTP 접속할 때 사용할 private key file의 Windows 경로다.

예:

```yaml
sync:
  enabled: true
  host: "linux-dev.example.internal"
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "C:/Users/kangs.lee/.ssh/id_ed25519"
```

`key_path`에 적는 file은 Windows에 있어야 한다. Linux에는 이 private key와 짝을 이루는 public key를 `~/.ssh/authorized_keys`에 등록한다.

## 권장 Key 생성

Windows PowerShell에서 실행한다.

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -C "kb-win-sync"
```

자동 실행 편의성이 중요하면 passphrase를 비워둘 수 있다. 이 경우 Windows 계정 접근 권한과 private key file 권한을 더 엄격하게 관리해야 한다.

생성 후 Windows에는 두 file이 생긴다.

```text
C:\Users\kangs.lee\.ssh\id_ed25519      # private key, config.yaml의 sync.key_path에 넣는 값
C:\Users\kangs.lee\.ssh\id_ed25519.pub  # public key, Linux에 등록할 값
```

`id_rsa`를 이미 가지고 있고 조직 정책상 RSA key를 사용해야 한다면 기존 file을 사용할 수 있다. 새로 만드는 경우에는 `id_ed25519`를 권장한다.

## Linux에 Public Key 등록

Windows PowerShell에서 public key 내용을 확인한다.

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

출력된 한 줄 전체를 Linux server의 `~/.ssh/authorized_keys`에 추가한다.

Linux에서:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## 접속 Test

Windows PowerShell에서 SSH 접속을 검증한다.

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" your-linux-user@linux-dev.example.internal
```

이 명령이 성공해야 `kb-win-sync`의 SFTP sync도 같은 key로 동작할 수 있다.

## config.yaml 설정

접속 test가 성공하면 Windows local config에 같은 private key path를 넣는다.

```yaml
sync:
  enabled: true
  host: "linux-dev.example.internal"
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "C:/Users/kangs.lee/.ssh/id_ed25519"
```

Windows path는 YAML에서 slash(`/`)를 쓰는 형식이 가장 단순하다.

좋은 예:

```yaml
key_path: "C:/Users/kangs.lee/.ssh/id_ed25519"
```

주의가 필요한 예:

```yaml
key_path: "C:\Users\kangs.lee\.ssh\id_ed25519"
```

backslash를 쓰면 YAML escape 문제를 피하기 위해 별도 처리가 필요할 수 있다.

## 문제 해결

- `Permission denied (publickey)`: Linux `authorized_keys`에 public key가 등록되어 있는지 확인한다.
- `No such file or directory`: `sync.key_path`가 Windows에 실제 존재하는 private key file을 가리키는지 확인한다.
- `Bad permissions`: Linux의 `~/.ssh`는 `700`, `authorized_keys`는 `600`으로 설정한다.
- passphrase prompt 때문에 scheduled run이 멈춤: Task Scheduler 자동 실행에는 passphrase 없는 전용 key 또는 별도 SSH agent 구성이 필요하다.

private key, local config, token, vault data는 source repository에 커밋하지 않는다.
