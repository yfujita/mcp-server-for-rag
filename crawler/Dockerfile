# ベースイメージ
FROM python:3.10-slim-buster

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY app/ .
COPY run.sh .

# 実行スクリプトに実行権限を付与
RUN chmod +x run.sh

# 実行コマンドを定義
# run.shスクリプトを実行
CMD ["./run.sh"]
