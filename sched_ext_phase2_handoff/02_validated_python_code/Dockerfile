FROM python:3.12-slim

RUN pip install --no-cache-dir matplotlib scipy pytest

WORKDIR /work

# Nothing else to install — this is deliberately minimal so the image
# builds in seconds, not minutes. Source files are mounted at runtime
# (see run.sh), not copied in, so you can edit locally and re-run
# without rebuilding the image.

CMD ["python", "experiment.py"]
