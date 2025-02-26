# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Create a virtual environment in /opt/venv
RUN python -m venv /opt/venv

# Ensure that the virtual environment’s binaries are used
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install the Python dependencies from requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your application code into the container
COPY app.py .

# Define the command to run your app using the virtual environment’s Python interpreter
CMD ["python", "app.py"]

