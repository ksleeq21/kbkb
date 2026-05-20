# 보안 메모

- 이 저장소는 소스 코드 전용이다.
- vault 데이터, `.msg` 파일, 첨부파일, SQLite 데이터베이스, 로그, `.env`, 토큰, SSH 키, 로컬 config를 커밋하지 않는다.
- 이메일, 노트, 첨부파일, 검색된 context를 외부 SaaS 서비스에 업로드하지 않는다.
- API는 AI 소비자에게 읽기 전용이며 기본적으로 `127.0.0.1`에 바인딩해야 한다.
- health가 아닌 모든 API 호출에는 bearer-token 인증이 필요하다.
- 관리자 reindex는 별도의 admin token을 사용한다.
- 커밋되는 모든 fixture는 반드시 synthetic 데이터여야 한다.
