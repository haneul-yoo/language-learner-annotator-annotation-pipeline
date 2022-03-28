# gunicorn -w 8 -b 0.0.0.0:58108 main:app
# gunicorn -w 8 -b 0.0.0.0:5000 main:app
gunicorn main:app \
    --workers 8 \
    --bind 0.0.0.0:5000 \
    --access-logfile access.log \
    --error-logfile error.log \
    --reload