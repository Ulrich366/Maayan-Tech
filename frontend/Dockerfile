FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Vite bakes these into the static JS bundle at build time — must be declared as
# ARG and forwarded to ENV so `npm run build` picks them up via import.meta.env.
# Railway automatically injects service variables of the same name as build args
# when they are declared here (see docs.railway.com/builds/dockerfiles).
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
