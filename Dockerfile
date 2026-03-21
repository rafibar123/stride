FROM ultralytics/ultralytics:latest
WORKDIR /app
COPY requirements-railway.txt .
RUN pip install -r requirements-railway.txt
RUN python3 -c "import cv2; import ultralytics; print('cv2:', cv2.__version__, '  ultralytics OK')"
COPY . .
CMD ["python3", "start.py"]
