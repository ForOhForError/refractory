#!/bin/bash
export DJANGO_SECRET="SECRETHERE"
while true
do
  poetry run python src/main.py
done
