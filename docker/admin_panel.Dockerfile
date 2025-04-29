# Stage 1: Build the React app
FROM node:18-alpine AS builder

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock) first
# to leverage Docker cache for dependencies
COPY admin_panel/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the admin panel application code into the container
COPY admin_panel/ .

# Build the React app for production
RUN npm run build

# Stage 2: Serve the static files
FROM node:18-alpine

WORKDIR /app

# Install `serve` to run the static build
RUN npm install -g serve

# Copy the build output from the builder stage
COPY --from=builder /app/build ./build

# Expose the port the app runs on (serve defaults to 3000)
EXPOSE 3000

# Command to serve the static files
CMD ["serve", "-s", "build", "-l", "3000"] 