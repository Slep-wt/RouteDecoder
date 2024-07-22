FROM ubuntu:latest

# Install system dependencies, including cron
RUN apt-get update && apt-get install -y python3 python3-pip cron wget curl openjdk-11-jre

# Install Python packages from requirements.txt
COPY requirements.txt /app/
WORKDIR /app
RUN pip3 install -r requirements.txt
RUN pip3 install -U python-dotenv

ENV PYTHONUNBUFFERED=1

# Copy your script
COPY . /app/


# Create a crontab
RUN crontab crontab

# Start cron
CMD cron -f -l 8 2>&1 && crontab -l
