#Base Image
FROM python:3.11-slim

# System Settings 
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
    
# Workdir
WORKDIR /app
    
# System Dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*
    
# Python Dependencies 
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt
    
# Application Code 
COPY . /app
    
# Expose Port 
EXPOSE 8000
    
# Default Command 
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    