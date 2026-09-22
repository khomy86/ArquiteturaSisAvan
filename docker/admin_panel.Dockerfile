FROM docker.io/library/node:22-alpine AS build
WORKDIR /app
COPY admin_panel/package.json admin_panel/package-lock.json ./
RUN npm ci
COPY admin_panel/ ./
RUN npm run build

FROM docker.io/library/nginx:1.28-alpine
COPY docker/spa.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
