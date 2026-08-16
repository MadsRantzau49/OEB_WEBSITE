FROM node:20-alpine AS build

ENV NODE_OPTIONS=--max-old-space-size=256
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv/frontend
