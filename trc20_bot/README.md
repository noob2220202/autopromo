# TRC20 USDT 텔레그램 알림봇

## 실행 방법 (Docker 미사용)

```bash
cd trc20_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
python main.py
```

장기 운영 시에는 `systemd`, `tmux`, 혹은 Railway/Fly.io의 buildpack 배포(Dockerfile 불필요)를 사용하세요.
