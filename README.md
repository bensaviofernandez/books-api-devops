# Books API – DevSecOps Pipeline

[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://jenkins.example.com/job/books-api-pipeline/) 


> **Seven‑stage Jenkins pipeline with security scanning & live monitoring**

---

## 📚 What is this project?

The **Books API** is a minimal Flask service for CRUD operations on a JSON book catalogue.  It doubles as a learning sandbox for DevOps best practices:

* Multi‑stage **Docker** builds (test + production images)
* **CI/CD** in Jenkins, triggered by GitHub webhooks
* **SonarQube** code‑quality gate
* **Aqua Trivy** image vulnerability scanning
* **Blue‑green style** deploy to staging & production containers
* **Prometheus + Grafana** observability with alert rules



## 🚀 Quick start

```bash
# 1. clone
$ git clone https://github.com/bensaviofernandez/books-api-devops.git && cd books-api-devops

# 2. build & run locally
$ docker compose up -d --build books-api
# → API listening on http://localhost:5000/books

# 3. run tests
$ docker compose run books-api-test pytest -v
```

## 🛠 Local development

| Tool       | Version   | Notes                                                   |
| ---------- | --------- | ------------------------------------------------------- |
| Python     | 3.12      | See `pyproject.toml`                                    |
| Docker     | 24.x      | Enable BuildKit for caching                             |
| Jenkins    | LTS 2.452 | Pipeline as code (see `Jenkinsfile`)                    |
| SonarQube  | 10.5 LTS  | Run via `docker compose -f monitoring.yml up sonarqube` |
| Prometheus | 2.52      | Scrapes `/metrics` every 5 s                            |
| Grafana    | 11.0      | Auto‑provisioned dashboard JSON                         |

## 🛡️ Security gates

* **Trivy** blocks the pipeline on *HIGH* / *CRITICAL* CVEs.
* Dependabot PRs keep Python & Alpine base images patched.

## 📈 Metrics endpoint

The Flask app exposes Prometheus metrics at `/metrics`:

* `books_api_requests_total{method,endpoint,status}`
* `books_api_request_duration_seconds`
* `books_api_books_count`

Alert rules live in `monitoring/rules/books_api_alerts.yml`.






