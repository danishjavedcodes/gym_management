FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set timezone to Pakistan
RUN apt-get update && apt-get install -y tzdata
RUN ln -fs /usr/share/zoneinfo/Asia/Karachi /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

# Create and set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
