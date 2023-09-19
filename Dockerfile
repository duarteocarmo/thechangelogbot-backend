FROM python:3.10

COPY requirements.txt pyproject.toml ./
COPY Makefile README.md  ./
COPY src/ src/
COPY config.yml config.yml
COPY api_runner.sh api_runner.sh

RUN python -m pip install --upgrade pip && \ 
	python -m pip install -r requirements.txt --no-cache-dir && \
	python -m pip install . --no-cache-dir 

RUN chmod +x api_runner.sh

WORKDIR /

EXPOSE 8000

CMD ["./api_runner.sh"]
