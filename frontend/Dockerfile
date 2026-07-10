# Forensic Wace frontend — build from the repository root:
#   docker build -f frontend/Dockerfile .

FROM node:20-alpine AS build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
# The entrypoint renders templates with envsubst; API_UPSTREAM selects the
# API backend (overridden by the Helm chart with the release service name).
ENV API_UPSTREAM=api:8080
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html
EXPOSE 80
