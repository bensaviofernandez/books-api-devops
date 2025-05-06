FROM python:3.11-slim

WORKDIR /app

# Upgrade pip and setuptools to address security CVEs
RUN pip install --upgrade pip setuptools

COPY . /app/
RUN pip install -r requirements.txt
RUN pip install pytest pytest-cov

CMD ["pytest"]
