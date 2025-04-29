# Stage 1: Build the application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json
COPY web/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY web/ ./

# Build the application
RUN npm run build

# Stage 2: Serve the application
FROM node:18-alpine

WORKDIR /app

# Install serve to run the built application
RUN npm install -g serve

# Copy only the build artifacts from the builder stage
COPY --from=builder /app/build ./build

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["serve", "-s", "build", "-l", "3000"] 