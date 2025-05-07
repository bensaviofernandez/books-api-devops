# Build stage for tests
FROM python:3.11-slim AS test
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt pytest pytest-cov
COPY . .
CMD ["pytest"]

# Production stage
FROM python:3.11-slim AS production
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt
COPY . .
ENV FLASK_APP=app/__init__.py
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
