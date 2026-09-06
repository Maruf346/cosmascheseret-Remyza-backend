# Chesera Backend - AWS Deployment and CI/CD Guide

> **Stack**: Django 6, Gunicorn, Nginx, Docker, AWS EC2 + RDS (PostgreSQL) + S3 + ECR, GitHub Actions
> **Last updated**: 2026-09-06

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [AWS IAM — Create Deployment User](#2-aws-iam--create-deployment-user)
3. [AWS ECR — Container Registry](#3-aws-ecr--container-registry)
4. [AWS RDS — PostgreSQL Database](#4-aws-rds--postgresql-database)
5. [AWS S3 — Media Storage](#5-aws-s3--media-storage)
6. [AWS EC2 — Server Setup](#6-aws-ec2--server-setup)
7. [GitHub Secrets & Variables](#7-github-secrets--variables)
8. [First-time EC2 App Bootstrap](#8-first-time-ec2-app-bootstrap)
9. [Nginx Setup on EC2](#9-nginx-setup-on-ec2)
10. [SSL with Let's Encrypt (Certbot)](#10-ssl-with-lets-encrypt-certbot)
11. [Automatic Certificate Renewal](#11-automatic-certificate-renewal)
12. [CI/CD Flow - How It Works](#12-cicd-flow--how-it-works)
13. [Domain Setup (DNS)](#13-domain-setup-dns)
14. [Monitoring & Logs](#14-monitoring--logs)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Architecture Overview

```
Developer pushes to main
        |
        v
GitHub Actions (CI/CD)
  [1] Build Docker image (Dockerfile.prod)
  [2] Push to AWS ECR
  [3] SSH into EC2
  [4] docker compose pull + up
        |
        v
EC2 Instance
  Nginx (80/443)  -->  Gunicorn :8005 (Docker container)
                          |
                    RDS PostgreSQL
                    S3 (media files)
```

---

## 2. AWS IAM — Create Deployment User

This user is used **only** for CI/CD (GitHub Actions). It needs ECR push access.

### Steps (AWS Console ? IAM)

1. Go to **AWS Console** ? search `IAM` ? open it
2. Left sidebar ? **Users** ? **Create user**
3. **User name**: `remyza-github-deployer`
4. Click **Next** (no console access needed)
5. **Set permissions** ? choose **Attach policies directly**
6. Search and attach these policies:
   - `AmazonEC2ContainerRegistryPowerUser` ? for ECR push
   - *(Do NOT add S3 or RDS here — those are managed by the EC2 instance role)*
7. Click **Next** ? **Create user**
8. Click on the user ? **Security credentials** tab
9. Scroll to **Access keys** ? **Create access key**
10. Use case: **Application running outside AWS** ? Next
11. Click **Create access key**
12. **COPY BOTH VALUES NOW** (you won't see the secret again):
    - `Access key ID` ? will go to GitHub secret `AWS_ACCESS_KEY_ID`
    - `Secret access key` ? will go to GitHub secret `AWS_SECRET_ACCESS_KEY`

### EC2 Instance Role (for ECR pull + S3 access on the server)

1. IAM ? **Roles** ? **Create role**
2. Trusted entity: **AWS service** ? **EC2** ? Next
3. Attach policies:
   - `AmazonEC2ContainerRegistryReadOnly` ? pull images
   - `AmazonS3FullAccess` ? media file read/write
   - *(or create a custom policy scoped to your specific bucket)*
4. Role name: `remyza-ec2-role` ? Create role
5. Go to **EC2** ? select your instance ? **Actions ? Security ? Modify IAM role** ? select `remyza-ec2-role`

---

## 3. AWS ECR — Container Registry

ECR stores your Docker images privately.

### Steps (AWS Console ? ECR)

1. Search `ECR` ? **Elastic Container Registry**
2. **Create repository**
3. Settings:
   - **Visibility**: Private
   - **Repository name**: `remyza-backend`
   - **Image tag mutability**: Mutable
   - **Scan on push**: Enable ?
4. Click **Create repository**
5. Copy the **URI** — it looks like:
   `123456789012.dkr.ecr.us-east-1.amazonaws.com/remyza-backend`
   - The part before `/remyza-backend` is your **ECR Registry**
   - `remyza-backend` is your **ECR Repository name**

> Save these — they go into GitHub vars `ECR_REPOSITORY` and secret `ECR_REGISTRY`

---

## 4. AWS RDS — PostgreSQL Database

### Steps (AWS Console ? RDS)

1. Search `RDS` ? **Create database**
2. **Database creation method**: Standard create
3. **Engine**: PostgreSQL (latest 16.x)
4. **Templates**: Free tier (dev) or Production
5. **Settings**:
   - **DB instance identifier**: `remyza-db`
   - **Master username**: `remyza_user`
   - **Master password**: (create a strong password, save it)
6. **DB instance class**: `db.t3.micro` (start here, scale up later)
7. **Storage**: 20 GB gp2 (enable autoscaling)
8. **Connectivity**:
   - **VPC**: same VPC as your EC2
   - **Public access**: NO ? keep database private
   - **VPC security group**: Create new ? name it `remyza-rds-sg`
9. **Additional configuration**:
   - **Initial database name**: `remyza_db`
10. Click **Create database** (takes ~5 min)
11. Once created, copy the **Endpoint** (e.g. `remyza-db.xxxx.us-east-1.rds.amazonaws.com`)

### Allow EC2 to connect to RDS

1. Go to **EC2** ? select your instance ? note the **Security Group** name
2. Go to **RDS** ? your DB ? **Connectivity & security** ? click the security group (`remyza-rds-sg`)
3. **Inbound rules** ? **Edit inbound rules** ? **Add rule**:
   - Type: `PostgreSQL`
   - Port: `5432`
   - Source: **Custom** ? select the EC2 security group (type its name in the box)
4. Save rules

---

## 5. AWS S3 — Media Storage

### Create Bucket

1. Search `S3` ? **Create bucket**
2. **Bucket name**: `remyza-media-prod`
3. **Region**: same as EC2 (e.g. `us-east-1`)
4. **Block Public Access**: KEEP ALL BLOCKED ?
   (files are accessed via signed URLs or through Django)
5. Leave everything else default ? **Create bucket**

### Bucket CORS (needed for direct file access from frontend)

1. Go to your bucket ? **Permissions** tab ? **CORS** ? Edit
2. Paste:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedOrigins": ["https://trychesera.com", "https://www.trychesera.com", "https://api.trychesera.com"],
    "ExposeHeaders": ["ETag"]
  }
]
```
3. Save

### Bucket Policy (allow EC2 instance role to access it)

Go to **Permissions** ? **Bucket policy** ? paste (replace `ACCOUNT_ID` and bucket name):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEC2RoleAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:role/remyza-ec2-role"
      },
      "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
      "Resource": "arn:aws:s3:::remyza-media-prod/*"
    }
  ]
}
```

---

## 6. AWS EC2 — Server Setup

### Launch Instance

1. Search `EC2` ? **Launch instance**
2. **Name**: `remyza-backend`
3. **AMI**: Ubuntu 24.04 LTS (64-bit x86)
4. **Instance type**: `t3.small` minimum (t3.medium recommended for production)
5. **Key pair**: Create new ? name `remyza-key` ? RSA ? `.pem` ? **Download** (save it!)
6. **Network settings**:
   - **VPC**: default (or your custom VPC)
   - **Auto-assign public IP**: Enable
   - **Security group**: Create new ? name `remyza-ec2-sg`
     - Add rules:
       | Type       | Port | Source      |
       |------------|------|-------------|
       | SSH        | 22   | My IP only  |
       | HTTP       | 80   | Anywhere    |
       | HTTPS      | 443  | Anywhere    |
7. **Storage**: 20 GB gp3
8. Click **Launch instance**

### Connect to EC2

```bash
# From your local machine (first time)
chmod 400 remyza-key.pem
ssh -i remyza-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### Install Docker & AWS CLI on EC2

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker   # apply group without logout

# Install Docker Compose plugin
sudo apt-get install docker-compose-plugin -y

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt-get install unzip -y
unzip awscliv2.zip
sudo ./aws/install
aws --version

# Install Nginx
sudo apt-get install nginx -y
sudo systemctl enable nginx

# Install Certbot
sudo apt-get install certbot python3-certbot-nginx -y
```

---

## 7. GitHub Secrets & Variables

Go to your GitHub repo ? **Settings** ? **Secrets and variables** ? **Actions**

### Secrets (sensitive — encrypted)

| Secret Name             | Value                                                   |
|-------------------------|---------------------------------------------------------|
| `AWS_ACCESS_KEY_ID`     | From IAM user created in Step 2                         |
| `AWS_SECRET_ACCESS_KEY` | From IAM user created in Step 2                         |
| `ECR_REGISTRY`          | `123456789012.dkr.ecr.us-east-1.amazonaws.com`          |
| `EC2_HOST`              | Your EC2 public IP or elastic IP                        |
| `EC2_USER`              | `ubuntu`                                                |
| `EC2_SSH_KEY`           | **Full content** of your `.pem` key file (paste all of it) |

> For `EC2_SSH_KEY`: open your `.pem` file in a text editor, select ALL text including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`, and paste into the secret value.

### Variables (non-sensitive — visible in logs)

Go to **Variables** tab (next to Secrets):

| Variable Name    | Value                   |
|------------------|-------------------------|
| `AWS_REGION`     | `us-east-1`             |
| `ECR_REPOSITORY` | `remyza-backend`        |

---

## 8. First-time EC2 App Bootstrap

Do this **once** on the server before the first CI/CD run.

```bash
# On EC2
mkdir -p ~/app
cd ~/app

# Create .env from the template
nano .env
# ? Paste contents of .env.production.example with all real values filled in

# Pull and start manually the first time
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS \
  --password-stdin YOUR_ECR_REGISTRY

docker pull YOUR_ECR_REGISTRY/remyza-backend:latest

# Copy docker-compose.prod.yml to server
scp -i remyza-key.pem docker-compose.prod.yml ubuntu@EC2_IP:~/app/

# Start
cd ~/app
docker compose -f docker-compose.prod.yml up -d

# Verify
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

---

## 9. Nginx Setup on EC2

Current phase: **HTTP only**.

Use this before DNS/SSL is fully ready. Do not enable the HTTPS server block until Certbot has created the certificate files.

If you are using PuTTY, you do not need `scp`. Open the Nginx site file directly on EC2:

```bash
sudo nano /etc/nginx/sites-available/remyza
```

Paste the current HTTP-only config:

```nginx
upstream django_backend {
    server 127.0.0.1:8005;
}

server {
    listen 80;
    listen [::]:80;
    server_name api.trychesera.com _;

    client_max_body_size 200M;

    location / {
        proxy_pass          http://django_backend;
        proxy_http_version  1.1;
        proxy_set_header    Host              $host;
        proxy_set_header    X-Real-IP         $remote_addr;
        proxy_set_header    X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header    X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout    120s;
        proxy_read_timeout    120s;
    }

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    access_log /var/log/nginx/chesera_access.log;
    error_log  /var/log/nginx/chesera_error.log warn;
}
```

Save in nano:

```text
CTRL + O
Enter
CTRL + X
```

Enable the site and reload Nginx:

```bash
sudo ln -sf /etc/nginx/sites-available/remyza /etc/nginx/sites-enabled/remyza
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

If Nginx is stopped, use:

```bash
sudo systemctl restart nginx
```

Before SSL, test HTTP:

```bash
curl -I http://api.trychesera.com
```

If DNS is not ready yet, test the EC2 public IP:

```bash
curl -I http://EC2_PUBLIC_IP
```

The `_` fallback in `server_name api.trychesera.com _;` allows basic IP testing.

## 10. SSL with Let's Encrypt (Certbot)

**Prerequisite**: Your domain DNS must point to EC2 public IP first (see Step 13).

```bash
# On EC2 — get certificate
sudo certbot --nginx -d api.trychesera.com

# Certbot will:
# 1. Ask your email address (for renewal notices)
# 2. Ask you to agree to ToS - A
# 3. Ask if you want to share email ? N (optional)
# 4. Automatically edit nginx config with SSL paths
# 5. Reload nginx

# Verify HTTPS works
curl -I https://api.trychesera.com/api/v1/health/
```

---

## 11. Automatic Certificate Renewal

Certbot installs a systemd timer automatically. Verify it:

```bash
# Check renewal timer is active
sudo systemctl status certbot.timer

# Test dry-run renewal
sudo certbot renew --dry-run

# If you want a cron backup (optional - certbot timer already handles this):
sudo crontab -e
# Add this line:
0 3 * * * certbot renew --quiet && systemctl reload nginx
```

---

12. [CI/CD Flow - How It Works](#12-cicd-flow--how-it-works)

```
git push origin main
       |
       v
GitHub Actions: deploy.yml
  Job 1: build-and-push
    - Checkout code
    - Authenticate to ECR
    - docker build -f Dockerfile.prod
    - Push image with commit SHA tag + latest tag

  Job 2: deploy (runs after Job 1)
    - SSH into EC2
    - aws ecr get-login-password | docker login
    - docker pull latest image
    - docker compose -f docker-compose.prod.yml up -d
    - docker image prune -f
```

### To deploy:

```bash
git add .
git commit -m "feat: your change"
git push origin main
# ? GitHub Actions starts automatically
# ? Monitor at: github.com/YOUR_ORG/REPO/actions
```

---

## 13. Domain Setup (DNS)

### If using Route 53 (AWS):

1. Go to **Route 53** ? **Hosted zones** ? Create hosted zone
2. Domain name: `trychesera.com` ? Public hosted zone ? Create
3. Copy the 4 **NS (Name Server)** records from Route 53
4. Go to your domain registrar (GoDaddy / Namecheap / etc.)
5. Update nameservers to the 4 Route 53 NS values
6. Back in Route 53 ? Create records:
   | Record name  | Type | Value              |
   |--------------|------|--------------------|
   | `api`        | A    | EC2 Public IP      |
   | (blank/`@`)  | A    | EC2 Public IP (if frontend on same server) |

### If using another DNS provider:

Add an **A record**:
- Host/Name: `api`
- Points to: Your EC2 public IP
- TTL: 300

> DNS changes take 5–30 min to propagate globally.

---

## 14. Monitoring & Logs

```bash
# View running containers
docker compose -f ~/app/docker-compose.prod.yml ps

# View backend logs (live)
docker compose -f ~/app/docker-compose.prod.yml logs -f backend

# View last 100 lines
docker compose -f ~/app/docker-compose.prod.yml logs --tail=100 backend

# View nginx logs
sudo tail -f /var/log/nginx/remyza_access.log
sudo tail -f /var/log/nginx/remyza_error.log

# Django shell inside container
docker exec -it cheshara_backend python manage.py shell

# Run manual migration inside container
docker exec -it cheshara_backend python manage.py migrate

# Check disk space
df -h

# Check memory
free -h
```

---

## 15. Troubleshooting

| Problem | Fix |
|---------|-----|
| `502 Bad Gateway` from Nginx | Backend container not running. Check `docker ps` and `docker logs cheshara_backend` |
| `DATABASE connection refused` | Check DB_HOST in .env. Check RDS security group allows EC2 SG on port 5432 |
| `S3 Access Denied` | Check EC2 instance IAM role has S3 access. Check bucket policy |
| `Certificate not found` error in Nginx | Run certbot first before enabling SSL server block |
| GitHub Actions `ECR login failed` | Check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets are set correctly |
| GitHub Actions `SSH connection failed` | Check `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`. Make sure port 22 is open in EC2 security group from GitHub Actions IPs |
| `collectstatic` fails in Docker build | Make sure `DJANGO_SETTINGS_MODULE` is set and all env vars needed at import time have defaults |
| Container keeps restarting | Run `docker logs cheshara_backend` to see the crash reason |

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `Dockerfile.prod` | Production Docker image (Python 3.12-slim, non-root user) |
| `entrypoint.sh` | Runs migrations then starts Gunicorn |
| `docker-compose.prod.yml` | Production compose (no local DB — uses RDS) |
| `.dockerignore` | Keeps image lean |
| `nginx/nginx.conf` | Nginx reverse proxy. Current phase is HTTP-only for `api.trychesera.com`; HTTPS is enabled later after Certbot. |
| `.github/workflows/deploy.yml` | GitHub Actions CI/CD pipeline |
| `.env.production.example` | Template for production .env (never commit real .env) |
| `cheshara_config/settings.py` | Updated: PostgreSQL, S3 storage, env-based email |
| `requirements.txt` | Added: gunicorn, psycopg2-binary, django-storages, boto3 |
| `.codex/DEPLOYMENT.md` | This guide |
