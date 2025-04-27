# Use an official Node runtime as a parent image
FROM node:18-alpine

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

# Install `serve` to run the static build
RUN npm install -g serve

# Expose the port the app runs on (serve defaults to 3000)
EXPOSE 3000

# Command to serve the static files
CMD ["serve", "-s", "build", "-l", "3000"] 