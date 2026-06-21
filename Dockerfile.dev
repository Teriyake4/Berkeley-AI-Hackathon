FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# npm ci fails cross-platform (macOS lockfile vs Linux optional deps);
# npm install resolves correctly inside the container.
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
