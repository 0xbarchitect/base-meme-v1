# TraderJoe v1 MM Bot
This repository contains source code of MM bot for TraderJoe v1.

## Prerequisites

- Conda3
- Python 3.11 virtual environment
- Foundry

## Setup

- Create virtual env and activate it, for simplicity, we name the vir env as `joev1-bot`
```bash
$ conda create -n joev1-bot python=3.11
$ conda activate joev1-bot
```

- Install dependencies
```bash
$ pip install -r requirements.txt
```

- Install [pyrevm](./pyrevm/README.md)

- Create .env file from template
```bash
$ cp .env.example .env
```

- Fulfill secrets and credentials to .env file

## Migrate 

- Execute DB migrations
```bash
$ python manage.py migrate
```

## Run

- Start bot
```bash
$ python main.py
```