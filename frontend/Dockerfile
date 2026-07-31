FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# RCC is distributed locally as a rebuilt container, without a bind mount for
# frontend sources. Running Next's development/HMR runtime here only leaves
# open browser tabs with incompatible module graphs after a container rebuild.
# Build once and serve immutable, hashed production assets instead.
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
