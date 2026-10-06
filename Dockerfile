name: CI

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

jobs:
  test:

    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -r app/requirements.txt

      - name: Run tests
        run: |
          pytest

      - name: Build Docker image
        run: |
          docker build -t devops-pipeline .

      - name: Run Docker container
        run: |
          docker run -d \
            --name devops-app-test \
            -p 5000:5000 \
            devops-pipeline

      - name: Wait for application
        run: |
          sleep 5

      - name: Test application health
        run: |
          curl --fail http://localhost:5000/health

      - name: Stop Docker container
        if: always()
        run: |
          docker stop devops-app-test
          docker rm devops-app-test