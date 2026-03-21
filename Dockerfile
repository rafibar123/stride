FROM ultralytics/ultralytics:latest
WORKDIR /app
COPY requirements-railway.txt .
RUN pip install -r requirements-railway.txt
COPY . .
CMD ["python3", "start.py"]
