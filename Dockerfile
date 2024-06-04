FROM python:3.8

WORKDIR /app

COPY requirements.txt /app

RUN pip install -r requirements.txt --no-cache-dir

COPY app.py /app

COPY utils.py /app

COPY env.py /app

EXPOSE 8051

CMD [  "streamlit", "run", "app.py", "--server.port", "8051", "--server.enableXsrfProtection", "false", "--server.enableCORS", "false" ]
