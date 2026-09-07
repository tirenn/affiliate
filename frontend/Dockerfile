FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG INTERNAL_API_URL
ENV INTERNAL_API_URL=$INTERNAL_API_URL

COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

ARG INTERNAL_API_URL
ENV INTERNAL_API_URL=$INTERNAL_API_URL

COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

CMD ["sh", "-c", "npm start -- -p ${PORT}"]
