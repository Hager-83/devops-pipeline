Step 1  → Understand the Flask application
Step 2  → Run it locally
Step 3  → Write the Dockerfile
Step 4  → Build and run the Docker image
Step 5  → Add Docker healthcheck
Step 6  → Create docker-compose.yml
Step 7  → Add environment variables
Step 8  → Understand and run pytest
Step 9  → Create GitHub Actions CI
Step 10 → Add Docker build to CI
Step 11 → Deploy to staging
Step 12 → Add Prometheus monitoring
Step 13 → Add logging
Step 14 → Write the final README





-------------------------------------------

# build 
```
 docker build -t devops-pipeline .
```

![alt text](../images/1.png)

```
docker images
```

![alt text](../images/2.png)

run the container 
```
docker run -p 5000:5000 devops-pipeline
```

![alt text](../images/3.png)

```
http://localhost:5000
```

![alt text](../images/4.png)

![alt text](../images/5.png)

after adding helth check 

![alt text](../images/6.png)

```
http://localhost:5000/health

```

![alt text](../images/7.png)



![alt text](../images/image.png)