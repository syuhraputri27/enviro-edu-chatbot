# Gunakan image Python 3.10/3.11 resmi
FROM python:3.11-slim

# Tetapkan folder kerja di dalam 'container'
WORKDIR /code

# Salin file requirements
COPY requirements.txt .

# Install semua library Python
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Salin sisa kode aplikasi Anda
COPY . .

# (Perintah Procfile akan dijalankan secara otomatis,
# tapi kita tambahkan CMD untuk jaga-jaga)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860"]