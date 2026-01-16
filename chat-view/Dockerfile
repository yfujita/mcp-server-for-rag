FROM node:25-slim

WORKDIR /app

# package.jsonだけ先にコピーして依存関係をインストール
# これによりソースコード変更時にnpm installが再実行されるのを防ぐ（キャッシュ利用）
COPY package*.json ./
COPY package-lock.json ./
RUN npm install

# ソースコードをコピー
COPY . .

# Viteのデフォルトポート
EXPOSE 5173

# ホストからアクセスできるように --host オプションを付与
CMD ["npm", "run", "dev", "--", "--host"]