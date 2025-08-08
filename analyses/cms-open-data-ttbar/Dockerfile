# Базуємося на твоєму образі
FROM stellarsynapse/agc-container-xrd-pandas:latest

# Додаємо pandas (і заодно tqdm, якщо треба)
RUN pip install --no-cache-dir ml



# Робоча директорія у контейнері
WORKDIR /code

# За замовчуванням контейнер не виконує нічого
CMD ["/bin/bash"]
