# Linux Token 생성

이 문서는 Linux에서 `KB_API_TOKEN`과 `KB_API_ADMIN_TOKEN`을 생성하고 설정하는 방법을 설명한다.

`KB_ADMIN_TOKEN`이 아니라 `KB_API_ADMIN_TOKEN`을 사용한다. 기본 config와 server code는 `KB_API_ADMIN_TOKEN` 환경 변수를 읽는다.

## Token 용도

- `KB_API_TOKEN`: `/search`, `/notes/by-path`, `/context` 같은 read-only endpoint에 사용하는 bearer token.
- `KB_API_ADMIN_TOKEN`: `/admin/reindex` 같은 admin endpoint에 사용하는 별도 bearer token.

두 token은 서로 다른 값이어야 한다.

## init-config 자동 생성

`kb-api init-config`는 config와 기본 directory를 만들 때 현재 shell에 맞는 rc file에도 token export block을 추가한다.

```bash
kb-api init-config --output ~/.config/kb-api/config.yaml
source ~/.zshrc  # bash를 사용하면 source ~/.bashrc
```

추가되는 block에는 `kb-api` local bearer token 용도와 보안 주의 주석이 포함된다. 같은 marker block이 이미 있으면 중복으로 추가하지 않는다.

## 임시 Shell Session용 Token 생성

Linux shell에서 다음을 실행한다.

```bash
export KB_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export KB_API_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

현재 shell에 token이 설정되었는지 값 없이 확인한다.

```bash
test -n "$KB_API_TOKEN" && echo "KB_API_TOKEN is set"
test -n "$KB_API_ADMIN_TOKEN" && echo "KB_API_ADMIN_TOKEN is set"
```

이 방식은 현재 shell session과 그 shell에서 시작한 process에만 적용된다.

## systemd Service용 Token 저장

user-level systemd service로 `kb-api`를 실행할 때는 repository 밖에 private environment file을 만든다.

```bash
mkdir -p ~/.config/kb-api
chmod 700 ~/.config/kb-api

KB_API_TOKEN_VALUE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
KB_API_ADMIN_TOKEN_VALUE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

printf 'KB_API_TOKEN=%s\nKB_API_ADMIN_TOKEN=%s\n' \
  "$KB_API_TOKEN_VALUE" \
  "$KB_API_ADMIN_TOKEN_VALUE" \
  > ~/.config/kb-api/env

chmod 600 ~/.config/kb-api/env
unset KB_API_TOKEN_VALUE KB_API_ADMIN_TOKEN_VALUE
```

service file에는 다음 줄을 둔다.

```ini
EnvironmentFile=%h/.config/kb-api/env
```

`examples/kb-api.service`는 이 pattern을 이미 사용한다. machine마다 `WorkingDirectory`와 `ExecStart`는 실제 설치 경로에 맞게 수정한다.

## API 호출 확인

API process가 token을 읽은 상태로 실행 중이면 다른 shell에서 같은 token을 불러와 확인한다.

```bash
set -a
source ~/.config/kb-api/env
set +a

curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/search?q=SSO' \
  -H "Authorization: Bearer $KB_API_TOKEN"
```

admin token은 admin endpoint에만 사용한다.

```bash
curl -sS -X POST http://127.0.0.1:8765/admin/reindex \
  -H "Authorization: Bearer $KB_API_ADMIN_TOKEN"
```

## 보안 주의

- token 값을 README, config example, shell history note, issue, commit message에 붙여 넣지 않는다.
- `~/.config/kb-api/env`는 source repository 밖에 둔다.
- token file permission은 `600`, 상위 directory permission은 `700`을 권장한다.
- token 값이 log에 출력되었거나 저장소에 커밋되었으면 즉시 새 token으로 교체한다.
